---
name: refactor-rules
description: Stage 2 가독성 리팩토링 룰북 — 허용/금지 목록, 복원할 RTL 이디엄 카탈로그, 매 커밋 3중 게이트 재실행 의무.
---

# Stage 2 리팩토링 룰북

대상: `rtl\<MOD>.v` (P2-T20에서 rtl_gen을 복사한 것). **rtl_gen\은 정확성 앵커 — 절대 수정 금지.**

## 매 커밋마다 (예외 없음)
```powershell
python verify\lec\run_lec.py --module <MOD> --gate rtl\<MOD>.v
python tools\check_inits.py --module <MOD> --rtl rtl\<MOD>.v
python verify\cosim\run_cosim.py --module <MOD> --stage rtl --seeds 1 2 3 --cycles <티어 기준>
```
셋 다 exit 0이어야 커밋. 작은 단위로 커밋할수록 LEC 미증명이 방금 바꾼 코드로 국소화된다.

## 허용
- 내부 넷/reg 의미명 개명 — 모듈 헤더 주석에 개명표(원래 넷리스트명 → 새 이름) 유지.
- 비트별 always 블록을 벡터 always로 병합 (의미 동일 조건).
- LUT INIT 인덱싱식 → 복원 연산자 치환: `==`, `!=`, `+`, `-`, 삼항, `case`, and-or 트리. LEC이 치환마다 증명해준다.
- CARRY4 mux/xor 체인 → `+`/비교 연산 복원.
- srl_name 주석 기반 시프트 배열화: `reg [W-1:0] dly [0:N];` — 트레일링 FF를 배열에 접는 것은 FF 멀티셋(check_inits)이 보존될 때만.
- 이디엄 복원 + 주석 (아래 카탈로그), `docs\module_notes\<MOD>.md` 작성.

## 금지 (하나라도 어기면 100% 동일성 논증이 깨진다)
- 포트/모듈/인스턴스 이름·폭 변경 (escaped 이름 포함 — 완전 동결).
- 모듈 경계를 넘는 로직 이동. **RegisterFile에 흡수된 Imager/SG_* 비교기 ~35개 체인은 이동 금지, module_notes에 소유권 문서화만** (넷 이름 `\SG_Line/L_COUNT_01_carry...`가 원 소속의 증거).
- FF 개수/클럭/리셋 종류·극성/INIT 변경, 상태 재인코딩, 파이프라인 단수 변경.
- 명백해 보이는 설계 버그 "수정" — 발견 시 문서화만 (동작 동일성이 목표).
- rtl_gen\ 수정, 넷리스트 원본 수정.

## 이디엄 카탈로그 (이 설계에서 실측된 패턴)
- **리셋해제 동기화기**: FDCE(D=1, CLR=R0) → 릴리즈 1클럭 후 상승 플래그. DACctrl `RSTnDD_reg`(CCK_CLK), 톱 `\sgd_reg[11]_i_7`(PCLK)×2.
- **all-1s 프리셋 카운터**: `if(!rst) cnt <= '1;` — DACctrl cck_hcnt(FDSE 9개, S=~RSTnDD), Imager BlankCnt/hck_hcnt(FDPE).
- **섀도뱅크 프리셋**: SyncDetect save_reg[1] 계열 FDPE 91개 — 첫 프레임 비교가 반드시 불일치하도록 1로 프리셋.
- **CE-freeze**: RegpSet의 `.CE(RSTn)` 10개 — 리셋 중 값 유지.
- **펄스 생성기 템플릿** (Imager ~10회 반복): `if(cnt==REG_x_TIM) sig<=1; else if(cnt==REG_x_TIM+REG_x_WID) sig<=0;` — 하나 해독하면 LATCH/VCK1/VCK2/R2K/K2*/VSW_STT/H_VST 전부 같은 틀.
- **SG 소프트 리셋**: regfile_body[56][16..18] 비트가 SG_Frame/StairStep/Checker·Line·Raster의 비동기 클리어. RSTn0/RSTn02_out/RSTn03_out = RSTn & (pattern_sel==k).
- **SRL+트레일링FF**: 넷리스트 `_srlN` + FDRE = 원본 RTL 딜레이 N+1.
- **네그에지 FF**: HCK_Polarity PIX_check/judge 5개 (IS_C_INVERTED) — 외부 HCK 극성 판별용.

## 네이밍 도구 레시피 (이름 변경은 이 경로만 — RULES.md §4)
```powershell
python tools\gen_rename_map.py --module <MOD>        # 초안 → naming\<MOD>.json
# 검토: FIXME_* 반드시 손으로 명명, 충돌 접미(_2) 확인. 포트는 ports_pending에 생성됨.
python tools\rename_apply.py --module <MOD>          # ① 내부 넷 적용
python tools\rename_check.py --module <MOD>          # 토큰열 no-op 증명 (HEAD 대비)
# 3중 게이트 → 커밋 "TASK-xxx[<MOD>/nets]: ..."
python tools\rename_apply.py --module <MOD> --ports  # ② 포트 + 부모 인스턴스 원자 갱신
                                                     #    (pending→active 승격도 자동)
python tools\rename_check.py --module <MOD>                       # 자기 파일
python tools\rename_check.py --module <MOD> --parent <PARENT>     # 부모 파일별
# 3중 게이트를 <MOD>와 모든 부모에 대해 → 커밋 "TASK-xxx[<MOD>/ports]: ..."
```
- 하네스(run_lec/gen_tb/check_inits/extract 스텁)는 `naming\<MOD>.json`의 **활성 ports를 자동 감지**해 gold(넷리스트 이름)와 브리지 — 별도 플래그 불필요.
- 이미 적용된 맵에 재적용하면 충돌 가드가 막는다(정상). 맵 수정 후 재적용하려면 해당 파일을 git에서 복원 후 진행.
- `$`-시작 식별자·Verilog 키워드는 도구가 거부한다 (과거 `module→module_2` 사고의 가드).
- 의미 네이밍(패스2)도 같은 경로: 맵의 nets/ports_pending에 항목 추가 → apply → check → 게이트.
- **커밋은 `git add`+`git commit` 2단계로 하지 말 것**: 여러 모듈이 병행 세션으로 동시 진행되면 공유 인덱스에 다른 세션의 `git add` 결과가 내 커밋에 섞여 들어가는 사고가 실측됨(add와 commit 사이의 시간차 창). 대신 `git commit <경로...> -m "..."` 단일 호출 사용 — 지정한 경로의 워킹트리 내용만 커밋하고 인덱스에 이미 스테이징된 다른 경로는 그대로 둔다.

## 권장 순서
T0→T1→T2(쌍둥이 VideoSwitch·mul_add는 각 1 Task)→T3→T4. RegisterFile 최후 — 흡수 로직맵 + docs/registers.md(레지스터 기본값·쓰기 디코드·regfile_body 사용처) + HCLK 호스트 버스 프로토콜 서술 의무. **포트 개명은 부모 파일을 수정하므로, 같은 부모를 공유하는 모듈들의 ports 커밋은 동시 진행 금지(직렬화)** — 특히 톱(Persephone_v200)을 부모로 갖는 18개 모듈.

## 패스2(의미 네이밍) 도구 규칙 (26-08-13 갱신)
- 맵 항목의 키는 **파일의 현재 이름**(=패스1 결과)이다. apply가 자동으로 체인을 단일 홉(넷리스트→현재)으로 합성하므로 수동 collapse 불필요.
- 자기 파일 치환은 . 바로 뒤 토큰(자식 인스턴스 포트 참조)을 건드리지 않는다 — 자식과 동명인 자기 포트(Q/D류)도 안전. 단, 어떤 항목의 유일한 출현이 . 뒤뿐이면 "not found"로 거부된다(그 이름은 사실 자식 포트라는 뜻 — 개명 대상 아님).
- [struct] 커밋에서 always 병합 시 **initial 문 누락 주의** — LEC은 초기값을 안 보지만 check_inits가 잡는다 (ColorMatrixSwap 실측).
- **패스2 커밋에서 `rename_check.py`가 이미 pass-1으로 개명된 이름을 재개명할 때 FAIL할 수 있다 — `ports`와 `nets` 섹션 모두 해당 (규칙화됨, 26-08-13, mul_add_operation+VideoSwitch_v101 ports 2건 + SyncDetect_v101 nets 1건 = 동일 원인 3회 재현)**: `rename_apply.py`는 `--ports` 적용 직후 naming JSON의 "ports"를, `--ports` 없는 nets 적용 직후에는 "nets"를 각각 단일홉(netlist-escaped원본→최종이름)으로 자동 collapse하는데, `rename_check.py`의 기본 BEFORE(`git show HEAD`)는 pass-1 결과 파일이라 collapsed 맵의 키와 토큰이 매칭되지 않아 `token ... is not in the map`으로 죽는다. **원인은 naming map이 아니라 rename_check.py 자체의 가정**(collapsed 맵은 LEC 브리지용으로는 맞지만 HEAD-diff 검증에는 안 맞음) — tools\ 불가촉이라 수정 불가. 대응: 게이트 자체(LEC/init/cosim)는 정상 영향 없음(collapsed 맵이 LEC엔 올바름) — rename_check만 별도로, 적용 직전 기억해둔 `{pass1이름: pass2이름}` 매핑(자기 파일은 nets∪pending, 부모는 pending만)으로 `tools/rename_apply.py`의 `span_tokenize`를 재사용하는 스크래치 스크립트를 만들어 git HEAD 대비 순수개명 여부를 직접 증명하고 커밋 메시지에 "rename_check verified via scratch reconstruction (known collapse-vs-HEAD tool gap)"로 명기한다. LEC/init/cosim은 그대로 정식 실행.
