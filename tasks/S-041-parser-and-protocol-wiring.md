# S-041 — [P1] 파서 설정 무효 + SPI 선택이 조용히 시리얼로 연결됨

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: S-039, S-040 (같은 파일 충돌 회피 — 커밋 후 착수)
- Skills to load: task-done, lang-keys
- 근거: `doc/refactor_audit_20260822.md` B-1, B-2

## 목적 (Why) — 기능이 조용히 거짓말한다

**(1) 패킷 파서 설정이 통째로 무효**: `model/connection_controller.py:250`이
`ParserFactory.create_parser(ParserType.RAW)`를 **설정과 무관하게 항상** 호출한다.
Preferences의 Packet 탭(Parser Type/Delimiter/Fixed Length), `ConfigKeys.PACKET_PARSER_TYPE`
설정 키, README의 기능 서술이 모두 있는데 **사용자가 무엇을 골라도 반영되지 않고**
AT/Delimiter/FixedLength 파서는 도달 불가 코드다.

**(2) SPI 선택이 조용히 시리얼로**: `PortConfig.protocol`과 SPI 필드(`speed`/`mode`),
프로토콜 콤보·`QStackedWidget` 분기가 갖춰져 SPI 지원처럼 보이지만, `open_connection()`은
LOOPBACK 여부만 보고 그 외에는 무조건 `SerialTransport`를 만든다. **`config.protocol`을
읽는 코드가 저장소에 한 곳도 없다**(`SpiTransport` 자체가 없음). SPI를 골라도 경고 없이
시리얼로 연결을 시도한다.

## 확정 설계

1. **파서 설정 반영** — `model/connection_controller.py`:
   - 파서 생성 시 설정값(`ConfigKeys.PACKET_PARSER_TYPE` 등)을 반영한다.
   - ⚠ **Model은 SettingsManager를 직접 읽지 않는다**(계층 규율). 설정을 읽는 주체는
     Presenter이므로, **`PortConfig`(DTO)에 파서 설정을 실어 보내거나 컨트롤러에 파서 설정을
     주입하는 방식** 중 현재 구조에 맞는 쪽을 택하고 근거를 보고하라.
     현재 `open_connection(config)`가 유일한 진입점이므로 DTO 확장이 자연스러울 수 있다.
   - `ParserFactory`가 요구하는 파라미터(delimiter, length 등)를 함께 전달한다.
   - 잘못된 설정값(빈 delimiter, 0 이하 length)은 이미 팩토리가 거부하므로, 그 예외가
     사용자에게 보이도록 처리 경로를 확인한다(조용한 실패 금지).
2. **미구현 프로토콜 명시적 거부** — `model/connection_controller.py`:
   - `config.protocol`이 지원하지 않는 값(현재 "SPI")이면 **연결을 시도하지 말고**
     `error_occurred`로 "미구현 프로토콜" 취지의 메시지를 발행하고 False 반환.
   - 메시지는 언어 키 경유가 아니어도 된다(Model 계층 로그·이벤트) — 단 Presenter가 UI로
     표면화하는 기존 경로(`_emit_error`)를 그대로 탄다.
   - 지원 프로토콜 판정은 문자열 하드코딩 대신 `common/enums.py`에 있으면 그것을,
     없으면 상수로 정의해 사용한다.
3. **README 정합**: SPI가 미지원임을 기능 목록에서 명확히(이미 §1.4에 "SPI/I2C는 향후"가
   있으면 UI에 노출되는 이유를 한 줄 보강).

## 검증 방법

- 테스트 신설 `tests/test_parser_and_protocol.py`:
  ① 파서 설정별로 `open_connection` 후 생성된 파서 타입이 설정과 일치하는지(LOOPBACK 사용).
  ② `protocol="SPI"`로 열기 시도 → 연결되지 않고 에러가 발행되는지.
  ③ 기본(Serial) 경로 회귀.
- 전체 pytest(offscreen, 기준선은 S-039/S-040 커밋 후 값 확인) + `check_language_keys`(키를
  추가했다면).

## Acceptance criteria (DoD)

- [ ] Preferences에서 고른 파서 타입이 실제로 적용된다 (테스트로 고정).
- [ ] SPI 선택 시 조용히 시리얼로 연결되지 않고 명시적으로 거부된다.
- [ ] Model이 SettingsManager를 직접 읽지 않는다 (계층 규율 유지) — 채택 방식과 근거 보고.
- [ ] 전체 pytest 통과.
