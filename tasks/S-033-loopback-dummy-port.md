# S-033 — 루프백 더미 포트 (하드웨어 없는 디버깅)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (확정 설계 기준)
- 선행: 없음 (사용자 제안 2026-08-22)
- Skills to load: task-done, lang-keys(툴팁 추가 시)

## 목적 (Why)

실기기 없이 앱의 송수신 전 경로(RX Fast Path·로깅·매크로 Expect·AutoTx·파일 전송)를
디버깅할 수단이 없다. 항상 포트 목록에 나타나는 **루프백 더미 포트**(쓴 바이트가 그대로
수신되는 에코)를 제공한다. S-010(com0com 실환경)의 소프트웨어 보완재.

## 코드 전제 (2026-08-22 작성 시점 확인 — RULES §8)

- Transport 생성 단일 지점: `model/connection_controller.py:240` `transport = SerialTransport(config)`.
- 추상 계약: `core/transport/base_transport.py` — open/close/is_open/read/write/in_waiting(property)
  + 선택 훅 set_broadcast/set_dtr/set_rts. `SerialTransport.read`는 예외 시 `b""`, write는 전파.
- 포트 목록: `model/port_scanner.py`가 열거 → `view/widgets/port_settings.py:403`이
  `addItem(display_text, info.device)`로 표시 (`.device`/`.description` 속성 사용).
- Worker는 transport.read/in_waiting를 논블로킹 폴링한다 (`model/connection_worker.py`).

## 확정 설계

1. `common/constants.py`: `LOOPBACK_PORT_NAME: str = "LOOPBACK"` 추가 (주석: 더미 포트 예약명 —
   실제 장치명과 충돌하지 않는 이름).
2. **신규 `core/transport/loopback_transport.py`** — `class LoopbackTransport(BaseTransport)`:
   - 내부 `bytearray` 버퍼 + `threading.Lock` (worker 스레드에서 read, UI/기타 스레드에서 write).
   - `write(data)`: 버퍼에 append (에코). `read(size)`: 버퍼 앞에서 size만큼 pop (없으면 `b""`).
   - `in_waiting`: 버퍼 길이. open/close/is_open: 플래그만. 선택 훅은 무동작.
   - 모듈 헤더 WHY/WHAT/HOW 관례, 타입 힌트.
3. `model/connection_controller.py` `open_connection`: `config.port == LOOPBACK_PORT_NAME`이면
   `LoopbackTransport(config)` 생성, 아니면 기존 그대로 — 분기 이 한 곳만.
4. `model/port_scanner.py`: 스캔 결과 목록 끝에 루프백 항목 상시 추가 —
   `.device = LOOPBACK_PORT_NAME`, `.description = "Loopback (debug echo)"` 형태의 경량
   객체(dataclass) 사용. 기존 반환 타입 소비처(`port_settings.py:403`)와 속성 호환 확인.
5. 테스트 (`tests/test_loopback_transport.py` 신규):
   - 단위: write→in_waiting→read 왕복, 부분 read, close 후 동작, 스레드 안전(간단 2스레드).
   - 통합: `ConnectionController.open_connection(PortConfig(port="LOOPBACK"))` →
     `send_data` → data_received 시그널로 에코 수신 (qtbot.waitSignal — 기존 통합 테스트 패턴 참고).
6. 실행 확인: 캡처 1회(dark/ko)로 포트 콤보에 LOOPBACK 항목이 보이는지 육안 확인
   (**캡처 후 settings.json checkout**).

## Acceptance criteria (DoD)

- [ ] 포트 목록에 LOOPBACK 상시 표시, 연결·송신 시 동일 바이트가 RX 경로로 수신 (통합 테스트).
- [ ] provider 분기는 controller 한 곳뿐 (다른 계층에 LOOPBACK 문자열 비교 없음 — 상수 경유).
- [ ] 전체 pytest 통과 (기준선 122+신규), 캡처 확인.
