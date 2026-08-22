# S-026 — 최소 창 크기 완화 (목표: 폭 ≤1280, 높이 ≤730)

- Status: TODO (2026-08-22 상위 설계 확정 — 하위 수행 가능)
- Recommended model: **하위(Sonnet) 가능** (확정 설계 기준 — 벗어나면 중단·보고)
- 선행: S-019, S-024, S-025 (완료됨)
- Skills to load: task-done

## 목적 (Why)

실측(`tools/ux_capture.py` + min_size_probe): MainWindow `minimumSizeHint`가
**ko 1471×786 / en 1427×786** — 1366×768 노트북(작업표시줄 감안 가용 ≈1366×728)에
창이 들어가지 않는다. 시리얼 도구는 현장 노트북 사용이 잦아 실사용 차단 결함.

## 실측 근거 (2026-08-22 위젯 트리 계측, ko)

창 1471 ≈ 좌측 857 + 우측 598 + 스플리터/여백. 지배 요인:

| 위젯 | mshW | 비고 |
|---|---|---|
| `DataLogWidget` 툴바 | **851** | 좌측 지배 — 제목+체크박스 5+콤보+검색+버튼 4가 한 줄 |
| `PortSettingsWidget` 시리얼 행 | 687 | DataLog 해소 후의 좌측 지배자 (이번엔 유지) |
| `MacroControlWidget` 실행 그룹 | **592** | 우측 지배 — 2행 그리드 |
| ManualControl 551 / SystemLog 394 / StatusBar 585 | — | 문제없음 |

높이 786 = 좌측 열 합(PortTabPanel 412 + ManualControl 183 + SystemLog 106 + 간격) + 메뉴/상태바.

## 확정 설계 (이대로 구현)

1. **DataLog 툴바 2행화** (`view/widgets/data_log.py` — 851 → 목표 ≤550):
   - 1행: 제목 + `addStretch()` + 옵션들(TX 브로드캐스트 체크+입력, 필터, 뉴라인 콤보, HEX, 타임스탬프, 일시 정지)
   - 2행: 검색창 + 이전/다음 버튼 + `addStretch()` + 지우기 + 저장(로깅 토글)
   - 검색창에 `setMinimumWidth(120)` 부여 — 공간이 생기므로 35px 압착 문제(S-019 후속 발견)도 함께 해소.
   - SystemLogWidget 툴바는 손대지 않는다 (394 — 문제없음. S-025의 stretch 규칙만 유지).
2. **MacroControl 실행 그룹 3행화** (`view/widgets/macro_control.py` — 592 → 목표 ≤420):
   - 1행: 간격(ms) 라벨+입력 + 반복 라벨+스핀 + 브로드캐스트 체크
   - 2행: 저장 + 불러오기 (+stretch)
   - 3행: 반복 시작 + 반복 중지 + 반복 일시정지 + 진행 카운터
   - 그룹 `setMinimumHeight(100)`(S-024에서 완화됨)은 그대로 — 행이 늘어난 만큼 sizeHint가 자연 확장.
   - 우측 열은 세로 여유가 크다(249/715) — 높이 증가 무해.
3. **높이 완화** (786 → 목표 ≤730):
   - `view/widgets/system_log.py` `setMinimumHeight(100)` → `60` (내용은 스크롤 — 시스템 로그는
     보조 정보라 최소 2~3줄이면 충분. 기본 크기에서는 레이아웃이 그대로 유지됨을 캡처로 확인).
   - `view/widgets/manual_control.py`의 다중행 입력(command_edit)의 최소 높이를 확인해
     2줄 수준(폰트 메트릭 기반)으로 하한 완화 — 현재 값이 이미 그 이하면 건드리지 않는다.
   - DataLog 2행화로 +약 28px가 상쇄되는지 실측으로 확인 — 목표 미달이면 **더 줄이려 하지 말고**
     최종 실측치를 보고 (PortStats 재배치 등 추가 축약은 상위 재설계 대상).
4. 레이아웃 여백·간격은 `LAYOUT_*` 상수만 사용 (ui_guide §2). 새 행 구성 시 기존 시그널
   연결·retranslate·get_state/apply_state는 전부 보존 — 위젯 재배치만, 생성 로직 불변.

## Steps

1. 수정 전 실측 기록: `.venv\Scripts\python tools\ux_capture.py --theme dark --lang ko --out <스크래치패드>\s026_before` (minimumSizeHint 출력 보관).
2. 설계 1→2→3 순으로 구현, 각 단계 후 캡처로 minimumSizeHint 변화를 기록한다 (표로 보고).
3. 전체 검증: pytest(offscreen, 기준선 122 — `tests/test_ui_guidelines.py` 포함),
   캡처 8조합(dark/light × ko/en — en 폭도 함께 확인), 육안 판정(잘림·겹침·검색창 폭 회귀).
4. **캡처 후 `git checkout -- resources/configs/settings.json`**.
5. `.agent/rules/ui_guide.md` §4의 실측치와 `tasks/S-026` 이 파일의 결과 기록 갱신은 상위가 수행 — 하위는 보고만.

## Acceptance criteria (DoD)

- [ ] minimumSizeHint **폭 ≤1280 (ko/en 모두)**. 높이 ≤730 또는 최종 실측치+미달 사유 보고.
- [ ] 검색창 최소 폭 120 확보 (35px 압착 해소 — 캡처 육안 확인).
- [ ] 기존 시그널·상태 저장·retranslate 전부 동작 (전체 pytest 122 통과).
- [ ] 캡처 8조합 잘림·겹침 0건.
