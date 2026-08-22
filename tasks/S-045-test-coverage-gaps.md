# S-045 — [P2] 커버리지 공백 메우기 + DataLogger 종료 유실

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` B-5, C-2

## 목적 (Why)

테스트가 **0건**인 모듈들이 있고, 그중 일부는 실패해도 조용해서 발견이 늦다.
S-038(로그 뷰 파손)이 정확히 이 공백 때문에 134개 테스트를 통과한 채 방치됐다.
**구조 개선(God object 분해 등)을 착수하기 전에 이 안전망을 먼저 깐다** — 지금
`ThemeManager`를 쪼개면 그 변경을 검증할 테스트가 없다.

또한 `core/data_logger.py`의 `stop_logging()`은 `join(timeout=1.0)` 후 타임아웃 여부와
무관하게 파일을 닫는다. 고속 로깅 중지 시 백그라운드 스레드가 쓰는 중인 파일을 메인이
닫아 `ValueError: I/O operation on closed file` + **잔여 큐 유실**이 발생한다.

## Steps (우선순위 순 — 시간이 부족하면 위에서부터)

1. **`core/data_logger.py`** — 테스트 신설 + 결함 수정:
   - 테스트: BIN/HEX/PCAP 각 포맷의 파일 산출물 검증. 특히 **PCAP 헤더·패킷 `struct.pack`
     바이트를 직접 파싱해 확인**(포맷이 틀리면 Wireshark에서만 드러나므로).
     HEX 덤프 라인 포맷도 정규식으로 고정.
   - 결함 수정: `stop_logging()`이 잔여 큐를 잃지 않도록 한다. 무한 대기는 위험하므로
     **드레인 완료까지 대기하되 상한을 두고, 상한 초과 시 남은 항목 수를 경고로 표면화**
     (S-039의 TX 드레인과 같은 원칙 — 조용히 버리지 않는다).
2. **`presenter/event_router.py`** — `_subscribe_events()`가 실제로 실행되는 테스트.
   EventBus에 각 토픽을 publish했을 때 대응 Qt 시그널이 나오는지 확인
   (토픽 오타·구독 누락을 잡는 것이 목적).
3. **`model/file_transfer_service.py`** — 백프레셔 루프, 취소, 완료/에러 이벤트 발행.
   LOOPBACK + 임시 파일로 실제 전송 왕복을 검증한다. ⚠ 이 파일의 **코드는 수정하지 말 것**
   (S-044가 enum 정리 중) — 테스트만 작성.
4. **`core/error_handler.py`** — 전역 예외 후크가 설치되고 예외를 잡아 기록하는지.
   ⚠ 테스트가 실제 `sys.excepthook`을 오염시키지 않도록 설치→검증→복원을 보장할 것.
5. **`core/structures.py`** — `RingBuffer` wraparound/overflow 산술과 `ThreadSafeQueue`
   maxlen 포화. `tests/test_core_structures.py`는 이름과 달리 이 모듈을 다루지 않으므로
   **혼동을 줄이려면 신규 파일**(`tests/test_ring_buffer.py` 등)로 만들고, 기존 파일 개명은
   하지 말 것(다른 문서가 참조 중일 수 있음 — 보고만).

## 검증 방법

- 각 신규 테스트 파일 단독 3회 연속 + 전체 pytest(offscreen, 기준선 168+신규) 2회 연속.
- DataLogger 수정은 스레드 관련이므로 RULES §2대로 시작·정상 종료·강제 종료 경로를 확인.

## Acceptance criteria (DoD)

- [ ] 1~3번 모듈에 테스트가 생기고 전부 통과 (4·5번은 시간 허용 시).
- [ ] PCAP/HEX 산출물이 바이트 수준으로 검증된다.
- [ ] DataLogger 종료 시 잔여 로그가 유실되지 않거나 표면화된다.
- [ ] 전체 pytest 통과. 어디까지 했는지 보고에 명시.
