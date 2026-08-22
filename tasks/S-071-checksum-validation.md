# S-071 — 패킷 체크섬 검증

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (알고리즘·배선은 명확, 설계 판단은 아래에 확정해 둠)
- 선행: 없음 (S-072와 함께 하면 시너지가 있으나 독립 수행 가능)
- Skills to load: task-done, lang-keys
- 근거: 사용자 요청 — WireScope 참고 후 "프로토콜 분석 기능"을 확장 (2026-08-23)

## ⚠️ 라이선스 (반드시 읽을 것)

참고 대상인 `reference/wirescope`는 **AGPL-3.0**이다. **코드를 복사하거나 가깝게
옮겨오면 SerialTool 전체가 AGPL 전염 대상이 된다.** 이 태스크는 **기능 개념만
참고해 독자 구현**한다. `reference/` 아래 파일을 열어 로직을 베끼지 마라 —
필요하면 알고리즘 표준 문서(CRC 다항식 정의 등)를 근거로 직접 작성한다.

## 목적 (Why) — 어느 패킷이 깨졌는지 알 수 없다

SerialTool은 패킷 경계를 나눌 수는 있지만(Raw/AT/Delimiter/FixedLength) **체크섬
개념이 전혀 없다**(`grep -rniE "checksum|crc" --include=*.py` 결과 0건, .venv 제외).
프로토콜 디버깅에서 "이 패킷이 유효한가"는 가장 자주 묻는 질문인데, 지금은 사람이
HEX를 눈으로 더해봐야 한다.

패킷 뷰 컬럼도 `Time · Type · HEX · ASCII`뿐이라(`view/panels/packet_panel.py:45`)
검증 결과를 보여줄 자리가 없다.

## 확정 설계

1. **계산은 Core에 둔다.** `core/checksum.py`(신규) — Qt·View 비의존 순수 함수.
   의존성 방향(`View → Presenter → Model → Core ← Common`)상 Model이 쓰기 좋고,
   테스트도 GUI 없이 된다.
2. **1차 알고리즘 범위**: `XOR`, `SUM8`, `SUM16`, `CRC-8`, `CRC-16/MODBUS`,
   `CRC-16/CCITT-FALSE`, `CRC-32`. 각각 **표준 시험 벡터**("123456789" 문자열의
   알려진 체크값)로 테스트를 고정하라 — 자체 계산끼리 비교하는 테스트는 무의미하다.
   그 외(DNP3·Fletcher 등)는 이번 범위 밖. 확장 가능한 구조만 갖춰라.
3. **DTO 확장**: `common/dtos.py`의 패킷 DTO에 검증 결과 필드를 더한다
   (예: `checksum_ok: Optional[bool]` — 검증을 안 했으면 `None`).
   **dict 금지 규칙**(CLAUDE.md)에 따라 반드시 DTO로 전달한다.
4. **설정**: 알고리즘·오프셋·길이·범위(SOF 제외 여부)를 `SettingsManager`로 관리한다.
   `common/constants.py`의 `ConfigKeys`에 키를 등재하고, `core/settings_schema.py`
   스키마와 마이그레이션도 함께 갱신하라 — **S-067에서 테마 enum을 빠뜨려 클래식
   테마가 저장되지 않던 전례가 있다.**
5. **표시**: 패킷 뷰에 검증 결과 컬럼을 추가한다. 색은 QSS 테마 경유(위젯에 색
   리터럴 금지). **4테마 모두에 대칭 적용**하고, `tests/test_qss_contrast.py`가
   요구하는 대비 기준(활성 ≥4.5:1)을 만족시켜라.
6. **UI 문자열은 언어 키 경유** — en/ko 동시 추가 후 `tools/check_language_keys.py` 통과.

## 검증 방법

- 알고리즘별 **표준 시험 벡터** 단위 테스트 (이게 이 태스크의 핵심 검증이다).
- 파서가 나눈 패킷에 검증이 실제로 붙는지 통합 테스트(LOOPBACK 사용, 실기기 불필요).
- 전체 pytest(offscreen, 기준선은 직전 커밋 값) + **ruff 0건** +
  `check_language_keys` + `check_task_boards` 통과.
- 컬럼을 추가했으므로 **네이티브 캡처로 잘림 여부를 육안 확인**하라(RULES §7).
  캡처 후 `settings.json` 무변경 확인. `tools/ux_capture.py --theme <t> --lang <l>`.
- **주의**: 패킷 뷰 컬럼 구성이 바뀌면 우측 패널 최소 폭 근거가 흔들린다
  (S-068, `tests/test_right_section_min_width.py`). 그 테스트가 깨지면 네이티브에서
  요구 폭을 다시 재고 `CONTROL_MIN_WIDTH_RIGHT_SECTION`을 갱신하라.

## Acceptance criteria (DoD)

- [ ] 7종 알고리즘이 표준 시험 벡터로 고정된다.
- [ ] 패킷별 검증 결과가 DTO로 전달되고 뷰에 표시된다.
- [ ] 설정 키가 ConfigKeys·스키마·마이그레이션에 모두 반영된다.
- [ ] 4테마 대비 기준 통과 + 네이티브 캡처 육안 확인.
- [ ] 전체 pytest·ruff·언어 키·보드 검사 통과.
- [ ] `reference/` 코드를 복사하지 않았음을 보고에 명시한다.
