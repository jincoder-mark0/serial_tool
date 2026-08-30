# 테스트 가이드 (Testing Guide)

이 문서는 SerialTool의 pytest/ruff 실행 순서와 결과 해석 규칙을 설명합니다.

> 현재 리팩토링 검증 체크리스트: [`../Task.MD`](../Task.MD)  
> 구조 변경 상세: [`../doc/refactoring_validation_report_20260830.md`](../doc/refactoring_validation_report_20260830.md)

현재 `refactor/presenter-view-boundary` 브랜치는 대규모 constructor/API 변경 후 전체 검증 단계입니다.
**과거의 497 passed 같은 숫자를 현재 기준선으로 사용하지 않습니다.** 전체 pytest를 실제 실행해 Green을 확인한 뒤 새 baseline을 기록합니다.

---

## 1. 테스트 환경

가상 환경 활성화:

Windows:

```powershell
.venv\Scripts\activate
$env:QT_QPA_PLATFORM = "offscreen"
```

Linux/macOS:

```bash
source .venv/bin/activate
export QT_QPA_PLATFORM=offscreen
```

의존성:

```bash
pip install -r requirements.txt
```

ruff가 없다면:

```bash
pip install ruff
```

---

## 2. 현재 권장 검증 순서

대규모 리팩토링에서는 전체 pytest부터 돌리기보다 실패 범위를 좁히는 순서로 실행합니다.

### 2.1 Ruff

```bash
ruff check .
```

먼저 import/undefined-name/unused 항목을 정리합니다.

### 2.2 Architecture contract

```bash
python -m pytest -q \
  tests/test_layer_dependencies.py \
  tests/test_composition_root_contract.py \
  tests/test_architecture_policy_boundaries.py \
  tests/test_direct_event_topology.py \
  tests/test_presenter_view_contract.py \
  tests/test_port_presenter_sender_contract.py
```

Windows PowerShell에서는 한 줄로 실행하거나 backtick을 사용합니다.

검증 대상:

- layer 역방향 import
- Single Composition Root
- EventRouter 재도입 여부
- hidden runtime fallback
- Presenter → 존재하지 않는 View API
- broad signal disconnect / sender inference 회귀

### 2.3 Lifecycle / Threading

```bash
python -m pytest -q \
  tests/test_shutdown_coordinator.py \
  tests/test_shutdown_data_logger.py \
  tests/test_file_transfer_manager.py \
  tests/test_port_scan_shutdown.py \
  tests/test_macro_script_manager.py \
  tests/test_manual_control_transient_state.py \
  tests/test_port_tab_cleanup.py
```

검증 대상:

- running QThread/QRunnable 정리
- shutdown ordering
- queued RX data loss
- FileTransfer cancel
- PortScan/MacroScript worker lifetime
- Auto Tx transient state

### 2.4 핵심 기능

```bash
python -m pytest -q \
  tests/test_command_transmission_service.py \
  tests/test_presenter_manual_control.py \
  tests/test_auto_tx.py \
  tests/test_macro_execution_coordinator.py \
  tests/test_parser_and_protocol.py \
  tests/test_presenter_packet.py \
  tests/test_file_transfer.py \
  tests/test_integration_refactored.py
```

### 2.5 전체 테스트

```bash
python -m pytest -q
```

전체 테스트가 Green이면 그 실행 결과의 정확한 passed/failed/skipped 수를 현재 baseline으로 기록합니다.

---

## 3. CI 보조 검사

```bash
python tools/check_language_keys.py
python tools/check_task_boards.py
```

GitHub Actions의 현재 핵심 job:

- Windows full pytest (`QT_QPA_PLATFORM=offscreen`)
- language key integrity
- task-board consistency
- `ruff check .`

PR에서 CI Green을 확인해야 merge-ready로 판단합니다.

---

## 4. 특정 테스트 실행

파일:

```bash
python -m pytest tests/test_command_transmission_service.py -v
```

함수:

```bash
python -m pytest tests/test_command_transmission_service.py::test_single_send -v
```

키워드:

```bash
python -m pytest -k "shutdown" -v
```

직전 실패만:

```bash
python -m pytest -lf
```

첫 실패에서 중단:

```bash
python -m pytest -x
```

느린 테스트 확인:

```bash
python -m pytest --durations=20
```

---

## 5. 결과 해석

- `.`: PASSED
- `F`: FAILED
- `E`: setup/runtime ERROR
- `s`: SKIPPED
- `x`: XFAIL

대규모 리팩토링에서 `TypeError`, `AttributeError`, import error가 나오면 바로 production에 compatibility fallback을 추가하지 않습니다.
먼저 stale test/API인지 판정합니다.

---

## 6. Stale API / Constructor 판정

### MainPresenter

현재 production MainPresenter는 Bootstrapper가 생성합니다.

테스트가 직접 두 번째 MainPresenter를 만들기보다 가능한 경우:

```python
runtime = ApplicationBootstrapper(view, settings).build()
presenter = runtime.main_presenter
```

을 사용합니다.

### Explicit DI

다음과 같은 옛 호출은 stale일 수 있습니다.

```python
PortPresenter(view, controller)
MacroPresenter(panel, runner)
```

현재 필수 Manager/Settings dependency를 production 계약에 맞게 주입합니다.

### 제거된 EventRouter

다음과 같은 구조는 복구하지 않습니다.

```python
presenter.event_router.packet_received.emit(...)
```

현재 owner의 direct Qt signal을 사용합니다.

### 제거된 MainPresenter 내부 필드

테스트가 다음을 MainPresenter에서 직접 찾으면 stale 가능성이 큽니다.

```text
data_handler
settings_manager
status_coordinator
file_transfer_manager
port_scan_manager
macro_script_manager
macro_presenter
packet_presenter
port_presenter
_sys_log_writer
```

실제 owner의 public API나 `ApplicationComponents`를 사용합니다.

---

## 7. View Mock 규율

Presenter 테스트에서 concrete View/Panel mock을 만들 때 가능한 경우 `spec=`을 사용합니다.

```python
panel = MagicMock(spec=ManualControlPanel)   # 권장
panel = MagicMock()                          # interface drift를 삼킬 수 있음
```

`spec`만으로 모든 path를 보장하지 못하므로 `tests/test_presenter_view_contract.py`가 source를 정적으로 검사합니다.

새 Presenter/Coordinator에서 View dependency를 추가할 때 타입 주석과 명확한 `self.attr = dependency` 형태를 유지하면 contract 검사 추적성이 좋아집니다.

---

## 8. Threading 테스트 규율

QThread/QRunnable을 테스트할 때는 다음을 구분합니다.

- thread start 자체가 성공했는지
- 실제 작업이 완료됐는지
- signal이 main thread에 전달됐는지
- cancel/stop 후 `isRunning()`이 false인지
- 테스트 teardown에서 background object가 남지 않는지

`time.sleep()`만으로 완료를 추정하지 말고 가능한 경우 `qtbot.waitUntil`, `waitSignal`, 실제 lifecycle state를 사용합니다.

---

## 9. Hardware / LOOPBACK / Mock 구분

테스트 결과를 보고할 때 다음을 구분합니다.

- Mock Serial
- LOOPBACK Transport
- 실제 serial hardware

LOOPBACK/Mock으로 통과한 것을 실제 장비 flow-control/timing 검증으로 표현하지 않습니다.

---

## 10. 완료 기준

현재 리팩토링 테스트 검증 완료 조건:

```text
ruff Green
  +
architecture contract Green
  +
lifecycle/threading Green
  +
feature tests Green
  +
full pytest Green
  +
language/task checks Green
  +
PR CI Green
```

검증하지 않은 항목은 `Task.MD`에서 체크하지 않습니다.
