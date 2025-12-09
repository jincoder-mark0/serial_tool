# 작업 세션 요약 (2025-12-09)

## 주요 작업 내용

### 1. 시그널 네이밍 리팩토링 및 일관성 확보
- **MacroCtrlWidget**:
  - `cmd_run_single_requested` → `cmd_run_once_requested` (버튼 텍스트와 일치)
  - `cmd_stop_requested` → `cmd_stop_run_requested` (명확성 향상)
  - `cmd_auto_start_requested` → `cmd_repeat_start_requested` (기능 명확화)
- **PortSettingsWidget**:
  - `scan_requested` → `port_scan_requested` (일관성 확보)
- **테스트 코드 업데이트**:
  - `tests/test_view.py` 및 `tests/test_ui_translations.py`에서 변경된 위젯 이름 및 시그널 반영
  - `ReceivedArea` → `ReceivedAreaWidget` 등 클래스명 변경 사항 적용

### 2. 버그 수정 및 안정성 개선
- **MainWindow 초기화 오류 수정**:
  - `AttributeError: 'MainWindow' object has no attribute 'left_section'` 해결
  - `_connect_toolbar_signals()` 호출 시점을 `left_section` 초기화 이후로 이동
- **PortController Import 오류 수정**:
  - `ModuleNotFoundError: No module named 'serial_worker'` 해결
  - `from serial_worker import SerialWorker` → `from model.serial_worker import SerialWorker`로 경로 수정
- **툴바 'Close' 버튼 동작 수정**:
  - 기존: `open_current_port` (토글)에 연결되어 닫힌 포트를 여는 문제 발생
  - 수정: `close_current_port` 메서드 신설 및 연결 (연결된 상태에서만 동작하도록 로직 추가)
  - `PortSettingsWidget` 및 `PortPanel`에 `is_connected()` 메서드 추가하여 상태 확인 로직 보강

### 3. UI/UX 개선
- **동적 윈도우 크기 조정**:
  - `MainWindow`의 우측 패널(Right Panel) 토글 시 윈도우 크기가 자동으로 조정되도록 구현
  - 패널 숨김 시: 윈도우 너비 감소 (패널 너비만큼)
  - 패널 표시 시: 윈도우 너비 증가 (기본값 400px)

### 4. 네이밍 리팩토링 (Command -> Macro)
- **용어 변경**: `Command` → `Macro` (시스템 명령과의 혼동 방지 및 기능 명확화)
- **클래스명 변경**:
  - `CommandListWidget` → `MacroListWidget`
  - `CommandControlWidget` → `MacroControlWidget`
  - `CommandListPanel` → `MacroPanel`
- **파일명 변경**:
  - `view/widgets/command_list.py` → `view/widgets/macro_list.py`
  - `view/widgets/command_control.py` → `view/widgets/macro_control.py`
  - `view/panels/command_list_panel.py` → `view/panels/macro_panel.py`

## 변경된 파일
- `view/widgets/macro_control.py`: (구 command_control.py) 시그널 리네임 및 클래스명 변경
- `view/widgets/macro_list.py`: (구 command_list.py) 클래스명 변경
- `view/panels/macro_panel.py`: (구 command_list_panel.py) 클래스명 변경 및 시그널 연결 수정
- `view/widgets/port_settings.py`: 시그널 리네임, `is_connected` 추가
- `view/panels/port_panel.py`: `is_connected` 추가
- `view/sections/main_left_section.py`: `open/close_current_port` 로직 개선
- `view/main_window.py`: 초기화 순서 변경, 툴바 시그널 연결 수정, 윈도우 리사이징 구현
- `model/port_controller.py`: Import 경로 수정
- `presenter/port_presenter.py`: 시그널 연결 수정
- `tests/test_view.py`: 테스트 코드 최신화 (MacroListWidget 반영)
- `tests/test_ui_translations.py`: 테스트 코드 최신화 (MacroListWidget 반영)

## 다음 단계 (Next Steps)
- **StatusPanel 구현**: `view/doc/implementation_plan.md`에 따른 상태 패널 구현
- **상태바 상세 정보 표시**: RX/TX 카운트, 에러 카운트 등 실시간 정보 연동
- **단축키 시스템 구현**: `QShortcut`을 이용한 전역/로컬 단축키 적용
