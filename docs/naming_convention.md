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

| Context | 설명 | 예시 |
|---------|------|------|
| `global` | 앱 전역 공유 | `global_btn_ok`, `global_btn_cancel` |
| `main` | 메인 윈도우 | `main_menu_file`, `main_title` |
| `port` | 포트 설정 위젯 | `port_lbl_baudrate`, `port_btn_connect` |
| `manual_ctrl` | 수동 제어 위젯 | `manual_ctrl_btn_send`, `manual_ctrl_chk_hex` |
| `cmd` | 명령 리스트/제어 | `cmd_btn_add`, `cmd_col_command` |
| `cmd_list` | 명령 리스트 패널 | `cmd_list_col_delay` |
| `recv` | 수신 영역 위젯 | `recv_btn_clear`, `recv_chk_timestamp` |
| `pref` | Preferences 다이얼로그 | `pref_lbl_font_size`, `pref_tab_general` |
| `about` | About 다이얼로그 | `about_title`, `about_lbl_version` |
| `font` | 폰트 설정 다이얼로그 | `font_grp_fixed`, `font_btn_reset` |
| `inspector` | 패킷 인스펙터 | `inspector_col_field` |
| `file_prog` | 파일 전송 진행 | `file_prog_status_completed` |

### 2.3 Type (UI 요소 타입)

| Type | 설명 | 예시 |
|------|------|------|
| `title` | 윈도우/다이얼로그 제목 | `main_title`, `about_title` |
| `menu` | 메뉴 항목 | `main_menu_file`, `main_menu_edit` |
| `btn` | 버튼 | `port_btn_connect`, `recv_btn_clear` |
| `lbl` | 라벨 | `port_lbl_port`, `pref_lbl_theme` |
| `chk` | 체크박스 | `manual_ctrl_chk_rts`, `recv_chk_hex` |
| `combo` | 콤보박스 | `port_combo_baud` |
| `input` | 입력 필드 | `manual_ctrl_input_cmd` |
| `grp` | 그룹박스 | `cmd_grp_auto`, `font_grp_fixed` |
| `tab` | 탭 | `pref_tab_general`, `right_tab_inspector` |
| `col` | 테이블 컬럼 | `cmd_list_col_command`, `inspector_col_field` |
| `dialog` | 다이얼로그 | `manual_ctrl_dialog_select_file` |
| `txt` | 텍스트 영역 | `recv_txt_log` |
| `status` | 상태 메시지 | `file_prog_status_sending` |
| `msg` | 일반 메시지 | `global_msg_saved` |

### 2.4 Suffix (선택적 속성)

| Suffix | 설명 | 예시 |
|--------|------|------|
| `_tooltip` | 툴팁 텍스트 | `port_btn_connect_tooltip` |
| `_placeholder` | 플레이스홀더 텍스트 | `manual_ctrl_input_cmd_placeholder` |

### 2.5 올바른 예시

```python
# ✅ 올바른 예시
"port_btn_connect"                    # 포트 연결 버튼
"port_combo_baud_tooltip"             # 보드레이트 콤보박스의 툴팁
"cmd_list_col_command"                # 명령 리스트의 명령 컬럼
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
"cmd_list_dialog_title_save"               # 저장 다이얼로그 제목
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
python tools/manage_lang_keys.py
```

이 도구는:
- 코드에서 사용된 모든 언어 키 추출
- 누락된 키 감지
- 사용되지 않는 키 식별
- 템플릿 파일 자동 생성

---

## 5. 요약

| 항목 | 규칙 | 예시 |
|------|------|------|
| 클래스 | PascalCase | `MainWindow` |
| 함수/메서드 | snake_case | `connect_port()` |
| 변수 | snake_case | `port_name` |
| 상수 | UPPER_CASE | `DEFAULT_BAUDRATE` |
| 비공개 멤버 | _prefix | `_internal_method()` |
| 언어 키 | [context]_[type]_[name] | `port_btn_connect` |

**핵심 원칙**: 명확하고, 일관되며, 검색 가능한 이름을 사용하세요!
