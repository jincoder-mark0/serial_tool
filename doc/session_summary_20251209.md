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
  - `ReceivedArea` → `RxLogWidget` 등 클래스명 변경 사항 적용

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
  - **좌측 패널 크기 유지**: `splitter.setSizes()` 사용하여 좌측 패널이 변경되지 않도록 수정

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

### 5. MVP 패턴 준수 강화
- **PreferencesDialog 리팩토링**:
  - `SettingsManager` 직접 접근 제거 (MVP 패턴 위반 해결)
  - Presenter(`MainWindow`)를 통해 설정을 전달받아 사용하도록 변경
  - `_get_setting()` 헬퍼 메서드 추가: 중첩된 설정 키(`"settings.theme"`) 안전 접근
  - View 계층이 Model 계층에 직접 접근하지 않도록 개선
- **설정 키 구조 정리**:
  - `PreferencesDialog`에 `port_newline` 설정 추가
  - `main_presenter.py`에서 설정 키 매핑 업데이트 (`port_baudrate`, `port_scan_interval` 등)

### 6. 완성도 개선 (Polish)
- **언어 키 완성**:
  - `MainToolBar`: 모든 액션에 언어 키 적용 (`toolbar_open`, `toolbar_close`, `toolbar_clear`, `toolbar_save_log`, `toolbar_settings`)
  - `MainMenuBar`: 메뉴 액션에 언어 키 적용 (`main_menu_open_port`, `main_menu_close_tab`, `main_menu_save_log`, `main_menu_toggle_right_panel`)
  - `MacroCtrlWidget`: Pause 버튼 추가 및 언어 키 적용 (`macro_ctrl_btn_repeat_pause`)
  - 한국어/영어 언어 파일에 모든 키 추가
- **TODO 주석 정리**:
  - 모든 TODO 주석을 Note로 변경하고 향후 구현 계획 명시
  - `macro_panel.py`: Repeat 파라미터 전달 방식 설명
  - `port_presenter.py`, `main_presenter.py`: 상태바 에러 표시 계획
  - `received_area.py`: 정규식 검색 지원 계획
- **테마 메뉴 개선**:
  - View -> Theme 메뉴에 현재 선택된 테마 체크 표시 추가
  - `MainMenuBar.set_current_theme()` 메서드 추가
  - 테마 액션을 checkable로 설정
- **우측 패널 토글 개선**:
  - 패널 숨김 시 왼쪽 패널 너비 저장 (`_saved_left_width`)
  - 패널 표시 시 저장된 왼쪽 패널 너비 복원
  - 좌측 패널 크기가 변경되지 않도록 개선
- **QSS 스타일 확장**:
  - `warning` 클래스 추가 (노란색 버튼 스타일)
  - Pause 버튼에 warning 스타일 적용
  - Dark/Light 테마 모두에 warning 스타일 정의

## 변경된 파일
- `view/widgets/macro_ctrl.py`: (구 command_control.py) Pause 버튼 추가, 시그널 리네임
- `view/widgets/macro_list.py`: (구 command_list.py) 새로 생성, 완전한 구현
- `view/panels/macro_panel.py`: (구 command_list_panel.py) 클래스명 변경, Note 주석 추가
- `view/widgets/main_toolbar.py`: 언어 키 적용
- `view/sections/main_menu_bar.py`: 언어 키 적용, 테마 체크 표시 기능 추가
- `view/widgets/port_settings.py`: 시그널 리네임, `is_connected` 추가
- `view/panels/port_panel.py`: `is_connected` 추가
- `view/sections/main_left_section.py`: `open/close_current_port` 로직 개선
- `view/main_window.py`: 우측 패널 토글 개선, 테마 체크 표시 업데이트
- `view/dialogs/preferences_dialog.py`: MVP 패턴 준수, `_get_setting()` 추가
- `view/widgets/received_area.py`: Note 주석 추가
- `presenter/main_presenter.py`: 설정 키 매핑 업데이트, Note 주석 추가
- `presenter/port_presenter.py`: Note 주석 추가
- `model/port_controller.py`: Import 경로 수정
- `tests/test_view.py`: 테스트 코드 최신화 (MacroListWidget 반영)
- `tests/test_ui_translations.py`: 테스트 코드 최신화 (MacroListWidget 반영)
- `config/languages/en.json`: 언어 키 추가 (toolbar, menu, macro_ctrl, pref)
- `config/languages/ko.json`: 언어 키 추가 (toolbar, menu, macro_ctrl, pref)
- `config/settings.json`: 설정 키 구조 업데이트
- `resources/themes/common.qss`: warning 클래스 추가
- `resources/themes/dark_theme.qss`: warning 스타일 정의
- `resources/themes/light_theme.qss`: warning 스타일 정의

## 다음 단계 (Next Steps)
- **Presenter 계층 완성**: Model과 View 연동 강화
- **SerialWorker 통합**: 실제 시리얼 통신 기능 구현
- **Macro 자동화 엔진**: Repeat 실행 로직 구현
- **파일 전송 기능**: 대용량 파일 전송 및 진행률 표시

