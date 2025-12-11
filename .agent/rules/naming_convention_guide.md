---
trigger: always_on
---

# SerialTool Naming Convention Guide

이 문서는 SerialTool 프로젝트의 명명 규칙을 정의합니다. 일관된 명명 규칙을 통해 코드의 가독성과 유지보수성을 향상시킵니다.

## 1. 기본 명명 규칙

### 1.1 클래스 (Classes)
**규칙**: `PascalCase` - 각 단어의 첫 글자를 대문자로 작성

**예시**:
```python
class SerialManager:
    pass

class MainWindow:
    pass

class PortController:
    pass
```

### 1.2 함수 및 메서드 (Functions/Methods)
**규칙**: `snake_case` - 소문자와 밑줄 사용

**예시**:
```python
def connect_port():
    pass

def update_ui():
    pass

def get_available_ports():
    pass
```

### 1.3 변수 (Variables)
**규칙**: `snake_case` - 소문자와 밑줄 사용

**예시**:
```python
port_name = "COM1"
is_connected = False
baudrate = 115200
```

### 1.4 상수 (Constants)
**규칙**: `UPPER_CASE` - 모두 대문자와 밑줄 사용

**예시**:
```python
DEFAULT_BAUDRATE = 115200
MAX_RETRIES = 3
TIMEOUT_SECONDS = 5
```

### 1.5 비공개 멤버 (Private Members)
**규칙**: `_prefix` - 밑줄 접두사 사용

**예시**:
```python
class Example:
    def __init__(self):
        self._internal_buffer = []
        self._helper_method()

    def _helper_method(self):
        pass
```

---

## 2. 언어 키 네이밍 규칙 (Language Keys)

다국어 지원을 위한 언어 키는 다음 형식을 **엄격히** 준수해야 합니다.

### 2.1 기본 형식
**패턴**: `[context]_[type]_[name]`

| 요소 | 설명 | 필수 |
|------|------|------|
| **context** | 위젯/컴포넌트 이름 | ✅ 필수 |
| **type** | UI 요소 타입 | ✅ 필수 |
| **name** | 구체적인 기능/용도 | ✅ 필수 |

### 2.2 Context (위젯/섹션)

| Context | 설명 | 관련 클래스 | 예시 |
|---------|------|------------|------|
| **`global`** | 앱 전역 공유 | - | `global_btn_ok`, `global_msg_saved` |
| **`main`** | 메인 윈도우 | `MainWindow` | `main_title`, `main_menu_file` |
| **`toolbar`** | 메인 툴바 | `MainToolBar` | `toolbar_act_open`, `toolbar_act_settings` |
| **`status`** | 메인 상태바 | `MainStatusBar` | `status_msg_ready`, `status_lbl_port` |
| **`port`** | 포트 설정 패널 | `PortSettingsWidget` | `port_btn_connect`, `port_combo_baud` |
| **`rx`** | 수신 로그 영역 | `ReceivedAreaWidget` | `rx_btn_clear`, `rx_chk_timestamp` |
| **`manual_ctrl`**| 수동 제어/전송 | `ManualCtrlWidget` | `manual_ctrl_btn_send`, `manual_ctrl_chk_hex` |
| **`file_prog`** | 파일 전송 진행 | `FileProgressWidget` | `file_prog_bar_transfer`, `file_prog_btn_cancel` |
| **`macro_list`**| 매크로 리스트 | `MacroListWidget` | `macro_list_col_command`, `macro_list_btn_add` |
| **`macro_ctrl`**| 매크로 제어 | `MacroCtrlWidget` | `macro_ctrl_spin_repeat`, `macro_ctrl_btn_start` |
| **`inspector`** | 패킷 인스펙터 | `PacketInspectorWidget`| `inspector_tree_packet`, `inspector_col_value` |
| **`system`** | 시스템 로그 | `SystemLogWidget` | `system_list_log`, `system_lbl_title` |
| **`pref`** | 설정 다이얼로그 | `PreferencesDialog` | `pref_tab_general`, `pref_chk_auto_update` |
| **`font`** | 폰트 설정 | `FontSettingsDialog` | `font_spin_size`, `font_combo_family` |
| **`about`** | 정보 다이얼로그 | `AboutDialog` | `about_lbl_version`, `about_btn_close` |

### 2.3 Type (UI 요소 타입)

| Type | 설명 | PyQt 위젯 예시 | 예시 |
|------|------|---------------|------|
| `title` | 윈도우/다이얼로그 제목 | - | `main_title`, `about_title` |
| `menu` | 메뉴 그룹 | `QMenu` | `main_menu_file` |
| `act` | 액션/명령 | `QAction` | `toolbar_act_open`, `main_act_copy` |
| `btn` | 버튼 | `QPushButton` | `port_btn_connect`, `rx_btn_clear` |
| `lbl` | 라벨 | `QLabel` | `port_lbl_port`, `pref_lbl_theme` |
| `chk` | 체크박스 | `QCheckBox` | `manual_ctrl_chk_rts`, `rx_chk_hex` |
| `combo` | 콤보박스 | `QComboBox` | `port_combo_baud` |
| `input` | 문자열 입력 필드 | `QLineEdit` | `manual_ctrl_input_cmd` |
| `spin` | 숫자 입력 필드 | `QSpinBox` | `macro_ctrl_spin_repeat`, `font_spin_size` |
| `txt` | 멀티라인 텍스트 영역 | `QTextEdit` | `rx_txt_log` |
| `grp` | 그룹박스 | `QGroupBox` | `cmd_grp_auto`, `font_grp_fixed` |
| `tab` | 탭 | `QTabWidget` | `pref_tab_general`, `right_tab_inspector` |
| `table` | 테이블 뷰 | `QTableView` | `macro_list_table` |
| `tree` | 트리 뷰 | `QTreeWidget` | `inspector_tree_packet` |
| `list` | 리스트 뷰 | `QListView` | `system_list_log` |
| `col` | 테이블/트리 컬럼 | `Header` | `macro_list_col_command`, `inspector_col_field` |
| `dialog` | 다이얼로그 | `QDialog` | `manual_ctrl_dialog_select_file` |
| `status` | 상태 메시지 | - | `file_prog_status_sending` |
| `msg` | 일반 메시지/알림 | `QMessageBox` | `global_msg_saved` |

### 2.4 Suffix (선택적 속성)

UI 요소의 기본 텍스트 외에 부가적인 정보를 정의할 때, 키 이름의 **맨 뒤**에 붙여 사용합니다.

| Suffix | 설명 | 대상 위젯 | 예시 |
|--------|------|-----------|------|
| **`_tooltip`** | 마우스 오버 시 표시되는 도움말 | 모든 위젯 | `port_btn_connect_tooltip`<br>`rx_chk_timestamp_tooltip`<br>`macro_list_btn_add_row_tooltip` |
| **`_placeholder`** | 입력 필드에 표시되는 안내 문구 | `input`, `txt`, `spin` | `manual_ctrl_input_cmd_placeholder`<br>`rx_input_search_placeholder`<br>`file_prog_lbl_eta_placeholder` |

> **Note**: Suffix는 반드시 `[context]_[type]_[name]` 뒤에 위치해야 합니다.
> * ❌ `port_tooltip_btn_connect` (순서 틀림)
> * ✅ `port_btn_connect_tooltip` (올바름)

### 2.5 올바른 예시

```python
# ✅ 올바른 예시
"port_btn_connect"                    # 포트 연결 버튼
"port_combo_baud_tooltip"             # 보드레이트 콤보박스의 툴팁
"macro_list_col_command"                # 명령 리스트의 명령 컬럼
"manual_ctrl_grp_control"             # 수동 제어의 제어 그룹박스
"recv_txt_log_placeholder"            # 수신 영역의 로그 텍스트 플레이스홀더
"about_lbl_app_name"                  # About 다이얼로그의 앱 이름 라벨
"font_grp_fixed_tooltip"              # 폰트 설정의 고정폭 그룹박스 툴팁
"pref_tab_general"                    # Preferences의 일반 탭
"file_prog_status_completed"          # 파일 전송 완료 상태
```

### 2.6 잘못된 예시

```python
# ❌ 잘못된 예시
"port_baud_combo_tooltip"       # type이 name 뒤에 위치
"port_settings"                 # type 누락 (port_grp_settings가 올바름)
"inspector_field"               # type 누락 (inspector_col_field가 올바름)
"save"                          # context와 type 누락
"btn_save"                      # context 누락
"port_baudrate"                 # type 누락
```

### 2.7 특수 케이스

#### 다이얼로그 타이틀
**패턴**: `[context]_dialog_title_[purpose]` 또는 `[context]_dialog_[action]_title`

```python
"manual_ctrl_dialog_save_log_title"        # 로그 저장 다이얼로그 제목
"pref_dialog_select_dir"                   # 디렉토리 선택 다이얼로그
"macro_list_dialog_title_save"               # 저장 다이얼로그 제목
```

#### 파일 필터
**패턴**: `[context]_dialog_file_filter_[extension]`

```python
"manual_ctrl_dialog_file_filter_txt"       # .txt 파일 필터
"manual_ctrl_dialog_file_filter_all"       # 모든 파일 필터
```

#### 상태 메시지
**패턴**: `[context]_status_[state]`

```python
"file_prog_status_completed"               # 완료 상태
"file_prog_status_sending"                 # 전송 중 상태
"file_prog_status_failed"                  # 실패 상태
"status_ready"                             # 준비 상태
```

---

## 3. 적용 가이드

### 3.1 새 UI 요소 추가 시
1. Context 확인 (어느 위젯/다이얼로그인가?)
2. Type 결정 (버튼? 라벨? 체크박스?)
3. Name 정의 (무엇을 하는가?)
4. 필요시 Suffix 추가 (툴팁? 플레이스홀더?)

### 3.2 기존 코드 리팩토링 시
- 규칙에 맞지 않는 키를 발견하면 수정
- 일괄 변경 시 `tools/manage_lang_keys.py` 활용

### 3.3 일관성 유지
- 비슷한 기능은 비슷한 이름 사용
- 예: 모든 "연결" 버튼은 `*_btn_connect` 패턴

---

## 4. 참고사항

### 4.1 왜 이러한 규칙을 따라야 하는가?
- **검색성**: 일관된 패턴으로 쉽게 검색 가능
- **가독성**: 키 이름만으로 UI 요소 위치와 타입 파악
- **자동화**: 스크립트로 키 검증 및 자동 생성 가능
- **협업**: 팀원 간 명확한 소통

### 4.2 도구 활용
프로젝트에는 언어 키 관리를 위한 도구가 있습니다:
```bash
python managers/manage_lang_keys.py
```

이 도구는:
- 코드에서 사용된 모든 언어 키 추출
- 누락된 키 감지
- 사용되지 않는 키 식별
- 템플릿 파일 자동 생성

---

## 5. UI 위젯 변수명 (Widget Variable Names)

PyQt5 위젯 변수명은 **`[기능]_[위젯약어]`** 형식을 사용합니다. (예: `connect_btn`, `rx_log_list`)

### 5.1 표준 약어 규칙 (Standard Suffixes)

| UI 요소 | 약어 | 예시 | 비고 |
|---------|------|------|------|
| **Button** | `_btn` | `send_btn`, `clear_btn` | QPushButton |
| **Label** | `_lbl` | `status_lbl`, `port_lbl` | QLabel |
| **CheckBox** | `_chk` | `hex_chk`, `timestamp_chk` | QCheckBox |
| **ComboBox** | `_combo` | `port_combo`, `baud_combo` | QComboBox |
| **SpinBox** | `_spin` | `repeat_count_spin`, `font_size_spin` | QSpinBox |
| **LineEdit** | `_input` | `search_input`, `filter_input` | QLineEdit (단일 행 입력) |
| **TextEdit** | `_txt` | `manual_cmd_txt`, `preview_txt` | QTextEdit, QPlainTextEdit, QSmartTextEdit |
| **ListView** | `_list` | `rx_log_list`, `system_log_list` | QListView, QSmartListView |
| **TableView** | `_table` | `macro_table` | QTableView |
| **TreeWidget** | `_tree` | `packet_tree` | QTreeWidget |
| **GroupBox** | `_grp` | `control_grp`, `file_grp` | QGroupBox |
| **Splitter** | `_splitter`| `main_splitter` | QSplitter |
| **Stacked** | `_stack` | `settings_stack` | QStackedWidget |
| **TabWidget** | `_tabs` | `port_tabs`, `main_tabs` | QTabWidget (복수형 권장) |
| **Action** | `_act` | `open_act`, `exit_act` | QAction (메뉴/툴바 항목) |

### 5.2 복합 위젯 (전체 이름 사용)

다음은 약어가 아닌 전체 이름을 사용합니다:
- `menu_bar` (QMenuBar)
- `status_bar` (QStatusBar)
- `progress_bar` (QProgressBar)

### 5.3 잘못된 예시

```python
# ❌ 잘못된 예시
self.reset_button = QPushButton()  # → reset_btn
self.title_label = QLabel()  # → title_lbl
self.option_group = QGroupBox()  # → option_grp
self.log_edit = QTextEdit()  # → status_log_list

# ✅ 올바른 예시
self.reset_btn = QPushButton()
self.title_lbl = QLabel()
self.option_grp = QGroupBox()
self.status_log_list = QTextEdit()
```

---

## 6. 시그널 및 핸들러 (Signals & Handlers)

### 6.1 시그널 네이밍

| 패턴 | 용도 | 예시 |
|------|------|------|
| `[대상]_changed` | 값/상태 변경 | `theme_changed`, `language_changed` |
| `[동작]_requested` | 사용자 요청 | `manual_cmd_send_requested`, `exit_requested` |
| `[대상]_[동사]ed` | 완료 알림 | `data_received`, `port_opened` |
| `[대상]_selected` | 선택 이벤트 | `transfer_file_selected`, `item_selected` |
| `[대상]_added` | 추가 이벤트 | `tab_added`, `row_added` |
| `[대상]_removed` | 제거 이벤트 | `tab_removed`, `row_removed` |

### 6.2 이벤트 핸들러 네이밍

| 패턴 | 용도 | 예시 |
|------|------|------|
| `on_[위젯]_[동작]` | 위젯명이 불명확할 때 | `on_send_manual_cmd_clicked` |
| `on_[동작]` | 위젯명이 명확할 때 | `on_send_clicked` (send_btn만 있는 경우) |
| `on_[대상]_[동작]` | 상태 변경 핸들러 | `on_language_changed` |
| `_on_[대상]_[동작]` | 내부 핸들러 | `_on_port_changed` |

**참고**: 위젯명이 문맥상 명확한 경우 `_btn`, `_chk` 등의 접미사를 생략할 수 있습니다. 하지만 가급적 구체적인 이름을 권장합니다.

---

## 7. 클래스 접미사 (Class Suffixes)

| 타입 | 접미사 | 예시 |
|------|--------|------|
| 독립 위젯 | `Widget` | `PortSettingsWidget`, `ManualControlWidget` |
| 복합 패널 | `Panel` | `PortPanel`, `MacroListPanel` |
| 다이얼로그 | `Dialog` | `PreferencesDialog`, `AboutDialog` |
| 레이아웃 영역 | `Section` | `LeftSection`, `RightSection` |
| 관리 클래스 | `Manager` | `SettingsManager`, `LanguageManager` |

---

## 8. 요약

| 항목 | 규칙 | 예시 |
|------|------|------|
| 클래스 | PascalCase | `MainWindow` |
| 함수/메서드 | snake_case | `connect_port()` |
| 변수 | snake_case | `port_name` |
| 상수 | UPPER_CASE | `DEFAULT_BAUDRATE` |
| 비공개 멤버 | _prefix | `_internal_method()` |
| 언어 키 | [context]_[type]_[name] | `port_btn_connect` |
| UI 위젯 변수 | [용도]_[약어] | `send_btn`, `status_lbl` |

**핵심 원칙**: 명확하고, 일관되며, 검색 가능한 이름을 사용하세요!