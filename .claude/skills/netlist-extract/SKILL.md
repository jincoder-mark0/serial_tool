---
name: netlist-extract
description: Persephone 넷리스트에서 모듈을 LEC/cosim용으로 추출하는 방법. extract_module.py의 두 모드, escaped identifier 규칙, 산출물 위치.
---

# 넷리스트 모듈 추출 (extract_module.py)

원본 넷리스트 `Persephone_v200_design_netlist.v`는 **읽기 전용 진실의 원천**이다. 절대 수정 금지.
모든 도구는 `db/netlist_db.json`(파서 산출물)을 통해 넷리스트를 본다. DB가 없거나 넷리스트 sha가 바뀌면 먼저 재생성:

```powershell
python tools\netlist_db.py Persephone_v200_design_netlist.v -o db\netlist_db.json
```
(census 하드체크 19종 + 왕복 selftest가 자동 실행됨. 실패 시 진행 금지.)

## 모드 1: LEC용 gold (--mode lec)
```powershell
python tools\extract_module.py --module <MOD> --mode lec
```
- `verify\lec\extracted\<MOD>_gold.v` — 모듈 넷리스트. renamed port(내부명≠외부명, 예: VTGamma의 ADRS_19_sp_1, 톱의 TEST)가 **없으면** 원문 그대로 슬라이스, **있으면** DB 재방출(외부 포트명 + 브리지 assign — yosys가 named-port 헤더 문법을 파싱 못 하기 때문).
- `verify\lec\blackboxes\<MOD>_stubs.v` — 자식 사용자 모듈 + 직접 인스턴스된 RAMB36E1/DSP48E1/ODDR의 `(* blackbox *)` 스텁. LEC 양쪽이 같은 스텁을 읽는다.
- `--no-dsp-stub`: DSP48E1 스텁 생략 (mul_add LEC에서 cells_sim의 실제 DSP 모델을 전개할 때 사용; run_lec.py --elab-dsp가 자동 전달).

## 모드 2: cosim용 gold 서브트리 (--mode cosim)
```powershell
python tools\extract_module.py --module <MOD> --mode cosim
```
- `verify\cosim\gen\<MOD>_gold.v` — 대상 모듈 + 전체 서브트리(blk_mem_gen 내부까지)를 DB에서 재방출, **모든 모듈명에 `_GOLD` 접미사** (게이트 쪽과 이름 충돌 방지). 프리미티브 참조는 개명하지 않음 — 시뮬레이션 시 Vivado unisims로 해석.

## escaped identifier 규칙 (모든 도구 공통)
- `\`로 시작, **첫 공백에서 끝남** — 방출 시 뒤 공백 필수: `\PE_dd_reg[1][0]_RegpSet_PE_reg_c ` 
- 도구 내부/DB에는 백슬래시 없이 저장, 방출은 반드시 `tools/vutil.py`의 `emit_id()` 사용 (자체 문자열 조립 금지 — 연결 포트명도 emit_id 필요).
- 이 규칙 위반이 과거 버그 클래스였다: 자식 인스턴스 연결에서 `.\PE_reg[6] (` 가 `.PE_reg[6](`로 방출되어 구문 오류.

## 도구 절대경로
- python: PATH의 `python` (3.11)
- 저장소 루트: `e:\FPGA\Persephone_v200`
