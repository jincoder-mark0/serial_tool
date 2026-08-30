# RxLogView Benchmark Result — 2026-08-30

> 대상: P2-B #4 `RxLogView BatchRenderer 후보안 비교`
> 결론: **별도 BatchRenderer 도입 보류 — 현재 구조 유지**
> 측정 환경: GitHub-hosted Windows Server 2025 / Python 3.11.9 / `QT_QPA_PLATFORM=offscreen`
> 측정 도구: `tools/rx_view_benchmark.py`, `tools/rx_view_batch_matrix.py`

---

## 1. 판정 요약

현재 `QSmartListView`에 별도 `BatchRenderer`를 추가할 근거가 부족하다.

핵심 근거:

1. `LogModel.add_logs()`는 이미 row batch insertion을 수행하며 single-row insert 대비 약 **5.5~5.8배** 빠름
2. ASCII bytes decode/formatting overhead는 약 **0~3%** 수준으로 dominant bottleneck이 아님
3. event-loop/paint servicing 비용은 약 **21~28%** 존재하지만 별도 renderer가 필요한 수준의 구조적 병목으로 확인되지 않음
4. View update 크기를 4 KiB -> 64 KiB로 키워 update 횟수를 16배 줄이면 처리량이 약 **14.7배** 증가
5. 이 batching 역할은 이미 `DataTrafficHandler`가 `UI_REFRESH_INTERVAL_MS=30 ms` 단위로 수행

따라서 현재 문제는 "BatchRenderer가 없음"이 아니라 **View update 호출 횟수**에 민감한 Qt View 경로이며, 이미 존재하는 upstream aggregation이 올바른 해결 위치다.

---

## 2. Architecture 근거

현재 RX 경로:

```text
ConnectionWorker
    |
    v
ConnectionController.data_received
    |
    v
DataTrafficHandler
    |  port별 bytearray aggregation
    |  UI_REFRESH_INTERVAL_MS = 30 ms
    v
LogDataBatch
    |
    v
MainWindow.append_rx_data()
    |
    v
QSmartListView.append_bytes()
    |
    +-- decode / HEX conversion
    +-- optional formatter
    +-- text split
    v
LogModel.add_logs(lines)
    |
    +-- beginInsertRows() 1회
    +-- list.extend(lines)
    +-- endInsertRows() 1회
```

즉 batching은 두 계층에 이미 존재한다.

- byte batching: `DataTrafficHandler`
- row insertion batching: `LogModel.add_logs()`

새 `BatchRenderer`를 추가하면 동일 책임의 세 번째 batching 계층이 생길 가능성이 크다.

---

## 3. 반복 측정 결과

### 3.1 Run A

Windows hosted runner, repeat=3:

| Scenario | Result |
|---|---:|
| Model batch insert | 2,554,617.727 lines/s |
| Model single insert control | 441,049.345 lines/s |
| Preformatted text | 2.404 MB/s |
| ASCII `append_bytes` | 2.363 MB/s |
| ASCII + event loop | 1.897 MB/s |
| HEX `append_bytes` | 0.426 MB/s |

Derived:

```text
batch_vs_single_ratio       = 5.792 x
ascii_formatting_cost_ratio = 1.017 x
event_loop_cost_ratio       = 1.246 x
```

### 3.2 Run B

별도 hosted runner, repeat=3:

```text
batch_vs_single_ratio       = 5.663 x
ascii_formatting_cost_ratio = 1.030 x
event_loop_cost_ratio       = 1.214 x
```

### 3.3 Final Run

최종 branch HEAD 검증 run, repeat=3:

| Scenario | Result |
|---|---:|
| Model batch insert | 2,565,641.949 lines/s |
| Model single insert control | 462,132.835 lines/s |
| Preformatted text | 2.401 MB/s |
| ASCII `append_bytes` | 2.397 MB/s |
| ASCII + event loop | 1.870 MB/s |
| HEX `append_bytes` | 0.422 MB/s |

Derived:

```text
batch_vs_single_ratio       = 5.552 x
ascii_formatting_cost_ratio = 1.002 x
event_loop_cost_ratio       = 1.281 x
```

세 run에서 같은 방향이 반복됐다.

---

## 4. Flush-size Matrix

같은 2 MiB ASCII payload를 View에 전달하되 update size만 바꿨다.
각 append 후 `QApplication.processEvents()`를 수행해 View update 횟수 영향을 의도적으로 드러냈다.

| Chunk | Update count | Throughput | Elapsed |
|---:|---:|---:|---:|
| 4 KiB | 512 | 0.813 MB/s | 2459.123 ms |
| 16 KiB | 128 | 3.191 MB/s | 626.802 ms |
| 64 KiB | 32 | 11.935 MB/s | 167.571 ms |

Derived:

```text
update_count_reduction_ratio             = 16.000 x
largest_vs_smallest_throughput_ratio     = 14.675 x
```

### 해석

update 횟수 감소와 처리량 증가가 거의 비례한다.

```text
4 KiB / 512 updates
        |
        | update 수 4배 감소
        v
16 KiB / 128 updates
        |
        | update 수 4배 감소
        v
64 KiB / 32 updates
```

따라서 비용은 bytes decode보다 Qt model/view notification, autoscroll, event handling, paint/layout처럼 **update 단위마다 발생하는 fixed cost**의 영향이 크다.

이 fixed cost를 줄이는 올바른 위치는 별도 renderer 추가보다 이미 존재하는 `DataTrafficHandler` aggregation이다.

---

## 5. Serial 입력량과의 관계

현재 지원 최대 baudrate는 4,000,000 baud다.
일반적인 8N1 기준으로 byte당 약 10 bit를 가정하면 한 port의 이론적 최대 payload는 대략:

```text
4,000,000 bit/s / 10 bit ~= 400,000 byte/s
```

30 ms 동안 누적되는 양은 대략:

```text
400,000 byte/s * 0.030 s ~= 12,000 byte
```

즉 최고 baudrate 지속 RX에서도 `DataTrafficHandler`의 30 ms aggregation은 대략 12 KiB 수준의 View update를 자연스럽게 만든다.
이는 matrix의 4 KiB보다 16 KiB scenario에 더 가깝다.

이 계산은 실제 USB/driver throughput 보장이 아니라 **현재 batching cadence가 workload와 동떨어진 값이 아님을 확인하기 위한 상한 추정**이다.

---

## 6. HEX Mode

HEX path는 약 0.42~0.44 MB/s로 ASCII보다 크게 느렸다.

그러나 현재 benchmark는 HEX에서 byte를 `"XX "` 문자열로 확장하므로 입력 1 byte가 약 3 text char로 증가하고, ASCII scenario와 row shape도 다르다.
따라서 이 결과를 바로 `BatchRenderer` 필요성으로 연결하지 않는다.

향후 실제 HEX 표시가 사용자-visible bottleneck이 되면 우선 조사 대상:

1. `" ".join(f"{b:02X}" ...)` conversion
2. 매우 긴 single-row text layout
3. `QTextDocument` delegate layout/paint
4. repaint cadence

별도 BatchRenderer는 그 이후 후보로 둔다.

---

## 7. 최종 결정

### 결정

**P2-B #4는 BatchRenderer를 구현하지 않고 완료 처리한다.**

유지:

- `DataTrafficHandler` 30 ms RX aggregation
- `LogModel.add_logs()` range insertion
- 현재 direct View facade

도입하지 않음:

- 별도 `BatchRenderer`
- 추가 QThread / rendering worker
- 데이터 drop/coalescing 정책

WHY:

- 기존 batching이 이미 효과적
- 새 abstraction이 해결할 독립적인 병목이 증명되지 않음
- 추가 lifecycle/ownership 복잡도 대비 기대 이득 불명확

---

## 8. 재검토 Trigger

다음 증상이 실제로 확인될 때만 BatchRenderer 또는 repaint scheduler를 다시 검토한다.

- 2/4 port 동시 고속 RX에서 visible UI freeze
- UI event latency 증가
- 30 ms aggregation 후에도 pending View update backlog 지속 증가
- 실제 화면 환경에서 offscreen 결과와 다른 severe paint bottleneck
- HEX mode가 실제 요구 throughput을 충족하지 못함

이 경우에도 먼저 `DataTrafficHandler` cadence / autoscroll / delegate paint를 측정한 뒤 별도 renderer를 검토한다.

---

## 9. 검증 범위

최종 benchmark branch CI:

```text
Windows Python 3.11 full pytest: 648 passed, 2 external lark warnings
Ruff: Green
Language keys: Green
Task board: Green
Observational benchmark: success
```

주의:

- GitHub-hosted runner 절대 수치는 제품 성능 보장이 아님
- 실제 display/USB Serial/4-port 동시 workload는 이 측정에 포함되지 않음
- 이 문서의 결론은 **현재 코드에 별도 BatchRenderer를 추가할 engineering evidence가 있는가**에 대한 판단임
