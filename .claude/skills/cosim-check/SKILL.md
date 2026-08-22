---
name: cosim-check
description: 락스텝 co-simulation 실행법 — run_cosim.py 명령, 티어별 시드/사이클 기준, X 정책, directed 스텀리스 훅, 불일치 트리아지.
---

# 락스텝 Co-simulation

한 모듈 (gold=넷리스트+unisim, gate=RTL, 모든 출력 매 클럭 negedge 비교):
```powershell
python verify\cosim\run_cosim.py --module <MOD>                          # rtl_gen, 시드 1 2 3, 200k
python verify\cosim\run_cosim.py --module <MOD> --stage rtl --seeds 1 2 3 --cycles 1000000
```
전체 배치:
```powershell
python verify\cosim\run_all.py --seeds 1 2 --cycles 100000    # 스모크
```
PASS 기준: 모든 시드에서 `COSIM PASS` + 종료코드 0. 로그: `verify\logs\<MOD>_cosim_<stage>_<시각>.log`.

## 공식 게이트 기준 (Task 완료 조건)
| 티어 | 사이클 | 시드 |
|---|---|---|
| T0/T1 (Cursor, SG_Raster, ColorMatrixSwap, OffsetGain, Mute) | 200,000 | {1,2,3} |
| T2 (VideoSwitch쌍, SG_Frame/Checker/ComSync/Top, mul_add쌍, HCK_Pol, SyncRegen, VTGamma, DataInv, RegpSet) | 500,000 | {1,2,3} |
| T3 (ExtraArea, RegWriteback, VExtend, SG_Line/StairStep, DACctrl, H_Flip, 톱) | 1,000,000 | {1,2,3} |
| T4 (SyncDetect, Imager, RegisterFile) | 2,000,000 | {1,2,3} |
| Mem_* 7종 | 500,000 | {1,2,3} |

## TB 구조 (gen_tb.py 자동 생성 — 직접 수정 금지, 생성기를 고칠 것)
- 클럭: PCLK=8ns, HCLK=14ns, CCK_CLK=22ns, SFT_CLK=34ns, HCK_IN=38ns, clka=8ns, clkb=14ns — 짝수 주기 + **서브-ns 위상 오프셋 {0.0/0.23/0.41/0.63/0.81}**. 제약: 오프셋들, 오프셋+0.1(=**unisim FF의 100ps Q 수송 지연** 통과 후 gold 출력 변화 시각), 비교 스트로브(오프셋+0.15)가 전부 서로소. 과거 {.3/.5/.7/.9}는 .9+.1=.0이 PCLK 엣지와 겹쳐 gold만 레이스 → HCK_Polarity/Imager 산발 불일치의 원인이었음.
- 비교 스트로브는 각 negedge **+0.15ns** (네그에지 FF 갱신과의 동시성 제거).
- **Mem_\* 전용 위상 교대 스텀리스**: unisim RAMB 충돌 윈도우는 최대 3ns라 랜덤 양포트 동시 접근은 반드시 충돌 X 유발 → 한 시점 한 포트만 활성(유휴 포트는 주소 0에 파킹, 아무도 0에 쓰지 않음), 위상 사이 20ns 정지 갭. 교차 포트 데이터 흐름은 위상 간에 검증됨.
- 데이터 입력: 홀수 ns 시각에만 랜덤 갱신 (엣지 레이스 원천 차단). `+seed=<n> +cycles=<n>` 플러스아그.
- 리셋: R0*(액티브 하이)/RSTn*(액티브 로우) 이름 규약으로 자동 처리 — t=0~501 어서트, 이후 시드 기반 3회 중간 펄스.
- glbl GSR가 100ns에 해제 → unisim FF가 INIT로 초기화 = RTL initial과 일치. 비교는 t=601부터.
- **X 정책**: `!==` 비교 — X===X는 일치(정상), X vs 확정값은 즉시 실패. 불일치 20개 초과 시 조기 종료.

## directed 스텀리스 훅
`verify\cosim\directed\<MOD>.vh`가 **TB 생성 시점에** 존재하면 TB 하단에 `include`됨. TB의 reg를 계층 참조로 구동하는 initial 블록을 넣을 수 있다 (예: SG_* pattern_sel 시퀀스, mul_add 2^20 전수 스윕, H_Flip HS/VS 프레임 타이밍). 파일 추가 후 run_cosim을 다시 실행하면 자동 반영.

**directed 훅이 있는 모듈은 반드시 `--root .`를 repo 루트에서 붙여 실행할 것** (mul_add_operation·H_Flip_v101 2건 재현, 규칙화됨 26-08-13): `gen_tb.py`가 기본으로 `root.resolve()`(항상 절대경로) 기준 `` `include "<절대경로>/<MOD>.vh"`` 를 TB에 박아 넣는데, 이 환경의 `D:\iverilog\bin\iverilog.exe`(Icarus 12.0 devel)는 드라이브 문자 절대경로(`E:/...`, `E:\...` 둘 다)의 `` `include`` 를 예외 없이 못 찾는다(파일은 실제 존재 — 최소 재현으로 확인된 iverilog 자체의 한계, 상대경로/`-I` 탐색은 정상 동작). `verify\` 하네스는 불가촉이므로, `gen_tb.py`/`run_cosim.py` 둘 다 지원하는 기존 `--root` 플래그에 절대경로 대신 `.`(상대경로)를 넘겨 우회한다:
```powershell
python verify\cosim\gen_tb.py --module <MOD> --root .
python verify\cosim\run_cosim.py --module <MOD> --stage rtl --seeds 1 2 3 --cycles <N> --root .
```
directed 훅이 없는 모듈은 영향 없음(기본 `--root` 생략 그대로 사용).

## 불일치 트리아지
1. 로그의 첫 MISMATCH가 근원: `t=... clk=... port=... gold=... gate=...`.
2. t<1000이면 초기화 문제 (check_inits, glbl, initial 누락).
3. 리셋 펄스 직후면 비동기 리셋 경로/게이트 리셋 전파.
4. 특정 포트만이면 그 출력의 콘을 LEC 미증명 목록과 대조 (LEC이 통과했다면 블랙박스 경계 의미론 차이 — 대개 Mem_* 모델 레이턴시/WRITE_FIRST/enb 게이팅).
5. 파형 필요 시 gen_tb.py에 $dumpfile 추가 개조 후 GTKWave(`D:\oss-cad-suite\bin\gtkwave.exe`).

## 도구 절대경로
- iverilog/vvp: `D:\iverilog\bin\iverilog.exe`, `D:\iverilog\bin\vvp.exe`
- unisims: `D:\Xilinx\Vivado\2019.2\data\verilog\src\unisims` + `...\glbl.v` (run_cosim.py가 자동 포함)
