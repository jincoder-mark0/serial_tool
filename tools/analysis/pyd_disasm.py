"""
pyd_disasm.py — 원본 .pyd 정적 분석 도구 (읽기 전용, 코드 실행 없음)

`ui/_reference/main_window.pyd` 처럼 심볼이 없는 Cython 네이티브 모듈에서 함수와 상수를 잇는다.
pyd-analysis 스킬 §6 "최소 시도 목록"의 1~7을 구현한다. **파일을 읽기만 하며 모듈을 import 하거나
어떤 코드도 실행하지 않는다** (RULES.md §4).

사용:
  python tools/analysis/pyd_disasm.py strings              # 문자열 테이블 복원 (735개)
  python tools/analysis/pyd_disasm.py methods              # PyMethodDef 목록 (이름/함수RVA/docstring)
  python tools/analysis/pyd_disasm.py refs <시작RVA> <끝RVA>   # 함수의 문자열 참조를 최초 등장 순으로
  python tools/analysis/pyd_disasm.py disasm <시작RVA> <끝RVA> # 심볼 주석 디스어셈블 (capstone 필요)

capstone 은 선택 사항이며 `disasm` 하위 명령에만 필요하다. 프로젝트 venv 를 오염시키지 말고
`pip install --target <스크래치>/pylib capstone` 으로 격리 설치한 뒤 PYTHONPATH 로 지정한다.
"""
import argparse
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PYD = REPO_ROOT / "ui" / "_reference" / "main_window.pyd"


class Pyd:
    """PE 파싱 + Cython 문자열/정수 테이블 복원."""

    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self._parse_pe()
        self._load_strings()

    # ---------------------------------------------------------------- PE
    def _parse_pe(self):
        d = self.data
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        assert d[pe:pe + 4] == b"PE\0\0", "PE 서명 없음"
        coff = pe + 4
        nsec, opt_size = struct.unpack_from("<H", d, coff + 2)[0], struct.unpack_from("<H", d, coff + 16)[0]
        opt = coff + 20
        assert struct.unpack_from("<H", d, opt)[0] == 0x20B, "PE32+ 아님"
        self.image_base = struct.unpack_from("<Q", d, opt + 24)[0]
        self.sections = []
        for i in range(nsec):
            o = opt + opt_size + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode()
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", d, o + 8)
            self.sections.append(dict(name=name, vaddr=vaddr, vsize=vsize,
                                      rawptr=rawptr, rawsize=rawsize))

    def rva_to_off(self, rva):
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["rawsize"]):
                d = rva - s["vaddr"]
                return s["rawptr"] + d if d < s["rawsize"] else None
        return None

    def off_to_rva(self, off):
        for s in self.sections:
            if s["rawptr"] <= off < s["rawptr"] + s["rawsize"]:
                return s["vaddr"] + (off - s["rawptr"])
        return None

    def sec_of_rva(self, rva):
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["rawsize"]):
                return s["name"]
        return None

    # ------------------------------------------------------- .pdata 함수 경계
    def functions(self):
        pd = next((s for s in self.sections if s["name"] == ".pdata"), None)
        if pd is None:
            return []
        out = []
        for o in range(pd["rawptr"], pd["rawptr"] + pd["rawsize"], 12):
            beg, end, _ = struct.unpack_from("<III", self.data, o)
            if beg or end:
                out.append((beg, end))
        return sorted(out)

    def func_span(self, rva):
        """rva 로 시작하는 함수의 전체 범위. 인접한 .pdata 조각을 이어 붙인다."""
        funcs = self.functions()
        end = rva
        for s, e in funcs:
            if s == end:
                end = e
            elif s > end:
                break
        return (rva, end) if end > rva else None

    # --------------------------------------------------- 문자열/정수 테이블
    def _find_zlib_blob(self):
        d = self.data
        for i in range(len(d) - 1):
            if d[i] != 0x78:
                continue
            if (d[i] * 256 + d[i + 1]) % 31 != 0 or (d[i + 1] & 0x20):
                continue
            try:
                out = zlib.decompressobj().decompress(d[i:], 4 << 20)
            except zlib.error:
                continue
            if len(out) > 1024:
                return i, out
        return None, None

    def _find_len_array(self, total):
        """원소 합이 정확히 total 이 되는 uint32 배열의 시작 오프셋."""
        d = self.data
        for sec in self.sections:
            lo, hi = sec["rawptr"], sec["rawptr"] + sec["rawsize"]
            n = (hi - lo) // 4
            if n < 200:
                continue
            vals = struct.unpack_from("<" + "I" * n, d, lo)
            pref, idx = [0], {0: 0}
            for j, v in enumerate(vals, 1):
                pref.append(pref[-1] + v)
                if pref[-1] - total in idx and j - idx[pref[-1] - total] >= 200:
                    return lo + idx[pref[-1] - total] * 4
                idx.setdefault(pref[-1], j)
        return None

    def _load_strings(self):
        self.blob_off, blob = self._find_zlib_blob()
        self.strings = []
        self.len_off = None
        if blob is None:
            return
        self.len_off = self._find_len_array(len(blob))
        if self.len_off is None:
            return
        pos, o = 0, self.len_off
        while pos < len(blob):
            v = struct.unpack_from("<I", self.data, o)[0]
            if v > 4096 or pos + v > len(blob):
                break
            self.strings.append(blob[pos:pos + v].decode("utf-8", "replace"))
            pos += v
            o += 4

    def find_string_base(self, probe_rvas, expected):
        """전역 배열 베이스를 적합으로 찾는다. expected 는 그 함수가 쓸 문자열 집합."""
        best = (0, None)
        for b in range(0x44000, 0x48000, 8):
            hit = sum(1 for t in probe_rvas
                      if 0 <= (t - b) // 8 < len(self.strings)
                      and self.strings[(t - b) // 8] in expected)
            if hit > best[0]:
                best = (hit, b)
        return best[1]

    # --------------------------------------------------------- PyMethodDef
    def method_defs(self):
        """(.data 오프셋, ml_name, 함수 RVA, flags, docstring 첫 줄) 목록."""
        d, ib = self.data, self.image_base
        out = []
        for sec in self.sections:
            if sec["name"] not in (".data", ".rdata"):
                continue
            lo, hi = sec["rawptr"], sec["rawptr"] + sec["rawsize"]
            for base in range(lo, max(lo, hi - 32), 8):
                nm_p, meth, flags, doc_p = struct.unpack_from("<QQqQ", d, base)
                if not (ib < nm_p < ib + 0x100000 and ib < meth < ib + 0x100000):
                    continue
                o = self.rva_to_off(nm_p - ib)
                if o is None:
                    continue
                e = d.find(b"\0", o, o + 48)
                if e < 0:
                    continue
                nm = d[o:e].decode("utf-8", "replace")
                if not nm or not all(c.isalnum() or c == "_" for c in nm):
                    continue
                doc = ""
                if ib < doc_p < ib + 0x100000:
                    do = self.rva_to_off(doc_p - ib)
                    if do:
                        de = d.find(b"\0", do, do + 400)
                        if de > 0:
                            doc = d[do:de].decode("utf-8", "replace").split("\n")[0]
                out.append((base, nm, meth - ib, flags, doc))
        return out

    # ------------------------------------------------- RIP 상대 참조 추출
    _MODRM = {0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D}

    def rip_refs(self, beg, end):
        """(참조 명령 RVA, 타깃 RVA) 를 순서대로. 경량 스캐너이므로 오탐이 섞일 수 있다."""
        off = self.rva_to_off(beg)
        buf = self.data[off:off + (end - beg)]
        out, i = [], 0
        while i < len(buf) - 6:
            if buf[i] in (0x48, 0x4C) and buf[i + 1] in (0x8B, 0x8D) and buf[i + 2] in self._MODRM:
                disp = struct.unpack_from("<i", buf, i + 3)[0]
                out.append((beg + i, beg + i + 7 + disp))
                i += 7
            else:
                i += 1
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["strings", "methods", "refs", "disasm"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pyd", default=str(DEFAULT_PYD))
    ap.add_argument("--base", default=None, help="문자열 전역 배열 베이스 RVA (기본: 자동 적합)")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = Pyd(Path(a.pyd))
    print(f"# {p.path.name}  ImageBase=0x{p.image_base:x}  문자열 {len(p.strings)}개 "
          f"(블롭 0x{p.blob_off:x}, 길이배열 0x{p.len_off:x})" if p.strings else "# 문자열 테이블 미복원")

    if a.cmd == "strings":
        for i, s in enumerate(p.strings):
            print(f"[{i:>3}] {s!r}")
        return 0

    if a.cmd == "methods":
        for base, nm, rva, fl, doc in p.method_defs():
            print(f"0x{base:06x}  {nm:<26} RVA 0x{rva:06x} flags=0x{fl:x}  {doc!r}")
        return 0

    beg, end = int(a.args[0], 16), int(a.args[1], 16)
    base = int(a.base, 16) if a.base else 0x45e08  # main_window.pyd 실측값
    if a.cmd == "refs":
        seen = []
        for at, t in p.rip_refs(beg, end):
            if (t - base) % 8 or not (0 <= (t - base) // 8 < len(p.strings)):
                continue
            i = (t - base) // 8
            if i in [x[0] for x in seen]:
                continue
            seen.append((i, at))
            print(f"  0x{at:06x}  str[{i}] = {p.strings[i]!r}")
        return 0

    # disasm
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    except ImportError:
        print("capstone 이 없다. 격리 설치: pip install --target <스크래치>/pylib capstone", file=sys.stderr)
        return 2
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    off = p.rva_to_off(beg)
    for ins in md.disasm(p.data[off:off + (end - beg)], beg):
        note = ""
        if "[rip" in ins.op_str:
            for at, t in p.rip_refs(ins.address, ins.address + ins.size):
                if (t - base) % 8 == 0 and 0 <= (t - base) // 8 < len(p.strings):
                    note = f"    ; str[{(t - base) // 8}] = {p.strings[(t - base) // 8]!r}"
                else:
                    note = f"    ; -> 0x{t:x} ({p.sec_of_rva(t)})"
        print(f"  0x{ins.address:06x}  {ins.mnemonic:<8} {ins.op_str}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
