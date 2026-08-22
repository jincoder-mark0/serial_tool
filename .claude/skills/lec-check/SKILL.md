---
name: lec-check
description: yosys 형식 등가검증(LEC) 실행법 — run_lec.py 명령, 블랙박스 evert 방식, mul_add DSP 예외, 미증명 포인트 트리아지, WSL 폴백.
---

# 형식 등가검증 (LEC)

한 모듈:
```powershell
python verify\lec\run_lec.py --module <MOD>                       # gate = rtl_gen\<MOD>.v
python verify\lec\run_lec.py --module <MOD> --gate rtl\<MOD>.v    # Stage 2
python verify\lec\run_lec.py --module <MOD> --keep-going          # 미증명 전체 목록
```
전체 배치 (규칙 변경 후 필수):
```powershell
python verify\lec\run_all.py                    # 29모듈, 약 3분, 요약표 출력
python verify\lec\run_all.py --gate-dir rtl     # Stage 2 전체
```
종료코드 0 = 증명 완료. 로그: `verify\logs\<MOD>_lec_<시각>.log`.

## 플로우 내부 (이해용)
1. gold(넷리스트) + stubs + yosys `+/xilinx/cells_sim.v`(-nooverwrite) → proc/flatten/**async2sync**(비동기 FF의 SAT 지원) → **expose -evert t:자식타입들**(블랙박스 자식 제거+포트 승격: 입력=비교 출력, 출력=공유 자유 입력 — 블랙박스 통과 피드백 루프를 건전하게 절단) 
2. gate(RTL)도 동일 처리
3. `equiv_make → equiv_simple -seq 10 → equiv_induct -seq 20 → equiv_status -assert`

## 알려진 특례
- **mul_add_operation/_1**: gate에 DSP 인스턴스가 없으므로 `--elab-dsp` 필수 (gold 쪽 DSP를 cells_sim 모델로 전개; run_all.py는 자동). 현재 양쪽 모두 증명 성공.
- **Mem_\***: LEC 대상 아님 — 행위 모델은 cosim + `mem_extract --check`로 증명 (memory-models 스킬).
- **LEC은 FF 초기값을 증명하지 않는다** → 반드시 `check_inits.py` + t=0부터의 cosim과 함께 사용 (module-done 스킬의 체크리스트).

## 미증명 포인트 트리아지
1. `--keep-going`으로 전체 목록 확보. `equiv_status`의 `Unproven $equiv ... \<wire>_gold \<wire>_gate` 와이어명이 단서.
2. 미증명 와이어를 구동하는 넷리스트 셀을 찾아(`grep`) rtl_gen의 대응 코드와 비트 단위 대조.
3. 소수(<5)이고 피드백 루프 주변이면 증명 깊이 문제일 수 있음 — 스크래치에서 seq를 20/40으로 올려 실험 (RegpSet이 이 사례: REGP 피드백 루프, seq 10/20으로 해결).
4. 대량이면 디컴파일 규칙 버그 — mechanical-decompile 스킬의 정책(전체 재생성+재검증) 적용.
5. 최후 폴백: WSL2 Ubuntu-20.04에 OSS CAD Suite linux-x64 설치 후 sby/eqy 미터 (eqy Windows CRLF 버그 issue #207 주의).

## Stage 2 주의
리팩토링은 내부 넷 이름을 바꾸므로 equiv_make의 이름 매칭이 줄어 증명이 느려질 수 있다. **작은 단위로 커밋하고 매 커밋마다 LEC 재실행** — 미증명 콘이 방금 바꾼 코드로 국소화된다.

## nets 단계(포트 아님) 개명 시 LEC 미증명 — 국소 vs 광범위 트리아지 (26-08-13, 2건 재현으로 규칙화)
포트를 전혀 건드리지 않아도(순수 `nets` 리네임만) equiv_make의 이름 기반 자동 앵커(find_same_wires)가 끊겨 미증명이 날 수 있다 (SyncDetect_v101: 24개, VExtend_v101: 4개 — 둘 다 확정 해결됨; RegWriteback_v101: 22개 — 미해결/스킵).
1. `--keep-going` 로그에서 미증명 셀 개수와 **논리적 국소성**을 먼저 판정한다.
2. **국소 패턴(해결 가능, 실측 2건)**: 미증명 셀이 소수(문서화 범위 4~24개)이고 전부 하나의 대칭 비교기/콤비네이터 idiom에 국한(예: `*_OK_i_N`, `new*_i_N` 같은 LUT+체인 콘 — 흔히 refactor-rules 카탈로그의 "펄스/비교기 템플릿"과 겹침). 이 경우 그 콘의 유일한 renamed 팬인을 찾는다 — 전형적으로 이름에 `_n_0_`, `__N`, 또는 collision 접미사(`_2` 등)가 붙은 "FF Q 출력 트레일링 사본 와이어"(디컴파일이 만든 번들/사본 넷, 실질 FF 자체가 아님)다. `grep`으로 rtl_gen에서 해당 넷의 `assign`/`wire` 선언을 확인해 이 가설을 검증한 뒤, naming\<MOD>.json의 `_review`에 사유를 적고 그 넷들만 `nets`에서 제거(원본 escaped 이름 유지) → 재적용 → 재게이트. 두 사례 모두 이 방식으로 unproven → 0.
3. **광범위 패턴(표적 제외로 해결 안 됨, 실측 1건)**: 미증명 셀이 많고(20개 이상) 서로 다른 논리섬(상태머신 여러 개, 출력 포트 여러 개)에 걸쳐 있으면 — 개명 밀도 자체가 원인일 가능성이 높아 소규모 map 편집으로 국소화되지 않는다(RegWriteback_v101 실측: seq를 30/60으로 올려도 무변화, 즉 깊이 문제 아님을 확인 후에도 미해결). 이 경우 표준 실패 프로토콜(해당 파일 `git checkout`, naming 맵 폐기, mistakes.md 기록, 모듈 스킵)을 따른다 — 과도한 개별 디버깅에 시간을 쓰지 않는다.
4. 두 갈래 모두 **baseline(무개명 rtl_gen) 자체가 완전 증명됨을 먼저 재확인**해 두면(대개 이미 알려진 상태) 원인이 디컴파일 버그가 아니라 리네임임을 빠르게 배제할 수 있다.

## 포트 개명(pass 1 /ports 커밋) 시 LEC 미증명 — 해결됨 (26-08-13)
- 과거 증상: 활성 `ports` 맵 존재 시 SyncRegen/SG_Frame 등에서 미증명 (rename_check·cosim은 PASS).
- **근본 원인 확정**: 구 하네스의 `<MOD>__adapter` 래퍼가 flatten 시 게이트 전 와이어에 `impl.` 접두어를 붙여 equiv_make의 이름 앵커를 붕괴시킴 (SyncRegen 실측: $equiv 116→6개). 깊은 순차 콘(카운터 출력)이 앵커 없이는 미증명.
- **수정**: run_lec.py가 어댑터 대신 `cd <MOD>; rename <new> <old>; cd`로 게이트 포트 와이어만 옛 이름으로 되돌림 — 접두어 오염 없음, 앵커 보존. (yosys `rename`은 활성 모듈 안에서만 평면 이름을 해석한다 — 경로/이스케이프 형식은 "Object not found".)
- 이 패턴으로 실패했다가 스킵된 모듈은 ports 스텝을 재실행하면 된다 (SG_Frame_v101 등). 재발 시에는 진짜 앵커 부족일 수 있으니 표준 트리아지(위)로.

## 도구 절대경로
- yosys: `D:\oss-cad-suite\bin\yosys.exe` (run_lec.py가 PATH에 bin+lib 자동 주입; 수동 실행 시 `$env:PATH="D:\oss-cad-suite\bin;D:\oss-cad-suite\lib;$env:PATH"`)

## [struct] 커밋의 수용 기준 — 절대 규칙 (26-08-13 규칙화)
- **-assert exit 0 그 자체가 기준이다.** '미증명 셀이 있지만 하류 레지스터는 증명됐다'는 방증은 **순환 논증** — equiv_induct는 미증명 $equiv 페어까지 시점 t 가정에 포함하므로, 거짓 페어 가정 위에서 하류가 '증명'될 수 있다 (SG_Checker 실측: depair하자 20셀로 확대).
- 상태 요소(카운터/레지스터 뱅크)의 재명명+벡터화는 FF 페어링을 소실시켜 인접 콘 전체를 쌍별 증명 불가로 만들 수 있다 ('wide counter vectorization' 클래스: SyncRegen·SG_Checker 실측). 이런 조각은 기계형 유지 + module_notes 문서화가 정답.
- 구조 복원 후 의미가 달라진 동명 중간 와이어는 개명으로 거짓 페어링을 끊을 수 있으나, 그 와이어가 **진짜 등가 앵커였다면 개명이 오히려 악화**시킨다 — depair 시도 후 미증명이 늘면 즉시 원복.
