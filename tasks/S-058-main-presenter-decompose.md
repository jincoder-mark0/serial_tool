# S-058 — MainPresenter 분해

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능** (분해 후보 확정 — 벗어나면 중단·보고)
- 선행: S-055 커밋 후 (같은 파일)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-7(감사② 지적)

## 목적 (Why)

감사② 진단: `presenter/main_presenter.py`가 이미 `lifecycle_manager`/`event_router`/
`data_handler`로 일부 위임하고 있어 설계 자체는 양호하나, 그럼에도 한 클래스가 5~6개의
서로 다른 관심사를 갖는다:

1. 설정 DTO 조립·해체(60여 필드 매핑, **두 곳**에 나뉘어 있어 스키마가 바뀌면 양쪽을 고쳐야 함)
2. 종료 시 상태 수집·저장(DTO를 손으로 dict로 풀어 병합)
3. 포트/매크로 이벤트 UI 동기화
4. 매크로 송신 라우팅
5. 로깅 시작/중지 시 확장자→포맷 결정
6. (S-052 이후) 시스템 로그 로깅 배선

특히 **5번(확장자→`LogFormat` 매핑)은 순수 로직인데 Presenter에 있어 테스트하려면 QWidget
스택 전체가 필요하다**.

## 확정 설계 (감사② 후보 채택)

우선순위 순 — 시간이 부족하면 위에서부터:

1. **`LoggingFormatResolver`**(또는 함수) — 확장자→`LogFormat` 결정 로직을 순수 함수로 추출.
   Qt 없이 단위 테스트 가능해야 한다. 가장 쉽고 이득이 명확한 첫 조각.
2. **`PreferencesCoordinator`** — 설정 DTO 조립(1)과 적용을 한 곳으로 모은다. 현재
   **두 곳에 흩어진 필드 매핑을 하나로** 합치는 것이 목적이다(스키마 변경 시 한 곳만 고침).
3. **`ShutdownStateCollector`** — 종료 시 상태 수집·저장(2). DTO→dict 수동 변환이 몰려 있는
   곳이라 실수가 나기 쉽다.

**절대 조건**:
- `MainPresenter`의 공개 API와 시그널 배선은 **불변**. `main.py`가 `MainPresenter(window)`로
  생성하고 View가 이를 통해 동작한다.
- **설정 저장 키 문자열 불변** — 사용자 설정 호환.
- 추출한 클래스가 View를 직접 만지지 않는다(기존처럼 Presenter를 통하거나 주입받는다).

## 검증 방법

- 기존 테스트(`tests/test_presenter_init.py`, `test_integration_refactored.py`,
  `test_presenter_manual_control.py` 등)가 **수정 없이 통과**해야 한다. 고쳐야 통과한다면
  계약이 깨진 것이므로 중단·보고(S-053/S-054와 같은 안전 판정).
- 추출한 순수 로직에 단위 테스트 신규(특히 1번은 Qt 없이).
- **설정 왕복 검증**: 앱을 캡처로 1회 띄운 뒤 `settings.local.json`의 키 구성이 이전과
  같은지 확인(키가 사라지거나 추가되면 안 된다).
- 전체 pytest(offscreen) 2회 연속 + ruff 클린.

## Acceptance criteria (DoD)

- [ ] 최소 1번(포맷 결정)은 추출되고 Qt 없이 테스트된다.
- [ ] 기존 테스트 무수정 통과, 공개 API·저장 키 불변.
- [ ] 어디까지 분해했는지(1~3 중) 보고.
- [ ] 전체 pytest 통과.
