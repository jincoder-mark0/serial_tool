# View 계층 구현 가이드

> **목적**: View 계층에서 구현해야 할 UI 컴포넌트 목록과 요구사항 정의

**최종 업데이트**: 2025-12-05

---

## 📋 구현 항목 한눈에 보기

| # | 항목 | 난이도 | 파일 | View 전용 | 상태 |
|---|------|--------|------|----------|------|
| 1 | StatusPanel 위젯 | ⭐ 쉬움 | `view/widgets/status_panel.py` | ✅ | ❌ 누락 |
| 2 | 상태바 상세 정보 | ⭐ 쉬움 | `view/widgets/main_status_bar.py` | ✅ | ❌ 부분 |
| 3 | Connect 버튼 색상 | ⭐ 쉬움 | `view/widgets/port_settings.py` | ✅ | ❌ 부분 |
| 4 | 단축키 시스템 | ⭐⭐ 보통 | 여러 파일 | ✅ | ❌ 부분 |
| 5 | 색상 코드 표준화 | ⭐ 쉬움 | `.qss` 파일들 | ✅ | ❌ 부분 |
| 6 | Splitter 비율 복원 | ⭐ 쉬움 | `view/main_window.py` | ✅ | ❌ 누락 |
| 7 | Tooltip 개선 | ⭐ 쉬움 | 모든 위젯 | ✅ | ❌ 부분 |
| 8 | MainToolBar | ⭐⭐ 보통 | `view/widgets/main_toolbar.py` | ✅ | ❌ 누락 |
| 9 | Packet Inspector 설정 | ⭐⭐ 보통 | `view/dialogs/preferences_dialog.py` | ✅ | ❌ 누락 |

**View 전용 ✅**: 비즈니스 로직 없이 순수 UI만으로 구현 가능
**View 전용 ❌**: Presenter/Model 로직 필요 (제외)

---

## 🎯 구현 항목 상세

### 1. StatusPanel 위젯 생성 ⭐ 쉬움

**UI 레이아웃**:
```
┌─ Status ─────────────────────┐
│ RX: 1.23 MB  TX: 256 KB      │
│ Errors: 0  Uptime: 00:05:23  │
│ Last RX: [14:32:15.123]      │
└──────────────────────────────┘
```

**필요한 컴포넌트**:
- `QGroupBox` (타이틀: "Status")
- `QGridLayout` (2열 구성)
- 5개 `QLabel`:
  1. `rx_label`: "RX: 0 MB" (수신 바이트, 자동 B→KB→MB 변환)
  2. `tx_label`: "TX: 0 KB" (송신 바이트, 자동 B→KB→MB 변환)
  3. `errors_label`: "Errors: 0" (에러 횟수)
  4. `uptime_label`: "Uptime: 00:00:00" (HH:MM:SS 형식)
  5. `last_rx_label`: "Last RX: [--:--:--.---]" (마지막 수신 시각)

**업데이트 메서드** (Presenter에서 호출):
- `update_rx(bytes_count: int)` - RX 바이트 업데이트
- `update_tx(bytes_count: int)` - TX 바이트 업데이트
- `update_errors(count: int)` - 에러 횟수 업데이트
- `update_uptime(seconds: int)` - 업타임 업데이트
- `update_last_rx(timestamp: str)` - 마지막 수신 시각 업데이트
- `format_bytes(bytes_count: int) -> str` - 바이트 단위 변환 헬퍼

**언어 지원**:
- `language_manager` 연결
- 언어 키: `status_grp_title`

---

### 2. 상태바 상세 정보 ⭐ 쉬움

**UI 레이아웃** (우측 영구 위젯):
```
[Port: -- ○] [RX: 0 KB/s] [TX: 0 KB/s] [BPS: 0] [Buffer: 0%] [14:32:15]
```

**필요한 컴포넌트** (6개 영구 위젯):
1. `port_label`: QLabel - "Port: -- ○" (포트명 + 연결 상태)
2. `rx_label`: QLabel - "RX: 0 KB/s" (초당 수신 속도)
3. `tx_label`: QLabel - "TX: 0 KB/s" (초당 송신 속도)
4. `bps_label`: QLabel - "BPS: 0" (통신 속도)
5. `buffer_bar`: QProgressBar - 0-100% (80% 이상 빨간색)
6. `time_label`: QLabel - "00:00:00" (현재 시각)

**구현 사항**:
- 기존 `MainStatusBar` 클래스에 `init_widgets()` 메서드 추가
- `addPermanentWidget()` 사용하여 우측 고정
- QProgressBar:
  - `setMaximum(100)`, `setMaximumWidth(100)`
  - `setFormat("Buffer: %p%")`
  - 80% 이상 시 빨간색 스타일 적용

**업데이트 메서드**:
- `update_port_status(port: str, connected: bool)`
- `update_rx_speed(bytes_per_sec: int)`
- `update_tx_speed(bytes_per_sec: int)`
- `update_buffer(percent: int)`
- `update_time(time_str: str)`

---

### 3. Connect 버튼 색상 변경 ⭐ 쉬움

**3가지 상태별 UI**:

| 상태 | 텍스트 | 배경색 | 텍스트 색 |
|------|--------|--------|-----------|
| Disconnected | "Connect" | 기본 테마 | 기본 |
| Connected | "Disconnect" | `#4CAF50` (녹색) | `white` |
| Error | "Reconnect" | `#F44336` (빨강) | `white` |

**구현 사항**:
- `view/widgets/port_settings.py`에 메서드 추가
- `set_connection_state(state: str)` 메서드
  - 인자: `'disconnected'`, `'connected'`, `'error'`
  - 텍스트 변경: `setText()`
  - 스타일 변경: `setStyleSheet()`
  - property 설정: `setProperty("state", value)`
  - 즉시 적용: `style().unpolish()` + `style().polish()`

---

### 4. 단축키 시스템 ⭐⭐ 보통

**10개 단축키 매핑**:

| 단축키 | 기능 | 구현 파일 | 연결 대상 |
|--------|------|-----------|-----------|
| `Ctrl+O` | 포트 열기 | `main_window.py` | 메뉴 Open 액션 |
| `Ctrl+W` | 탭 닫기 | `main_window.py` | 현재 탭 제거 |
| `Ctrl+Enter` | 명령 전송 | `manual_control.py` | Send 버튼 |
| `F5` | CL 실행 | `command_list_panel.py` | Run 메서드 |
| `Ctrl+F5` | Auto Run | `command_list_panel.py` | Auto Run 토글 |
| `Insert` | 행 추가 | `command_list_panel.py` | add_row() |
| `Delete` | 행 삭제 | `command_list_panel.py` | delete_selected_rows() |
| `Ctrl+Shift+S` | 로그 저장 | `main_window.py` | 저장 다이얼로그 |
| `Ctrl+,` | 설정 | `main_window.py` | Preferences 다이얼로그 |

**구현 방법**:
- `QShortcut` + `QKeySequence` 사용
- 각 파일에 `init_shortcuts()` 메서드 추가
- `__init__()` 끝에서 호출
- 기존 시그널/슬롯 연결

---

### 5. 색상 코드 표준화 ⭐ 쉬움

**표준 색상 팔레트** (일관성 유지):

**상태 색상** (버튼, 배경):
- ✅ Connected: `#4CAF50` (녹색)
- ⚪ Disconnected: `#9E9E9E` (회색)
- ❌ Error: `#F44336` (빨강)
- ▶️ Running: `#2196F3` (파랑)
- ⚠️ Warning: `#FF9800` (주황)

**로그 텍스트 색상** (ReceivedArea):
- OK: `#4CAF50` (녹색)
- ERROR: `#F44336` (빨강)
- URC: `#FFEB3B` (노랑)
- Prompt (>): `#00BCD4` (청록)
- Timestamp: `#9E9E9E` (회색)

**적용 위치**:
- `resources/themes/dark_theme.qss`
- `resources/themes/light_theme.qss`
- `view/widgets/received_area.py` (appendHtml 시 적용)

**QSS 선택자**:
- `QPushButton[state="connected"]`
- `QPushButton[state="error"]`
- `QProgressBar[warning="true"]::chunk`

---

### 6. Splitter 비율 복원 ⭐ 쉬움

**기능**: 사용자가 조절한 좌우 패널 분할 비율을 저장/복원

**예시**:
- 사용자가 50:50 → 60:40으로 드래그
- 앱 재실행 시 60:40 유지

**구현 사항**:
- `closeEvent()`: `splitter.saveState()` → Base64 인코딩 후 저장
- `__init__()`: 저장된 상태를 Base64 디코딩 → `splitter.restoreState()`
- 설정 키: `ui.splitter_state`

---

### 7. Tooltip 개선 ⭐ 쉬움

**대상 위젯**: 모든 버튼과 주요 위젯

**구현**:
- 각 위젯의 `setToolTip()` 호출
- 단축키 포함 권장 (예: "Send command (Ctrl+Enter)")

**주요 대상**:
- `view/widgets/manual_control.py`: Send, Clear, Save Log 버튼, 체크박스들
- `view/widgets/command_list.py`: Add, Delete, Up, Down 버튼
- `view/widgets/command_control.py`: Run, Stop, Auto Run, Save, Load 버튼
- `view/widgets/port_settings.py`: Open, Scan 버튼

---

### 8. MainToolBar 추가 (선택적) ⭐⭐ 보통

**빠른 액션 버튼** (6개):
- Open - 포트 열기
- Close - 포트 닫기
- Clear - RX/TX 로그 지우기
- Save Log - 로그 저장
- Settings - 설정 열기

**사양**:
- 아이콘 크기: 24×24px
- 위치: 메뉴바 바로 아래 (`addToolBar(Qt.TopToolBarArea)`)
- 이동 불가: `setMovable(False)`
- 버튼 스타일: `setToolButtonStyle(Qt.ToolButtonTextUnderIcon)`

**구현**:
- 새 파일: `view/widgets/main_toolbar.py`
- 클래스: `MainToolBar(QToolBar)`
- 시그널 5개: `open_requested`, `close_requested`, `clear_requested`, `save_log_requested`, `settings_requested`
- `QAction` 생성 후 `addAction()`

**통합**:
- `view/main_window.py`에서 import 및 추가
- 각 시그널을 해당 핸들러에 연결

---

### 9. Packet Inspector 설정 (Preferences) ⭐⭐ 보통

**목적**: 패킷 파서 동작을 사용자가 설정할 수 있는 UI 제공

**설정 항목**:

1. **Parser 타입 선택**:
   - Auto Detect (자동 감지)
   - AT Parser (AT 명령)
   - Delimiter Parser (구분자 기반)
   - Fixed Length Parser (고정 길이)
   - Raw Parser (원시 데이터)

2. **Delimiter 설정**:
   - 기본값: `\r\n`, `0xFF`, `0x7E`
   - 사용자 정의 구분자 추가/삭제
   - 16진수 입력 지원

3. **Fixed Length 설정**:
   - 패킷 길이 (바이트)
   - 범위: 1-4096

4. **AT Parser 색상 규칙**:
   - OK: 녹색 (#4CAF50) ☑
   - ERROR: 빨강 (#F44336) ☑
   - URC: 노랑 (#FFEB3B) ☑
   - Prompt: 청록 (#00BCD4) ☑
   - 사용자 정의 패턴 추가

5. **Inspector 동작**:
   - 최근 패킷 버퍼 크기 (기본: 100개)
   - 실시간 추적 활성화 ☑
   - 자동 스크롤 ☑

**UI 레이아웃** (Preferences 대화상자 내 탭):
```
┌─ Parser Settings ──────────────────────┐
│ Parser Type:                           │
│   ○ Auto Detect                        │
│   ● AT Parser                          │
│   ○ Delimiter Parser                   │
│   ○ Fixed Length Parser                │
│   ○ Raw Parser                         │
│                                         │
│ ┌─ Delimiter Settings ────────────┐   │
│ │ Delimiters:                      │   │
│ │ [×] \r\n    [×] 0xFF   [×] 0x7E  │   │
│ │ [Add Custom] [____________]      │   │
│ └──────────────────────────────────┘   │
│                                         │
│ ┌─ Fixed Length ──────────────────┐   │
│ │ Packet Length: [64] bytes        │   │
│ └──────────────────────────────────┘   │
│                                         │
│ ┌─ AT Color Rules ────────────────┐   │
│ │ ☑ OK Pattern:     [Green  ▼]    │   │
│ │ ☑ ERROR Pattern:  [Red    ▼]    │   │
│ │ ☑ URC Pattern:    [Yellow ▼]    │   │
│ │ ☑ Prompt Pattern: [Cyan   ▼]    │   │
│ └──────────────────────────────────┘   │
│                                         │
│ ┌─ Inspector Options ─────────────┐   │
│ │ Buffer Size: [100] packets       │   │
│ │ ☑ Real-time Tracking             │   │
│ │ ☑ Auto Scroll                    │   │
│ └──────────────────────────────────┘   │
│                                         │
│         [Apply] [Reset] [Cancel]       │
└─────────────────────────────────────────┘
```

**구현 위치**:
- `view/dialogs/preferences_dialog.py`에 새 탭 추가
- 탭 이름: "Packet Inspector" 또는 "Parser"

**필요한 컴포넌트**:
- QRadioButton 그룹 (Parser 타입)
- QListWidget + QPushButton (Delimiter 관리)
- QSpinBox (Fixed Length, Buffer Size)
- QCheckBox (색상 규칙, 옵션)
- QComboBox (색상 선택)

**설정 저장 경로**:
```json
{
  "parser": {
    "type": "at",
    "delimiters": ["\r\n", "0xFF"],
    "fixed_length": 64,
    "at_colors": {
      "ok": "#4CAF50",
      "error": "#F44336",
      "urc": "#FFEB3B",
      "prompt": "#00BCD4"
    },
    "inspector": {
      "buffer_size": 100,
      "real_time_tracking": true,
      "auto_scroll": true
    }
  }
}
```

**업데이트 메서드**:
- `load_parser_settings()` - 설정 로드
- `save_parser_settings()` - 설정 저장
- `apply_parser_settings()` - 설정 적용 (Presenter에 시그널 emit)
- `reset_parser_settings()` - 기본값 복원

**언어 지원**:
- `parser_settings_title`
- `parser_type_auto`, `parser_type_at` 등
- `delimiter_custom_hint`
- `inspector_buffer_size`

---

## 🚫 View 범위 밖 (제외 항목)

다음 항목들은 **Presenter/Model 구현 필요** (현재 제외):

1. ❌ **PortCombo 자동 스캔** - 타이머 로직
2. ❌ **실시간 데이터 업데이트** - QTimer 호출
3. ❌ **RxLogView 성능 최적화** - Chunk 렌더링, Virtual Scrolling
4. ❌ **CommandList Drag&Drop** - 복잡한 이벤트 처리
5. ❌ **애니메이션 효과** - QPropertyAnimation
6. ❌ **Console 패널** - logger 연동

---

## 📊 우선순위

### ✅ 즉시 구현
1. **StatusPanel 위젯** - 신규 파일
2. **Connect 버튼 색상** - 메서드 추가
3. **Tooltip** - 모든 버튼
4. **Splitter 복원** - closeEvent 수정

### ✅ 하루 내 완료
5. **상태바 상세 정보** - 위젯 6개 추가
6. **색상 표준화** - QSS 수정
7. **단축키 시스템** - 여러 파일 수정

### ⭐ 선택적
8. **MainToolBar** - 신규 위젯
9. **Packet Inspector 설정** - Preferences 탭 추가

---

## 🎯 완료 기준

View 계층 완성 판단 기준:

1. ✅ StatusPanel이 각 포트 탭에 표시됨
2. ✅ 하단 상태바에 6개 필드 보임
3. ✅ Connect 버튼이 상태별로 색상 변경
4. ✅ 주요 단축키(Ctrl+O, F5, Insert 등) 동작
5. ✅ QSS 파일에 표준 색상 코드 적용
6. ✅ 창 크기와 Splitter 비율 저장/복원
7. ✅ 모든 버튼에 Tooltip
8. ✅ Packet Inspector 설정 UI

**데이터 연동은 다음 단계(Presenter 구현)에서!**

