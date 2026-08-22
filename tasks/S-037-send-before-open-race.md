# S-037 — 연결 직후 send 침묵 실패 레이스 수정

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (옵션 판단 1건 포함 — 코드 확인 후 선택)
- 선행: S-033 (발견 경위)
- Skills to load: task-done

## 목적 (Why) — S-033 수행 중 발견 (2026-08-22, 재현 확인된 기존 결함)

`ConnectionController.is_connection_open()`은 `worker.isRunning()`(Qt `start()` 직후 즉시 True)을
보는데, `ConnectionWorker.send_data()`의 가드는 `transport.is_open()`(OS 스레드가 `run()`에
진입해 `open()`을 마쳐야 True)을 본다. 이 간극에 send가 오면 **큐잉이 조용히 실패**한다
(False 반환, 에러 시그널·로그 없음 — 데이터 유실). LOOPBACK처럼 open이 즉시 끝나는
transport에서 재현 창이 잘 드러났지만 SerialTransport에도 동일하게 존재한다.
기존 통합 테스트(`test_integration_refactored.py::test_connection_send_and_close_flow`)가
`wait_until(worker.is_running())`으로 이미 회피하고 있었다 — 알려진 증상의 미해결 원인.

## 확정 설계 (옵션 — 하위가 코드 확인 후 선택, 근거 보고)

**옵션 A (권장 후보)**: `ConnectionWorker.send_data()`의 가드를 `transport.is_open()` 대신
"워커 종료 요청 여부"로 완화해 **open 완료 전에도 큐잉 허용** — run 루프가 open 후 TX 큐를
드레인하므로 순서는 보존된다. 전제 확인 필수: run 루프가 open 실패 시 큐를 버리는 경로,
close 시 잔여 큐 처리(기존에 flush 로직 있음)와의 상호작용을 코드로 확인하고, 안전하면 채택.
**옵션 B (A가 불안전하면)**: 가드는 유지하되 실패를 침묵시키지 않는다 — False 반환 시
controller가 `PORT_ERROR`(또는 경고 로그+`data_sent` 미발행 명확화)로 표면화.

어느 쪽이든: 레이스를 재현하는 회귀 테스트 1건(“start 직후 대기 없이 send → 데이터가
결국 전달된다(A) 또는 명시적 오류가 난다(B)”)을 추가하고, 기존 테스트의
`wait_until(worker.is_running())` 회피가 여전히 필요한지 재평가해 보고.

## 검증 방법

신규 회귀 테스트(LOOPBACK 이용 — 대기 없이 send) 3회 연속 통과 + 전체 pytest(offscreen,
기준선 130+신규) + 스레드 규율(RULES §2: 시작·종료·강제 종료 경로 테스트 확인).

## Acceptance criteria (DoD)

- [ ] start 직후 send가 유실되지 않거나(A) 명시적으로 실패한다(B) — 회귀 테스트로 고정.
- [ ] 선택한 옵션과 근거(전제 확인 결과) 보고. 전체 pytest 통과.
