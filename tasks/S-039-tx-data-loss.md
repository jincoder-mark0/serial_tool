# S-039 — [P0] TX 데이터 유실 2건 (close 시 flush 부재 + write_timeout 무효)

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인·커밋 완료)
- Recommended model: **하위(Sonnet) 가능** (설계 확정 — 벗어나면 중단·보고)
- 선행: 없음
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` A-2, A-3

## 목적 (Why)

"전송 성공"이라고 보고한 데이터가 실제로는 나가지 않는 경로가 두 개 있다.

**(1) close 시 TX 큐 flush 부재**: `model/connection_worker.py`의 `run()`은
`while self.is_running():` 조건을 루프 맨 위에서만 확인한다. `msleep(1)`(큐·버퍼가 빈
상태) 중에 `stop()`이 플래그를 내리면 TX 큐를 비우는 블록을 한 번도 통과하지 못하고
`finally`로 빠지며, `finally`는 RX 배치 버퍼만 flush하고 **TX 큐는 버린다**.
`send_data()`는 큐잉 성공 시점에 이미 `True`를 반환한 뒤다.
- 결합 위험: `model/file_transfer_service.py`는 마지막 청크가 **큐에 들어간 시점**에
  `FileCompletionEvent(success=True)`를 발행한다. 전송 완료 직후 포트를 닫는 운용에서
  파일 끝부분이 조용히 유실되고도 "성공"이 뜬다.

**(2) `write_timeout=0`**: `core/transport/serial_transport.py:72` 주석은 "전송 실패 시 예외를
전파하여 데이터 유실을 방지"라고 적었지만, 설치된 pyserial 3.5의 Windows 구현은 정반대다
(실행 확인):
```
serialwin32.py:315      if self._write_timeout != 0:   # 이때만 완료 확인(GetOverlappedResult)
serialwin32.py:332-334  elif errorcode in (ERROR_SUCCESS, ERROR_IO_PENDING): return len(data)
```
즉 `0`이면 **완료 미확인 상태에서도 성공으로 보고**한다.

## 확정 설계

1. **TX flush** — `model/connection_worker.py`:
   - `run()`의 `finally` 블록에서 `transport.close()` **이전에** TX 큐를 마지막으로 드레인한다
     (`transport.is_open()`인 동안만; 이미 닫혔거나 open 실패면 드레인 불가 → 아래 3번).
   - 드레인 실패/불가 시 조용히 버리지 말고 남은 항목 수를 `error_occurred`(또는 최소한
     `logger.warning`)로 표면화한다. **침묵 금지가 이 태스크의 핵심**이다.
2. **write_timeout** — `core/transport/serial_transport.py`:
   - `write_timeout=0` → `WRITE_TIMEOUT_S`(신규 상수, `common/constants.py`, 값 1.0 제안)로 교체해
     pyserial이 완료를 확인하는 분기를 타게 한다. 타임아웃 시 `SerialTimeoutException`이
     올라오며, 현재 `write()`는 예외를 상위로 전파하므로(기존 주석의 의도) 그대로 두면 된다.
   - 잘못된 주석(“write_timeout=0으로 예외 전파”)을 실제 동작에 맞게 수정한다.
   - ⚠ 이 변경은 **쓰기가 블로킹될 수 있음**을 뜻한다. `ConnectionWorker.run()`이 워커 스레드
     이므로 UI는 멈추지 않지만, 값이 너무 크면 종료가 지연된다 — 1.0초 제안 근거를 주석에.
3. **파일 전송 완료 시점** — `model/file_transfer_service.py`:
   - 완료 이벤트를 "마지막 청크 큐잉"이 아니라 "TX 큐가 비워진 뒤"에 발행하도록 조정.
     `ConnectionController`/`ConnectionWorker`에 큐 잔량 조회가 이미 있으면
     (`get_write_queue_size`) 그것으로 폴링. **판단이 갈리면 이 항목만 보류하고 보고**하라
     (1·2번은 그대로 진행).

## 검증 방법

- 회귀 테스트 신설 `tests/test_tx_flush.py`:
  ① LOOPBACK 포트로 `send_data` 직후 즉시 `close_connection` → 보낸 바이트가 유실되지 않거나
  (드레인 성공) **명시적 경고/에러가 발생**하는지(침묵 금지) 확인.
  ② 큐에 여러 건을 넣고 즉시 종료 → 순서·수량 확인.
- 전체 pytest(offscreen, 기준선 139+신규) 2회 연속.
- 실기기 검증은 불가 — **"실기기 미검증"으로 명시 보고**. write_timeout 변경의 실제 시리얼
  타이밍 영향은 S-010(가상 포트)/실기기에서 재확인 대상임을 보고에 남긴다.

## Acceptance criteria (DoD)

- [ ] 종료 시 TX 큐가 드레인되거나, 불가 시 조용히 버리지 않고 표면화된다 (테스트로 고정).
- [ ] `write_timeout`이 완료 확인 분기를 타고, 주석이 실제 동작과 일치한다.
- [ ] 파일 전송 완료 이벤트 시점 조정 (또는 보류 사유 보고).
- [ ] 전체 pytest 통과, 실기기 미검증 항목 명시.
