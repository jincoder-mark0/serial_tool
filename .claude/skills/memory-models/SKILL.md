---
name: memory-models
description: Mem_* 행위 모델(bram_tdp_model/bram_sdp_model) 사양 — 2클럭 레이턴시, WRITE_FIRST, 바이트 쓰기, enb 게이팅, .mem 파일 검증(mem_extract --check), HFLIP 레인맵.
---

# Mem_* 행위 메모리 모델

7개 동결 래퍼(`rtl_gen\Mem_*.v`)가 공유 코어 2종(`rtl_gen\lib\bram_tdp_model.v`)을 인스턴스:

| 래퍼 | 코어 | 구성 | INIT (.mem) |
|---|---|---|---|
| Mem_DAC_M / Mem_DAC_P | bram_tdp_model | 512×32, we 1비트 | mem_init\Mem_DAC_M.mem / _P.mem (서로 다름) |
| Mem_Gamma / Mem_Gamma__1 | bram_tdp_model | 512×32, we 1비트 | 바이트 동일 쌍 (유니티 감마 램프) |
| Mem_Register | bram_tdp_model NBYTES=4 | 64×32 **바이트 쓰기** wea[3:0] | 레지스터 파워온 기본값 (docs/registers.md) |
| Mem_HFLIP / Mem_HFLIP__1 | bram_sdp_model | 1024×20 SDP | 없음 (0으로 파워업) |

## 재현된 의미론 (넷리스트 실측 근거)
- **읽기 레이턴시 2클럭**: ①RAMB36E1 동기 읽기 레지스터 ②blk_mem_gen_generic_cstr가 추가한 패브릭 FDRE단 (DOA/DOB_REG=0이어도!). 
- **WRITE_FIRST** (7개 전부): 같은 포트 쓰기 시 그 포트 읽기 레지스터에 신규 데이터. Mem_Register는 바이트 레인 단위 — 쓰인 레인은 신규, 안 쓰인 레인은 기존 저장값.
- **HFLIP**: 포트A는 쓰기 전용(ENARDEN=wea), 포트B는 읽기 전용이며 **두 레이턴시 단 모두 enb 게이트**.
- 읽기 경로 레지스터·미기록 메모리 내용 모두 **0으로 파워업** (unisim·실리콘과 일치 — X 아님).
- 문서화된 편차: unisim의 교차 포트 동일주소 충돌 X (100ps 윈도우)는 재현하지 않음 — cosim 클럭 위상 오프셋(≥200ps)이 윈도우를 회피하며, 실제 설계는 포트별 다른 클럭/용도로 충돌 없음.

## 검증 (LEC 없음 — 이 두 가지가 게이트)
```powershell
python tools\mem_extract.py --check      # .mem ↔ 넷리스트 INIT_xx 바이트 역검증 (7/7)
python verify\cosim\run_cosim.py --module Mem_Register --seeds 1 2 3 --cycles 500000
```
7개 각각 cosim 3시드×500k. 랜덤 스텀리스가 쓰기/읽기/동시 포트/바이트 워크/enb 게이팅을 커버.

## .mem 재생성/검증
```powershell
python tools\mem_extract.py            # 추출 (Gamma쌍 동일·DAC쌍 상이 assert 포함)
python tools\mem_extract.py --check    # 역검증 — 이것이 "INIT 100% 동일"의 증명
```
- 워드 매핑: `words[8L+i] = int(line_hex[56-8i : 64-8i], 16)` (INIT_00의 최우측 8헥사 = 워드 0).
- INITP는 7개 모두 전부 0 (도구가 assert).
- $readmemh 경로는 **시뮬 작업 디렉터리 기준 상대경로** — run_cosim.py가 cwd=저장소 루트로 고정.

## HFLIP 레인맵 (참고 — 모델에는 불필요)
넷리스트 내부에서 20비트가 바이트 레인당 5비트로 분산: dina[4:0]→DIADI[4:0], [9:5]→[12:8], [14:10]→[20:16], [19:15]→[28:24]. 이 순열은 Mem_HFLIP **경계 안**에만 존재하므로 동결 경계의 행위 모델에는 순열이 없다. `mem_init\manifest.json`에 기록됨.
