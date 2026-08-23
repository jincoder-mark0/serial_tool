# S-071 — 패킷 체크섬 검증

- Status: DONE (2026-08-23 — 상위 직접 수행. core/checksum.py 신설(7종, 표준 시험
  벡터로 고정), 패킷 뷰 검증 컬럼 추가, 설정 키·기본값 배선. pytest 434 passed, ruff 0건,
  네이티브 캡처 4테마 × 2언어 육안 확인)
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

- [x] 7종 알고리즘이 표준 시험 벡터로 고정된다.
- [x] 패킷별 검증 결과가 DTO로 전달되고 뷰에 표시된다.
- [x] 설정 키가 ConfigKeys·기본값에 반영된다 (packet 블록은 스키마가 느슨해 enum 변경 불필요).
- [~] 네이티브 캡처 4테마×2언어 육안 확인 완료. 색상은 넣지 않아 대비 검사 대상 아님 (아래 "하지 않은 것").
- [x] 전체 pytest·ruff·언어 키·보드 검사 통과.
- [x] `reference/` 코드를 열어 로직을 복사하지 않았다 — CRC 파라미터는 공개된 카탈로그 정의(다항식·init·반사·xorout)와 표준 검사값으로 직접 작성했다.


## 수행 결과 (2026-08-23, 상위 직접)

- **`core/checksum.py`**: XOR·SUM8·SUM16·CRC-8·CRC-16/MODBUS·CRC-16/CCITT-FALSE·CRC-32.
  Qt 비의존 순수 함수. 다항식별 룩업 테이블은 캐시한다.
- **표준 시험 벡터로 고정**(`tests/test_checksum.py`, 31건): `"123456789"`에 대한 공개
  검사값(CRC-8 0xF4 / MODBUS 0x4B37 / CCITT-FALSE 0x29B1 / CRC-32 0xCBF43926)과 대조하고,
  CRC-32는 `zlib.crc32`와도 교차 확인한다. **일부러 init을 0xFFFF→0x0000으로 훼손해
  테스트가 실패하는 것을 확인**했다(`crc16_modbus: 0xBB3D != 0x4B37`).
- **배선**: `PacketViewData.checksum_ok`(Optional[bool]) 추가, `PacketPresenter`가
  설정을 읽어 검증. 오프셋은 음수면 끝에서부터 센다(체크섬은 대개 말미).
  **패킷이 짧으면 "불일치"가 아니라 "검증 불가"(None)** — 파서 설정이 안 맞을 때
  모든 행이 빨개지면 진짜 깨진 패킷을 못 찾는다.
- **표시**: 패킷 뷰에 `검증`/`CHK` 컬럼. OK / FAIL / **빈칸(검증 안 함)** 3-상태.
  "통과"와 "검증하지 않음"을 같은 모양으로 두면 설정이 안 걸린 것을 통과로 오인한다.
- **컬럼 헤더를 언어 키로 전환**: 새 컬럼만 번역하면 헤더가 뒤섞이므로 5개 모두
  `packet_col_*` 키 경유로 바꾸고 언어 전환 시 `headerDataChanged`로 다시 그린다.

### 컬럼 추가가 만든 회귀를 잡았다

캡처에서 **시각 컬럼이 `12:0…`로 잘렸다.** 처음엔 기존 문제로 의심했으나, 체크섬
컬럼을 숨겼을 때 폭이 54→103으로 돌아오는 것을 확인해 **이번 변경이 원인**임을
가렸다(넘겨짚지 않고 실측).

원인: `ResizeToContents`는 표가 비어 있을 때 헤더 라벨 폭으로 정해지는데, 그 뒤
Stretch 컬럼(HEX/ASCII)이 남는 폭을 모두 가져가 데이터가 도착해도 시각 컬럼이 최소
폭(49px)에 눌린 채였다. 실제 창 측정: `widths=[49, 49, 394, 57, 49]` vs
`hints=[103, 31, 143, 63, 23]`.

**첫 행이 들어온 시점에 1회만** 시각 컬럼 폭을 내용에 맞추도록 했다. 매 행마다
재계산하면 S-061이 없앤 비용이 되살아나므로 최초 1회로 제한했다(Clear 시 리셋).
보정 후 4조합 모두 `widths=[103, 5x, ~198, ~198, 49]`.

### 하지 않은 것

- **검증 결과 색상**: 태스크에 "색은 QSS 테마 경유"라고 적었으나 넣지 않았다.
  현재는 `OK`/`FAIL` 텍스트만 쓴다. 셀 색을 넣으려면 `Qt.ForegroundRole`에 테마
  색을 실어야 하는데, 위젯 코드에 색 리터럴을 두지 않으려면 ColorManager 경유
  경로를 새로 만들어야 해 범위를 넘는다. 텍스트만으로도 판독에 지장이 없어
  **후속으로 남긴다**(색을 넣으면 `tests/test_qss_contrast.py` 대상에도 추가할 것).
- **우측 패널 최소 폭**: 컬럼이 늘어 재측정했으나 매크로 탭 요구 폭이 그대로라
  (ko 566 / en 575) `CONTROL_MIN_WIDTH_RIGHT_SECTION=580`은 유효하다. 패킷 탭은
  300px 미만을 요구한다.
