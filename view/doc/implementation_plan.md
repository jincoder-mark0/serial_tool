# View 계층 구현 가이드

> **목적**: View 계층에서 구현해야 할 UI 컴포넌트 목록과 요구사항 정의

**최종 업데이트**: 2025-12-09

---

## 📋 구현 항목 한눈에 보기

| # | 항목 | 난이도 | 파일 | View 전용 | 상태 |
|---|------|--------|------|----------|------|
| 1 | **Connect 버튼 상태 스타일** | ⭐⭐ 보통 | `view/widgets/port_settings.py`<br>`.qss` | ✅ | **△ QSS 보완 필요** |
| 2 | **Packet Inspector 설정 UI** | ⭐⭐ 보통 | `view/dialogs/preferences_dialog.py` | ✅ | **❌ 누락 (구현 필요)** |
| 3 | 색상 코드 표준화 및 QSS 통합 | ⭐ 쉬움 | `.qss` 파일들<br>`view/color_rules.py` | ✅ | △ QSS 보완 필요 |
| 4 | Main Status Bar 동적 UI 통합 | ⭐⭐ 보통 | `view/sections/main_status_bar.py` | ✅ | △ Presenter 연동 필요 |

**View 전용 ✅**: 비즈니스 로직 없이 순수 UI만으로 구현 가능
**View 전용 ❌**: Presenter/Model 로직 필요 (제외)

---

## 🎯 구현 항목 상세

### 1. Connect 버튼 상태 스타일 보완 ⭐⭐ 보통

**목적**: `PortSettingsWidget`의 연결 버튼이 'Error' 상태일 때 명확한 시각적 피드백을 제공하고, 모든 상태에 대한 QSS를 완성합니다.

**3가지 상태별 UI**:

| 상태 (QProperty: `state`) | 텍스트 | 배경색 (QSS 정의) | 텍스트 색 |
|------|--------|----------------------|-----------|
| `disconnected` | "Connect" / "열기" | 기본 테마 | 기본 |
| `connected` | "Disconnect" / "닫기" | `#4CAF50` (녹색) | `white` |
| `error` | "Reconnect" / "재연결" | **`#F44336` (빨강)** | `white` |

**구현 사항 (View Code - 완료)**:
- `view/widgets/port_settings.py`의 `set_connection_state()`에서 `state` 프로퍼티 설정 완료.

**구현 사항 (QSS - 미완성)**:
- **Task**: `resources/themes/dark_theme.qss` 및 `light_theme.qss`에 `QPushButton[state="error"]` 스타일 정의 추가.

---

### 2. Packet Inspector 설정 (Preferences) ⭐⭐ 보통

**목적**: 패킷 파서 동작을 사용자가 설정할 수 있는 UI 제공. 이 UI는 `PreferencesDialog` 내부에 새로운 탭으로 구현되어야 합니다.

**구현 위치**: `view/dialogs/preferences_dialog.py` 내부에 별도 탭 추가

**설정 항목**:

1. **Parser 타입 선택** (QRadioButton Group):
   - Auto Detect (자동 감지)
   - AT Parser (AT 명령)
   - Delimiter Parser (구분자 기반)
   - Fixed Length Parser (고정 길이)
   - Raw Parser (원시 데이터)

2. **Delimiter 설정** (QListWidget + QLineEdit):
   - 기본값: `\r\n`, `0xFF`, `0x7E`
   - 사용자 정의 구분자 추가/삭제
   - 16진수 입력 지원

3. **Fixed Length 설정** (QSpinBox):
   - 패킷 길이 (바이트)
   - 범위: 1-4096

4. **AT Parser 색상 규칙** (QCheckBox + QComboBox):
   - OK, ERROR, URC, Prompt 패턴 활성화 체크 및 색상 선택 (preference dialog)
   - 사용자 정의 패턴 추가

5. **Inspector 동작** (QSpinBox + QCheckBox):
   - 최근 패킷 버퍼 크기 (기본: 100개)
   - 실시간 추적 활성화 ☑
   - 자동 스크롤 ☑

**Preferences 레이아웃** (Preferences 대화상자 내 탭):
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

**Task**: `PreferencesDialog`에 **Parser 탭(`create_parser_tab` 등)**과 관련 로직을 구현합니다.

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

### 3. 색상 코드 표준화 ⭐ 쉬움

**목적**: 애플리케이션 전반에 걸쳐 상태 및 로그 색상을 표준화하고 QSS에 반영합니다.

**표준 색상 팔레트** (일관성 유지):

| 용도 | 색상 코드 | 설명 |
| :--- | :--- | :--- |
| **Connected** | `#4CAF50` (녹색) | 포트 연결 성공 및 OK 응답 |
| **Error** | `#F44336` (빨강) | 에러 응답 및 연결 실패 |
| **Warning** | `#FF9800` (주황) | 경고 메시지 |
| **URC** | `#FFEB3B` (노랑) | URC (Unsolicited Result Code) 메시지 |
| **Prompt** | `#00BCD4` (청록) | 프롬프트 기호 (예: `>`) |
| **Timestamp** | `#9E9E9E` (회색) | 타임스탬프 |

**적용 위치**:
- `resources/themes/*.qss`
- `view/widgets/received_area.py` (appendHtml 시 적용)

**QSS 선택자**:
- `QPushButton[state="connected"]`
- `QPushButton[state="error"]`
- `QProgressBar[warning="true"]::chunk`

---

### 4. Main Status Bar 동적 UI 통합 ⭐⭐ 보통

**목적**: `MainStatusBar` 위젯에 데이터 출력을 위한 UI 요소를 배치하고, Presenter/Model에서 데이터를 받을 수 있는 `update_*` 메서드를 준비합니다. (순수 View 범위)

**UI 요소 (Permanent Widgets)**:
1. Port Status (`Port: COM1 ●` with color)
2. RX Speed (`RX: 0 KB/s`)
3. TX Speed (`TX: 0 KB/s`)
4. BPS (`BPS: 115200`)
5. Buffer Bar (`Buffer: 0%` QProgressBar)
6. Time Label (`00:00:00`)

**Task**: `main_status_bar.py`에 각 요소를 업데이트하는 **더미 메서드**(`update_port_status`, `update_rx_speed` 등)의 최종 구현을 확인합니다. (이 메서드들은 현재 존재하며, 다음 단계에서 Presenter와 연결됩니다.)

---

## 🚫 View 범위 밖 (제외 항목)

다음 항목들은 **Presenter/Model 구현 필요** (현재 제외):

1. ❌ **PortCombo 자동 스캔** - 타이머 로직
2. ❌ **실시간 데이터 업데이트** - QTimer 호출
3. ❌ **RxLogView 성능 최적화** - Chunk 렌더링, Virtual Scrolling
4. ❌ **CommandList Drag&Drop** - 복잡한 이벤트 처리
5. ❌ **애니메이션 효과** - QPropertyAnimation
6. ❌ **Console 패널** - logger 연동

**데이터 연동은 다음 단계(Presenter 구현)에서!**

