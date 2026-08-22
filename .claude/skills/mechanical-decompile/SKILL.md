---
name: mechanical-decompile
description: 기계적 디컴파일러(decompile.py) 사용·수정법과 1단계 LEC/cosim 실패 디버그 레시피. 규칙 변경 시 전 모듈 재생성+전 LEC 재실행 정책.
---

# 기계적 디컴파일 (Stage 1)

```powershell
python tools\decompile.py --module <MOD>     # 한 모듈
python tools\decompile.py --all              # Mem_*/blk_mem_gen_* 제외 29모듈 전부
```
출력: `rtl_gen\<MOD>.v` — **기계 생성물, 손으로 편집 금지** (헤더에 명시됨). 가독성 개선은 Stage 2에서 `rtl\`에만.

## 변환 규칙 요약 (전체 원문: docs/decompile_rules.md 및 decompile.py 헤더)
| 프리미티브 | 규칙 |
|---|---|
| LUT1~6 | `localparam LUTINIT_x; assign O = LUTINIT_x[{I(N-1),...,I0}];` — I0가 인덱스 LSB. LUT1은 INIT값별 직역(~I0/I0/상수) |
| FDCE/FDPE | `initial r=INIT; always @(posedge C or posedge CLR/PRE) ...` — CLR→0, PRE→1. **IS_C_INVERTED=1이면 negedge** (HCK_Polarity의 FDCE 5개!) |
| FDRE/FDSE | 동기 R→0/S→1. R/S가 상수0로 묶이면 순수 DFF |
| CARRY4 | unisim 직역: `chain[0]=CI|CYINIT; O[i]=S[i]^chain[i]; CO[i]=S[i]?chain[i]:DI[i]` — `+` 복원은 Stage 2 |
| SRL16E | 16비트 시프트 reg + 상수 인덱스 탭. srl_name 속성은 주석 보존. RTL 딜레이 = A+1, 대부분 트레일링 FF 별도 존재 |
| MUXF7/8 | 삼항 연산자 |
| GND/VCC | 셀 삭제 + `1'b0/1'b1` 상수 전파. 톱 TEST 포트는 `assign TEST=1'b0;` (const 네트 별칭 금지) |
| ODDR | 프리미티브 인스턴스 그대로 (IS_D2_INVERTED=1 포함) — cosim 시 unisims로 해석 |
| DSP48E1 | 가드된 변환(속성·상수 포트 전부 assert 후): `P <= sext48($signed(A[24:0])*$signed(B[17:0]))` @PCLK, CEP 게이트 |
| RAMB36E1 | 도달 시 에러 — Mem_* 래퍼는 rtl_gen\Mem_*.v (행위 모델, memory-models 스킬 참조) |
| FF Q 타겟 | 전체 스칼라 넷 구동 → 그 넷을 reg로 승격. 벡터 비트 구동 → 인스턴스명 reg + 브리지 assign |
| renamed port | 헤더는 외부명만 + 내부 네트 브리지 assign (yosys가 named-port 헤더 미지원) |

## 정책: 규칙 변경 = 전체 무효화
디컴파일러 규칙을 하나라도 수정하면:
1. `python tools\decompile.py --all` (전 모듈 재생성)
2. `python verify\lec\run_all.py` (전 모듈 LEC 재실행 — 빠름, 이름 매칭 덕분에 총 ~3분)
3. 이전에 통과했던 cosim도 해당 규칙 영향권이면 재실행

## 실패 모드 디버그 레시피
- **yosys "module not found"** → 스텁 누락. run_lec.py가 자동 재추출하므로 보통 extract_module 버그. escaped 이름 방출(뒤 공백) 확인.
- **LEC 미증명 포인트 소수** → 특정 프리미티브 규칙 버그. `--keep-going`으로 전체 목록 확인 → `equiv_status` 목록의 와이어명 → 넷리스트에서 그 셀 역추적 → 규칙 수정 → 전체 재생성. 실례: `wire [7:6]` 같은 비-0 LSB 벡터의 whole-net 콘캣 전개 버그.
- **LEC "No SAT model for cell X"** → 블랙박스가 evert 안 됨. run_lec.py의 bb_types 계산 확인.
- **LEC 미증명이 피드백 루프 주변** → 증명 깊이 부족. 현재 기본 seq 10/20으로 대부분 해결. 안 되면 WSL2 Ubuntu-20.04의 sby/eqy 폴백 (eqy Windows CRLF 버그 issue #207 — LF 강제 또는 bin/eqy-script.py에 newline="\n" 1줄 패치).
- **cosim 초반 X 불일치** → RTL initial 누락(check_inits로 확인) 또는 iverilog에 glbl 미포함(-s glbl + glbl.v).
- **cosim 리셋 부근 불일치** → FF 템플릿의 CLR/CE 우선순위, 또는 SG 계열 게이트 리셋(regfile_body[56][16..18], RSTn0x) 오전파.
- **SRL 오프바이원** → 넷리스트 SRL 깊이 A+1 + 트레일링 FF는 별개 유지 (Stage 1에서 병합 금지).

## 도구 절대경로
- yosys: `D:\oss-cad-suite\bin\yosys.exe` (PATH에 `D:\oss-cad-suite\bin;D:\oss-cad-suite\lib` 주입 필요 — run_lec.py가 자동 처리)
- iverilog/vvp: `D:\iverilog\bin\`
- unisims: `D:\Xilinx\Vivado\2019.2\data\verilog\src\unisims`, glbl: 같은 경로 상위의 `glbl.v`
