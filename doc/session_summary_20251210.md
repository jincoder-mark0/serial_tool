# 작업 세션 요약 (2025-12-10)

**세션 날짜**: 2025-12-10
**주요 목표**: View 계층 완성, 중앙 집중식 경로 관리, 네이밍 일관성 개선, 아키텍처 및 성능 고도화

---

## 주요 작업 내용

### 1. View 계층 UI 완성

#### Parser 탭 구현 (PreferencesDialog)
- **언어 키 추가**:
  - `config/languages/en.json`: 22개의 Parser 관련 키 추가
  - `config/languages/ko.json`: 동일한 한국어 번역 추가
- **Parser 탭 UI 구성**:
  - **Parser Type**: 5가지 라디오 버튼 (Auto, AT, Delimiter, Fixed, Raw)
  - **Delimiter Settings**: QListWidget + 추가/삭제 버튼
  - **Fixed Length**: 패킷 길이 SpinBox (1-4096 바이트)
  - **Inspector Options**: 버퍼 크기, 실시간 추적, 자동 스크롤

#### Connect 버튼 상태 스타일 (QSS)
- **PortState Enum 통합**:
  - `core/port_state.py`: `DISCONNECTED`, `CONNECTED`, `ERROR` 상태 정의
  - `view/widgets/port_settings.py`: `set_connection_state(PortState)` 메서드 구현
- **QSS 스타일 추가**:
  - `dark_theme.qss`: `QPushButton[state="connected"]`, `[state="error"]` 스타일
  - `light_theme.qss`: 동일한 port connection state 스타일

#### ReceivedArea 동적 설정
- **max_lines 동적 적용**:
  - `ReceivedAreaWidget.set_max_lines(max_lines)` 메서드 추가
  - `MainPresenter.on_settings_change_requested()`: 설정 변경 시 모든 ReceivedArea 업데이트
  - `PortPresenter`: 초기화 시 설정에서 max_lines 읽어서 적용

---

### 2. 중앙 집중식 경로 관리 (AppConfig)

#### AppConfig 클래스 생성
- **파일**: `config.py`
- **기능**:
  - 모든 리소스 경로를 중앙에서 관리
  - 개발 모드와 PyInstaller 번들 환경 자동 감지
  - 경로 검증 메서드 (`validate_paths()`)
- **관리 경로**:
  - `settings_file`: `config/settings.json`
  - `languages_dir`: `config/languages/`
  - `themes_dir`: `resources/themes/`
  - `icons_dir`: `resources/icons/`

#### 매니저 클래스 통합
- **SettingsManager**:
  - `AppConfig` 인스턴스를 받아 `settings_file` 경로 사용
  - 싱글톤 패턴 `__new__` 메서드 수정 (`*args, **kwargs` 지원)
  - `@property` 데코레이터로 `_get_config_path` 변경
- **LangManager**:
  - `AppConfig`에서 `languages_dir` 경로 사용
  - 하위 호환성 유지 (AppConfig 없이도 동작)
- **ThemeManager**:
  - `AppConfig`에서 `themes_dir`, `icons_dir` 경로 사용
  - `load_theme()`, `get_icon()` 메서드 업데이트

#### main.py 수정
- **sys.path 설정 개선**:
  - 모든 import 전에 `sys.path.insert(0, ...)` 실행
- **AppConfig 초기화 및 전달**:
  - `AppConfig` 인스턴스 생성
  - 경로 검증 및 로깅
  - `MainWindow`에 `app_config` 전달

---

### 3. Import 구조 개선

#### __init__.py 생성
- **view/sections/__init__.py**:
  - `MainLeftSection`, `MainRightSection`, `MainStatusBar`, `MainMenuBar`, `MainToolBar` export
- **view/widgets/__init__.py**:
  - 모든 위젯 클래스 export (이미 존재, 확인만 함)
- **view/dialogs/__init__.py**:
  - `FontSettingsDialog`, `AboutDialog`, `PreferencesDialog` export

#### main_window.py Import 간결화
- **변경 전**:
  ```python
  from view.sections.main_left_section import MainLeftSection
  from view.sections.main_right_section import MainRightSection
  from view.widgets.main_toolbar import MainToolBar
  from view.dialogs.font_settings_dialog import FontSettingsDialog
  ```
- **변경 후**:
  ```python
  from view.sections import (
      MainLeftSection, MainRightSection,
      MainStatusBar, MainMenuBar, MainToolBar
  )
  from view.dialogs import (
      FontSettingsDialog, AboutDialog, PreferencesDialog
  )
  ```

#### PortPanel 직접 사용 제거
- `main_window.py`에서 `PortPanel` import 제거
- `isinstance(current_widget, PortPanel)` 체크 제거
- 더 일반적인 접근 방식 사용

---

### 4. 네이밍 일관성 개선

#### rx → recv 변경
- **파일**: `view/widgets/received_area.py`
- **변경 사항**:
  - 모든 `rx_` 접두사를 `recv_`로 변경
  - `on_clear_rx_log_clicked()` → `on_clear_recv_log_clicked()`
  - `rx_search_input` → `recv_search_input`
  - `rx_hex_chk` → `recv_hex_chk`
  - 등 모든 관련 변수 및 메서드명 변경

#### manual_control → manual_ctrl 변경
- **파일명 변경**:
  - `view/widgets/manual_control.py` → `view/widgets/manual_ctrl.py` (삭제됨)
  - `view/panels/manual_control_panel.py` → `view/panels/manual_ctrl_panel.py`
- **클래스명 변경**:
  - `ManualControlWidget` → `ManualCtrlWidget`
  - `ManualControlPanel` → `ManualCtrlPanel` (클래스명은 유지, import만 변경)
- **설정 키 변경**:
  - `config/settings.json`: `"manual_control"` → `"manual_ctrl"`
- **모든 참조 업데이트**:
  - `view/sections/main_left_section.py`
  - `presenter/main_presenter.py`
  - `tests/test_view.py`
  - `tests/test_ui_translations.py`

#### 기타 네이밍 개선
- **언어 키 통일**:
  - `recv_lbl_log` → `recv_title`
  - `status_lbl_log` → `system_title`
  - `right_tab_inspector` → `right_tab_packet`
  - `pref_tab_parser` → `pref_tab_packet`
- **QSS 선택자 수정**:
  - `rx_search_prev_btn` → `recv_search_prev_btn`
  - `rx_search_next_btn` → `recv_search_next_btn`

#### DTR/RTS 제거
- **PortSettingsWidget**:
  - `dtr_check`, `rts_check` 체크박스 제거
  - 포트 설정에서 DTR/RTS 옵션 제거
  - 2행 레이아웃 간소화 (Data | Parity | Stop | Flow)

---

### 5. QSS 스타일 개선

#### section-title 클래스 추가
- **common.qss**:
  ```css
  QLabel[class="section-title"] {
      font-weight: bold;
      padding: 0 5px;
      margin-bottom: 2px;
  }
  ```
- **dark_theme.qss**, **light_theme.qss**:
  - `QGroupBox::title`과 `QLabel[class="section-title"]`에 동일한 색상 적용
  - Dark: `#4CAF50` (녹색)
  - Light: `#2196F3` (파란색)
- **적용 위젯**:
  - `ReceivedAreaWidget.recv_log_title`
  - `StatusAreaWidget.status_log_title`

#### QSmartTextEdit 스타일 추가
- **common.qss**: `QSmartTextEdit`를 `QTextEdit`와 동일한 스타일 그룹에 추가
- **dark_theme.qss**, **light_theme.qss**: `QSmartTextEdit` 색상 및 포커스 스타일 적용

---

### 6. 수동 제어 (ManualCtrl) 개선

#### 여러 줄 입력 지원
- **QSmartTextEdit 구현**:
  - `view/pyqt_customs/smart_text_edit.py`: 라인 번호가 표시되는 커스텀 텍스트 에디터
  - `QTextEdit` 상속, `LineNumberArea` 위젯 포함
- **ManualCtrlWidget 적용**:
  - `QSmartLineEdit` → `QSmartTextEdit` 교체
  - `Ctrl+Enter`: 명령 전송
  - `Enter`: 새 줄 추가
  - 플레이스홀더 텍스트 업데이트 ("Ctrl+Enter to send")

---

### 6. 버그 수정 및 개선

#### 싱글톤 패턴 수정
- **문제**: `TypeError: SettingsManager.__new__() takes 1 positional argument but 2 were given`
- **해결**: `__new__(cls, *args, **kwargs)` 시그니처로 변경
- **적용 파일**:
  - `core/settings_manager.py`
  - `view/tools/lang_manager.py`

#### 경로 계산 수정
- **문제**: `Language directory not found: e:\_Python\serial_tool2\view\config\languages`
- **원인**: `view/tools/lang_manager.py`에서 상위 디렉토리 2번만 올라감
- **해결**: 3번 올라가도록 수정 (`os.path.dirname()` 3회 적용)

#### 우측 패널 표시 상태 복원
- **MainWindow.init_ui()**:
  - 설정에서 `right_panel_visible` 읽어서 메뉴 체크 상태 복원
  - `self.menu_bar.set_right_panel_checked(right_panel_visible)`

#### clear_log() 메서드 개선
- **main_window.py**:
  - `isinstance(current_widget, PortPanel)` 체크 제거
  - 직접 `current_widget.received_area.on_clear_recv_log_clicked()` 호출

---

### 7. 통신 구조 리팩토링 (Protocol Agnostic Architecture)
**목표**: Serial 통신에만 종속된 구조를 탈피하여, 향후 SPI/I2C 등 다양한 프로토콜을 수용할 수 있는 유연한 구조로 변경.

- **인터페이스 분리**: `ITransport` (core/interfaces.py) 인터페이스를 정의하여 통신 규약을 추상화함.
- **Transport 계층 구현**: `pyserial` 의존성을 `SerialTransport` (model/transports.py) 클래스로 격리함.
- **Worker 일반화**:
  - `SerialWorker`를 `ConnectionWorker` (model/connection_worker.py)로 이름을 변경하고 리팩토링.
  - Worker는 더 이상 Serial 객체를 직접 생성하지 않고, 외부에서 주입받은 `ITransport` 객체를 사용.
- **Controller 수정**: `PortController`가 `SerialTransport`를 생성하여 Worker에 주입(Dependency Injection)하도록 수정.

---

### 8. UI 성능 최적화 (QSmartListView)
**목표**: 대량의 로그 데이터(초당 수천 라인) 수신 시 발생하는 UI 버벅임(Freezing) 해결.

- **QSmartListView 도입**:
  - 기존 `QTextEdit` 대신 `QListView`와 `QAbstractListModel`을 활용한 커스텀 위젯 구현.
  - 화면에 보이는 부분만 렌더링하여 성능을 극대화함.
  - `view/custom_widgets/smart_list_view.py` 생성.
- **검색 기능 내장**:
  - 리스트 뷰 내부에서 정규식 기반의 `find_next`, `find_prev` 메서드 구현.
  - 검색 결과 하이라이트 및 자동 스크롤 기능 포함.
- **적용**: `ReceivedAreaWidget` 및 `SystemLogWidget`의 로그 뷰어를 `QSmartListView`로 교체 완료.

---

## 파일 변경 사항

### 생성된 파일
- `config.py` - AppConfig 클래스
- `core/port_state.py` - PortState Enum
- `view/sections/__init__.py` - Package init
- `view/dialogs/__init__.py` - Package init (업데이트)

### 삭제된 파일
- `view/widgets/manual_control.py` (→ `manual_ctrl.py`로 대체)
- `view/widgets/main_toolbar.py` (→ `view/sections/main_tool_bar.py`로 이동)

### 주요 수정 파일
- `main.py` - AppConfig 통합, sys.path 개선
- `view/main_window.py` - Import 간결화, PortPanel 제거
- `core/settings_manager.py` - AppConfig 통합, @property 추가
- `view/tools/lang_manager.py` - AppConfig 통합
- `view/tools/theme_manager.py` - AppConfig 통합
- `view/widgets/received_area.py` - rx → recv 네이밍 변경
- `view/widgets/system_log_widget.py` - section-title 스타일 적용
- `view/widgets/port_settings.py` - DTR/RTS 제거
- `view/dialogs/preferences_dialog.py` - Parser 탭 추가
- `config/languages/en.json` - Parser 키 추가
- `config/languages/ko.json` - Parser 키 추가
- `resources/themes/common.qss` - section-title 스타일
- `resources/themes/dark_theme.qss` - Port state, section-title 색상
- `resources/themes/light_theme.qss` - Port state, section-title 색상

---

## 문서 업데이트

### doc/task.md
- Phase 2 완료 항목 추가 (ReceivedArea, PortState, Parser 탭, AppConfig, import 개선)
- Phase 3 상태를 "진행 중"으로 변경
- SettingsManager, PortState, AppConfig 완료 표시

### doc/implementation_plan.md
- 최종 업데이트 날짜: 2025-12-10
- 핵심 목표에 "중앙 집중식 경로 관리" 추가
- 프로젝트 구조 업데이트 (AppConfig, __init__.py, 파일명 수정)

### README.md
- 최종 업데이트 날짜 추가
- 주요 기능 업데이트 (PortState, AppConfig, Package-level imports)
- 용어 통일 (커맨드 → 매크로, DTR/RTS 제거)

---

## 다음 단계

### 우선순위 높음
1. **Model 계층 구현**:
   - `SerialWorker` (QThread 기반 시리얼 I/O)
   - `PortController` (포트 라이프사이클 관리)
   - `PacketParser` 시스템

2. **Presenter 계층 완성**:
   - `PortPresenter` 완성 (포트 열기/닫기)
   - `MacroPresenter` 구현
   - `FilePresenter` 구현

### 우선순위 중간
3. **Core 유틸리티**:
   - `RingBuffer` 구현
   - `ThreadSafeQueue` 구현
   - `EventBus` 구현

4. **자동화 엔진**:
   - `MacroRunner` 구현
   - `FileTransferEngine` 구현

---

## 참고 사항

- **MVP 패턴 준수**: View는 SettingsManager에 직접 접근하지 않고 Presenter를 통해 데이터 전달
- **중앙 경로 관리**: 모든 리소스 경로는 AppConfig를 통해 관리
- **네이밍 일관성**: `recv`, `manual_ctrl` 등 약어 사용 시 일관성 유지
- **하위 호환성**: AppConfig 없이도 기존 방식으로 동작 가능 (fallback 메커니즘)
