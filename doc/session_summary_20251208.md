# 세션 요약 - 2025년 12월 8일

## 📋 작업 개요

이번 세션에서는 사용자 요청에 따라 UI/UX 개선, 버그 수정, 그리고 새로운 위젯 기능을 구현했습니다. 주요 작업은 다음과 같습니다:

1. **SmartNumberEdit 위젯 생성**: HEX 모드 지원 입력 필드
2. **PortTabWidget 생성**: 포트 탭 관리 캡슐화
3. **CommandListWidget 버그 수정**: Send 버튼 상태 유지
4. **테마별 아이콘 지원**: SVG 아이콘 로딩
5. **포트 탭 닫기 버튼 수정**: 탭 삭제 문제 해결
6. **포트 탭 이름 수정 기능**: 커스텀 이름 지정
7. **순환 import 문제 해결**: TYPE_CHECKING 활용
8. **탭 삭제 시 새 탭 생성 버그 수정**: 시그널 차단 및 최소 탭 유지
9. **언어 확장성 개선**: 하드코딩된 언어 비교 제거
10. **UI 아이콘 수정**: 버튼 objectName 불일치 해결
11. **UI/시그널/메서드 네이밍 리팩토링**: 구체적이고 일관된 이름으로 변경

10. **UI 아이콘 수정**: 버튼 objectName 불일치 해결
11. **UI/시그널/메서드 네이밍 리팩토링**: 구체적이고 일관된 이름으로 변경

---

## ✨ 주요 변경 사항

### 11. UI 요소 및 시그널/메서드 네이밍 리팩토링

**파일**: `manual_control.py`, `received_area.py`, `tx_panel.py`, `command_control.py`, `main_presenter.py` 등

**목적**: 모호한 변수명(`send_btn` 등)을 구체적인 이름(`send_manual_cmd_btn` 등)으로 변경하여 코드 가독성과 유지보수성을 향상시킴.

**주요 변경 내용**:
- **UI 위젯**:
  - `send_btn` → `send_manual_cmd_btn` (Manual Control)
  - `send_btn` → `send_text_data_btn` (Tx Panel)
  - `clear_btn` → `clear_rx_log_btn` (Received Area)
  - `run_once_btn` → `cmd_run_once_btn` (Command Control)
- **시그널**:
  - `send_command_requested` → `manual_cmd_send_requested`
  - `run_single_requested` → `cmd_run_single_requested`
- **메서드**:
  - `on_send_clicked` → `on_send_manual_cmd_clicked`
  - `find_next` → `on_rx_search_next_clicked`

**문서 업데이트**:
- `guide/naming_convention.md`: 시그널 및 핸들러 네이밍 규칙 예시 추가

### 12. PreferencesDialog 리팩토링

**파일**: `view/dialogs/preferences_dialog.py`

**목적**: 설정 로드/저장 로직을 개선하고 MVP 아키텍처를 엄격히 준수하도록 리팩토링.

**변경 내용**:
- **View (`PreferencesDialog`)**:
  - `load_settings`: `SettingsManager` 직접 사용
  - `apply_settings`: `.lower()`, `int()` 등 데이터 변환 로직 제거, 원본 데이터 시그널 전송
- **View (`MainWindow`)**:
  - `preferences_save_requested` 시그널 추가
  - 다이얼로그 시그널을 Presenter로 전달 (`apply_preferences` 메서드 제거)
- **Presenter (`MainPresenter`)**:
  - `on_preferences_save_requested` 핸들러 구현
  - 데이터 검증, 변환, `SettingsManager` 업데이트, UI 갱신 로직 통합

### 1. SmartNumberEdit 위젯 생성

**파일**: `view/widgets/common/smart_number_edit.py`

**목적**: `ManualControlWidget`의 입력 필드에서 HEX 모드와 일반 텍스트 모드를 지원하는 스마트 입력 위젯

**주요 기능**:
- HEX 모드 활성화 시 0-9, A-F, 공백만 입력 허용
- 소문자 입력 시 자동으로 대문자로 변환
- `QRegExpValidator`를 사용한 입력 검증
- `set_hex_mode(bool)` 메서드로 모드 전환

**적용**:
- `ManualControlWidget`에서 `QLineEdit` 대신 `SmartNumberEdit` 사용
- HEX 체크박스와 연동하여 자동 모드 전환

### 2. PortTabWidget 위젯 생성

**파일**: `view/widgets/port_tab_widget.py`

**목적**: 포트 탭 관리 로직을 캡슐화하여 코드 재사용성 및 유지보수성 향상

**주요 기능**:
- 탭 추가/삭제 관리
- 플러스(+) 탭 기능
- 테마별 아이콘 적용
- 탭 더블클릭 시 이름 수정

**변경 사항**:
- `LeftSection`에서 `QTabWidget` → `PortTabWidget` 사용
- 탭 관리 메서드들을 `PortTabWidget`으로 이동

### 3. CommandListWidget Send 버튼 상태 버그 수정

**파일**: `view/widgets/command_list.py`

**문제**: 행을 이동할 때 `_set_send_button`을 호출하여 새 버튼을 생성하면서, 버튼의 활성화 상태가 초기값(비활성화)으로 리셋되는 버그

**해결**:

```python
def _move_row(self, source_row: int, dest_row: int) -> None:
    # 0. 이동 전 버튼 상태 저장
    is_enabled = False
    index = self.cmd_table_model.index(source_row, 6)
    widget = self.cmd_table.indexWidget(index)
    if widget:
        btn = widget.findChild(QPushButton)
        if btn:
            is_enabled = btn.isEnabled()

    # 1-2. 행 이동
    items = self.cmd_table_model.takeRow(source_row)
    self.cmd_table_model.insertRow(dest_row, items)

    # 3. 위젯(버튼) 복구
    self._set_send_button(dest_row)

    # 4. 버튼 상태 복원
    new_index = self.cmd_table_model.index(dest_row, 6)
    new_widget = self.cmd_table.indexWidget(new_index)
    if new_widget:
        new_btn = new_widget.findChild(QPushButton)
        if new_btn:
            new_btn.setEnabled(is_enabled)
```

### 4. 테마별 SVG 아이콘 지원

**파일**: `view/theme_manager.py`

**추가된 메서드**:
```python
def get_icon(self, name: str) -> QIcon:
    """
    현재 테마에 맞는 아이콘을 반환합니다.
    아이콘 파일명 규칙: {name}_{theme}.svg
    """
    icon_path = f"resources/icons/{name}_{self._current_theme}.svg"

    if not os.path.exists(icon_path):
        fallback_path = f"resources/icons/{name}.svg"
        if os.path.exists(fallback_path):
            return QIcon(fallback_path)
        return QIcon()

    return QIcon(icon_path)
```

**생성된 아이콘**:
- `resources/icons/add_dark.svg`: 다크 테마용 (흰색)
- `resources/icons/add_light.svg`: 라이트 테마용 (검은색)

### 5. 포트 탭 닫기 버튼 문제 수정

**문제**: `insertTab`을 사용하여 플러스 탭 앞에 새 탭을 삽입하면, 인덱스가 밀리면서 닫기 버튼 상태가 꼬이는 현상

**해결 방법**:
```python
def add_new_port_tab(self) -> PortPanel:
    self.blockSignals(True)
    try:
        # 1. 기존 플러스 탭 제거
        count = self.count()
        if count > 0:
            self.removeTab(count - 1)

        # 2. 새 패널 추가 (닫기 버튼 자동 생성됨)
        panel = PortPanel()
        initial_title = panel.get_tab_title()
        self.addTab(panel, initial_title)

        # 3. 플러스 탭 다시 추가
        self.add_plus_tab()

        # 4. 새 탭으로 포커스 이동
        new_tab_index = self.count() - 2
        self.setCurrentIndex(new_tab_index)
    finally:
        self.blockSignals(False)

    self.tab_added.emit(panel)
    return panel
```

이 방식은 `insertTab` 대신 플러스 탭을 제거하고 재추가하여 모든 탭이 올바른 닫기 버튼을 갖도록 보장합니다.

### 6. 포트 탭 이름 수정 기능

**파일**: `view/panels/port_panel.py`, `view/widgets/port_tab_widget.py`

**기능**:
- 탭 제목 형식: `[커스텀명]:포트명`
- 탭 더블클릭 시 커스텀 이름 수정 다이얼로그 표시
- 포트 변경 시 자동으로 탭 제목 업데이트
- 커스텀 이름을 설정 파일에 저장/복원

**구현**:

**PortPanel**:
```python
class PortPanel(QWidget):
    tab_title_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.custom_name = "Port"
        self.init_ui()
        self.port_settings.port_combo.currentTextChanged.connect(self._on_port_changed)

    def get_tab_title(self) -> str:
        port_name = self.get_port_name()
        if port_name:
            return f"{self.custom_name}:{port_name}"
        else:
            return self.custom_name

    def set_custom_name(self, name: str) -> None:
        self.custom_name = name
        self.update_tab_title()
```

**PortTabWidget**:
```python
def eventFilter(self, obj, event):
    """탭바 더블클릭 이벤트를 감지합니다."""
    if obj == self.tabBar() and event.type() == event.MouseButtonDblClick:
        index = self.tabBar().tabAt(event.pos())
        if index >= 0 and index < self.count() - 1:
            self.edit_tab_name(index)
            return True
    return super().eventFilter(obj, event)

def edit_tab_name(self, index: int) -> None:
    widget = self.widget(index)
    if not isinstance(widget, PortPanel):
        return

    current_name = widget.get_custom_name()
    new_name, ok = QInputDialog.getText(
        self, "Edit Tab Name", "Enter custom name:", text=current_name
    )

    if ok and new_name and new_name != current_name:
        widget.set_custom_name(new_name)
```

### 7. 순환 import 문제 해결

**파일**: `view/widgets/port_tab_widget.py`

**문제**: `PortTabWidget`이 `PortPanel`을 import하고, `PortPanel`이 다시 다른 모듈을 import하면서 순환 import 발생

**해결 방법**:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from view.panels.port_panel import PortPanel

class PortTabWidget(QTabWidget):
    tab_added = pyqtSignal(object)  # PortPanel 대신 object 사용

    def add_new_port_tab(self) -> "PortPanel":
        from view.panels.port_panel import PortPanel  # 런타임 import
        panel = PortPanel()
        # ...
```

**핵심**:
- `TYPE_CHECKING`을 사용하여 타입 힌트만 import
- 실제 런타임에는 필요한 곳에서만 import
- 시그널은 `object` 타입 사용

### 8. 탭 삭제 시 새 탭 생성 버그 수정

**파일**: `view/widgets/port_tab_widget.py`

**문제**:
- 플러스 탭 바로 왼쪽 탭을 삭제하면 `on_tab_changed` 시그널이 발생
- 현재 탭 인덱스가 플러스 탭 인덱스와 같아져 새 탭이 생성됨

**해결 방법**:
```python
def close_port_tab(self, index: int) -> None:
    """탭 닫기 요청 처리"""
    # 마지막 탭(+)은 닫을 수 없음
    if index == self.count() - 1:
        return

    # 최소 1개의 포트 탭은 유지 (플러스 탭 제외)
    if self.count() <= 2:
        return

    # 시그널 차단하여 탭 삭제 시 on_tab_changed가 호출되지 않도록 함
    self.blockSignals(True)
    try:
        self.removeTab(index)

        # 삭제 후 적절한 탭으로 포커스 이동
        if self.count() > 1:
            new_index = max(0, index - 1)
            self.setCurrentIndex(new_index)
    finally:
        self.blockSignals(False)
```

**개선 사항**:
- 시그널 차단으로 `on_tab_changed` 호출 방지
- 삭제 후 플러스 탭이 아닌 일반 탭으로 포커스 이동
- 최소 1개의 포트 탭 유지 로직 추가


### 9. 언어 확장성 개선

**파일**: `view/language_manager.py`

**문제**: 언어별로 하드코딩된 비교 방식 (`"en"`, `"ko"`)은 새 언어가 추가될 때마다 코드를 수정해야 하는 확장성 문제

**개선 사항**:

```python
def get_text(self, key: str, lang_code: Optional[str] = None) -> str:
    """지정된 언어(또는 현재 언어)에 맞는 텍스트를 반환합니다."""
    target_lang = lang_code if lang_code else self.current_language
    # ...

def get_supported_languages(self) -> list:
    """지원되는 모든 언어 코드 목록을 반환합니다."""
    return list(self.resources.keys())

def text_matches_key(self, text: str, key: str) -> bool:
    """주어진 텍스트가 특정 키의 어떤 언어 번역과 일치하는지 확인합니다."""
    for lang_code in self.get_supported_languages():
        if text == self.get_text(key, lang_code):
            return True
    return False
```

**적용 파일**:
- `view/widgets/manual_control.py` (L170-171)
- `view/widgets/main_status_bar.py` (L31-32)
- `view/widgets/file_progress.py` (L70-71, L77-78)

**변경 전**:
```python
if self.file_path_lbl.text() == language_manager.get_text("key", "en") or \
   self.file_path_lbl.text() == language_manager.get_text("key", "ko"):
```

**변경 후**:
```python
if language_manager.text_matches_key(self.file_path_lbl.text(), "key"):
```

### 10. UI 아이콘 표시 문제 수정

**파일**: `resources/themes/dark_theme.qss`, `resources/themes/light_theme.qss`

**문제**: 버튼의 objectName과 QSS 선택자가 일치하지 않아 아이콘이 표시되지 않음

**불일치 목록**:
| 코드 objectName | QSS 선택자 (이전) | QSS 선택자 (수정) |
|----------------|------------------|------------------|
| `add_cmd_btn` | `add_btn` | `add_cmd_btn` |
| `del_cmd_btn` | `del_btn` | `del_cmd_btn` |
| `up_cmd_btn` | `up_btn` | `up_cmd_btn` |
| `down_cmd_btn` | `down_btn` | `down_cmd_btn` |
| `search_prev_btn` | `find_prev_btn` | `search_prev_btn` |
| `search_next_btn` | `find_next_btn` | `search_next_btn` |

**수정 내용**:
```css
/* Dark Theme */
QPushButton#add_cmd_btn { qproperty-icon: url(resources/icons/add_white.svg); }
QPushButton#del_cmd_btn { qproperty-icon: url(resources/icons/delete_white.svg); }
QPushButton#up_cmd_btn { qproperty-icon: url(resources/icons/up_white.svg); }
QPushButton#down_cmd_btn { qproperty-icon: url(resources/icons/down_white.svg); }
QPushButton#search_prev_btn { qproperty-icon: url(resources/icons/find_prev_white.svg); }
QPushButton#search_next_btn { qproperty-icon: url(resources/icons/find_next_white.svg); }

/* Light Theme */
QPushButton#add_cmd_btn { qproperty-icon: url(resources/icons/add_black.svg); }
/* ... (동일한 패턴) */
```

---

## 📝 수정된 파일 목록

### 신규 생성
- `view/widgets/common/smart_number_edit.py`
- `view/widgets/port_tab_widget.py`
- `resources/icons/add_dark.svg`
- `resources/icons/add_light.svg`

### 수정
- `view/widgets/command_list.py`
- `view/panels/port_panel.py`
- `view/sections/left_section.py`
- `view/widgets/manual_control.py`
- `view/widgets/main_status_bar.py`
- `view/widgets/file_progress.py`
- `view/language_manager.py`
- `view/theme_manager.py`
- `resources/themes/dark_theme.qss`
- `resources/themes/light_theme.qss`
- `core/settings_manager.py`
- `view/dialogs/preferences_dialog.py`
- `view/main_window.py`

### 문서
- `doc/CHANGELOG.md`
- `doc/session_summary_20251208.md`

---

## 🎯 작업 결과

### 개선 사항
1. ✅ **사용자 경험 향상**: HEX 모드 입력 제한으로 오입력 방지, 탭 이름 커스터마이징 가능
2. ✅ **코드 품질 개선**: 위젯 캡슐화로 재사용성 및 유지보수성 향상
3. ✅ **테마 일관성**: 모든 UI 요소에 테마가 올바르게 적용됨
4. ✅ **안정성 향상**: 버튼 상태 및 탭 닫기 버그 수정

### 해결된 문제
1. ✅ CommandListWidget 행 이동 시 Send 버튼 상태 초기화 버그
2. ✅ 포트 탭 추가 시 닫기 버튼이 사라지는 버그
3. ✅ 설정 키 불일치 (`menu_theme` vs `theme`)
4. ✅ ThemeManager에서 QIcon import 누락
5. ✅ PortTabWidget과 PortPanel 간 순환 import 문제
6. ✅ 탭 삭제 시 새 탭이 생성되는 버그
7. ✅ 마지막 포트 탭 삭제 방지 로직 추가
8. ✅ 언어별 하드코딩 문제 (확장성 개선)
9. ✅ UI 버튼 아이콘 미표시 문제 (objectName 불일치)

---

## 🔄 다음 단계 제안

1. **다국어 지원 강화**: 탭 이름 수정 다이얼로그 텍스트 다국어 처리
2. **포트 탭 아이콘**: 연결 상태에 따른 탭 아이콘 표시
3. **SmartNumberEdit 확장**: 다른 입력 필드에도 적용 (예: Delay 필드)
4. **테마 변경 시 아이콘 갱신**: 런타임 테마 변경 시 플러스 탭 아이콘 자동 업데이트

---

## 📌 참고 사항

- 모든 변경 사항은 기존 설정 파일과 호환됩니다.
- 커스텀 탭 이름은 `ports.[index].custom_name`에 저장됩니다.
- `SmartNumberEdit`는 `view/widgets/common/` 폴더에 배치하여 재사용 가능한 공통 위젯으로 관리됩니다.

---

**작성일**: 2025-12-08
**작성자**: AI Assistant
**세션 시간**: 약 1시간
