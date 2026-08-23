# S-083 — 소비자 없는 EventBus 갈래 제거

- Status: DONE (2026-08-23 — 상위 직접 수행. pytest 519 passed, ruff 0건)
- Recommended model: **상위 전용**
- 선행: 없음
- Skills to load: task-done
- 근거: 사용자 지시 "전체 기능 설계에 결함은 없는지 다시 살펴보세요" (2026-08-23)

## 목적 (Why)

`EventRouter`가 EventBus 토픽을 Qt 시그널로 복제해 두었는데, 둘은 연결한 소비자가
하나도 없었다:

| 시그널 | 소비자 | 실제 경로 |
|---|---|---|
| `data_received` | **0** | Fast Path (ConnectionController → MainPresenter 직접 시그널) |
| `file_transfer_progress` | **0** | `FileTransferService.signals.progress_updated` 직접 시그널 |

RX 조각마다 발행 → 라우팅 → emit 후 소멸했다.

성능 이득은 **작다** — 과장하지 않는다:

| | RX 조각당 | 5000조각/s 기준 UI 스레드 |
|---|---|---|
| 제거 전 | 3.27us | 1.63% |
| 제거 후 | 2.37us | 1.18% |

본질은 성능이 아니라 CLAUDE.md가 정한 **"Qt 직접 시그널과 EventBus를 목적에 따라
구분해 쓴다"는 규약이 실제로는 무너져 있었다**는 점이다. 같은 이벤트가 두 채널로
흐르고 진짜 소비자는 한쪽에만 붙어 있었다.

## 수행 결과

- `EventRouter`에서 두 시그널·구독·핸들러 제거 (되살리지 말라는 근거를 주석으로 남김)
- `FILE_PROGRESS`는 라우터가 유일한 구독자였으므로 **토픽 자체가 고아**였다.
  발행(`file_transfer_service.py`)과 상수(`EventTopics`)를 함께 제거.
  완료·에러 같은 생명주기 이벤트는 버스에 남기고 **고빈도 진행률 중복만** 걷어냈다.
- `PORT_DATA_RECEIVED`는 버스에 남는다 — MacroRunner가 Expect 매칭에 쓴다.

## 부수 발견 — 고아 토픽 검사의 전제가 틀려 있었다

`test_all_event_topics_have_at_least_one_subscriber_after_router_init`은 "EventRouter만
세우면 모든 토픽에 구독자가 있다"를 전제했다. `port.data_received`의 실제 구독자는
라우터가 아니라 **MacroRunner(Model)** 이므로 이 전제는 원래도 부정확했고, 라우터
구독을 걷어내자 거짓 실패로 드러났다. 검사에 MacroRunner를 포함해 현실화했다.

## 검증

파괴 시험(두 시그널을 되살렸을 때): `test_router_does_not_relay_rx_data`,
`test_router_does_not_relay_file_progress` 둘 다 실패.
