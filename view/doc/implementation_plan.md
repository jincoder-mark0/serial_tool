# View 계층 구현 가이드

> **목적**: View 계층에서 구현해야 할 UI 컴포넌트 목록과 요구사항 정의

**최종 업데이트**: 2025-12-05

---

## 📋 구현 항목 한눈에 보기

| # | 항목 | 난이도 | 파일 | View 전용 | 상태 |
|---|------|--------|------|----------|------|
| 1 | Connect 버튼 색상 | ⭐ 쉬움 | `view/widgets/port_settings.py` | ✅ | ❌ 부분 |
| 2 | 색상 코드 표준화 | ⭐ 쉬움 | `.qss` 파일들 | ✅ | ❌ 부분 |
| 3 | Packet Inspector 설정 | ⭐⭐ 보통 | `view/dialogs/preferences_dialog.py` | ✅ | ❌ 누락 |

**View 전용 ✅**: 비즈니스 로직 없이 순수 UI만으로 구현 가능
**View 전용 ❌**: Presenter/Model 로직 필요 (제외)

---

## 🎯 구현 항목 상세

### 1. Connect 버튼 색상 변경 ⭐ 쉬움

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

### 2. 색상 코드 표준화 ⭐ 쉬움

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

### 3. Packet Inspector 설정 (Preferences) ⭐⭐ 보통

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

**데이터 연동은 다음 단계(Presenter 구현)에서!**

