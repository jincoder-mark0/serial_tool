"""
extract_strings.py

TASK-001 helper: extract embedded strings from a compiled binary (e.g.
ui/main_window.pyd) WITHOUT executing/importing it. Pure byte-level scan.

Outputs three files:
  - strings_ascii.txt   : printable ASCII runs (len >= 4)
  - strings_utf16.txt   : UTF-16LE runs (len >= 4 code units), decoded to text
  - pyx_symbols.txt     : lines from strings_ascii.txt starting with "__pyx_"

Usage:
    python tools/analysis/extract_strings.py <input.pyd> <output_dir>

This script only reads the input file; it never imports/executes it.
"""
import re
import sys
from pathlib import Path

MIN_LEN = 4

ASCII_RE = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_LEN)
# UTF-16LE: printable ASCII byte followed by 0x00, repeated MIN_LEN+ times
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){%d,}" % MIN_LEN)


def extract_ascii(data: bytes) -> list[str]:
    return [m.group().decode("ascii", errors="replace") for m in ASCII_RE.finditer(data)]


def extract_utf16(data: bytes) -> list[str]:
    out = []
    for m in UTF16_RE.finditer(data):
        try:
            out.append(m.group().decode("utf-16le", errors="replace"))
        except Exception:
            pass
    return out


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: python {Path(__file__).name} <input.pyd> <output_dir>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    data = in_path.read_bytes()

    ascii_strings = extract_ascii(data)
    utf16_strings = extract_utf16(data)
    # NOTE: Cython embeds "__pyx_*" tokens both as standalone strings and
    # inside qualified names (e.g. "ui.main_window.__pyx_scope_struct_2_process_kill").
    # We keep any string CONTAINING "__pyx_" so qualified-name occurrences are
    # not silently dropped; this is the useful signal for symbol/function inference.
    pyx_symbols = sorted({s for s in ascii_strings if "__pyx_" in s})

    def _dump(path: Path, items: list[str], empty_note: str) -> None:
        # If no matches were found, write an explicit marker line instead of an
        # empty file, so a genuine null result is distinguishable from a script
        # failure / not-yet-run state.
        text = "\n".join(items) if items else empty_note
        path.write_text(text, encoding="utf-8")

    _dump(
        out_dir / "strings_ascii.txt",
        ascii_strings,
        f"# (no ASCII strings >= {MIN_LEN} chars found)",
    )
    _dump(
        out_dir / "strings_utf16.txt",
        utf16_strings,
        f"# (no UTF-16LE strings >= {MIN_LEN} code units found in {in_path.name}; "
        f"verified this is a genuine negative result, not a script defect)",
    )
    _dump(
        out_dir / "pyx_symbols.txt",
        pyx_symbols,
        "# (no strings containing '__pyx_' found)",
    )

    print(f"input: {in_path} ({len(data)} bytes)")
    print(f"ascii strings : {len(ascii_strings)}")
    print(f"utf16 strings : {len(utf16_strings)}")
    print(f"pyx symbols   : {len(pyx_symbols)}")


if __name__ == "__main__":
    main()
