# SerialTool v1.0

**최종 업데이트**: 2025-12-10

**SerialTool**은 Python과 PyQt5로 개발된 강력한 통신 유틸리티입니다. MVP(Model-View-Presenter) 패턴 기반의 깔끔한 아키텍처와 현대적인 UI/UX를 제공하며, Serial 통신뿐만 아니라 향후 SPI, I2C 등 다양한 프로토콜로 확장 예정입니다.

## 주요 기능 (Key Features)

### 핵심 기능
* **멀티 프로토콜(시리얼, SPI, I2C) 지원**: 탭 인터페이스로 여러 프로토콜(시리얼, SPI, I2C) 포트 동시 제어
* **수동 제어**:
  - HEX/ASCII 모드
  - Prefix/Suffix
  - 여러 줄 입력 지원 (라인 번호 표시, Ctrl+Enter 전송)
  - 파일 전송 기능
  - 로그 저장 및 화면(newline 설정, max line 수 설정) 클리어
* **매크로 자동화**:
  - 여러 명령어를 리스트로 관리
  - 순차 명령 실행
  - Repeat 및 Delay 설정
  - 스크립트 저장 및 불러오기 (JSON 형식)
* **실시간 모니터링**:
  - Tx/Rx 바이트 카운트
  - 색상 규칙 기반 로그 강조 (OK=녹색, ERROR=빨강)
  - 타임스탬프 표시

### UI/UX 특징
* **현대적 인터페이스**:
  - 다크/라이트 테마 전환
  - 듀얼 폰트 시스템 (Proportional/Fixed)
  - SVG 기반 테마 적응형 아이콘
  - 컴팩트한 2줄 포트 설정 레이아웃
  - 3단계 Select All 체크박스
  - PortState Enum 기반 연결 상태 표시
* **사용성**:
  - 모든 기능 툴팁 제공
  - 설정 자동 저장 (창 크기, 테마, 폰트)
  - 견고한 폴백 메커니즘 (설정 파일 누락 시 복구)
  - 중앙 집중식 경로 관리 (AppConfig)
  - Package-level imports (__init__.py)

### 다국어 지원
* **한국어/영어** 실시간 전환
* CommentJSON 기반 번역 관리
* 언어 키 자동 추출 도구 (`tools/manage_lang_keys.py`)

---

## 설치 및 실행

### 요구 사항
* Python 3.8+
* PyQt5, pyserial, commentjson

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/yourusername/SerialTool.git
cd SerialTool

# 2. 가상 환경 생성 (권장)
python -m venv .venv

# 3. 가상 환경 활성화
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 4. 패키지 설치
pip install -r requirements.txt
```

### 실행

```bash
# 가상 환경 활성화 후
python main.py
```

---

## 프로젝트 구조

```
serial_tool2/
├── app_main.py             # 애플리케이션 진입점
├── app_config.py           # 애플리케이션 설정
├── app_version.py          # 버전 정보
├── requirements.txt        # 의존성 목록
│
├── core/                   # 핵심 유틸리티
│   ├── constants.py        # 상수 정의
│   ├── event_bus.py        # 이벤트 버스
│   ├── logger.py           # 로깅 시스템 (Singleton)
│   ├── port_state.py       # 포트 상태 관리
│   ├── settings_manager.py # 설정 관리 (Singleton)
│   └── utils.py            # 유틸리티 함수
│
├── model/                  # 비즈니스 로직
│   ├── serial_worker.py    # 시리얼 통신 워커
│   └── port_controller.py  # 포트 제어
│
├── presenter/              # MVP Presenter 계층
│   ├── main_presenter.py   # 메인 프레젠터
│   └── port_presenter.py   # 포트 프레젠터
│
├── view/                   # UI 계층
│   ├── main_window.py      # 메인 윈도우
│   │
│   ├── manager/              # 관리자 계층
│   │   ├── color_manager.py      # 로그 색상 규칙
│   │   ├── lang_manager.py # 다국어 관리
│   │   └── theme_manager.py    # 테마 관리
│   │
│   ├── custom_widgets/       # PyQt5 커스텀 위젯
│   │   ├── smart_number_edit.py # 스마트 숫자 편집 위젯
│   │   └── smart_text_edit.py # 스마트 텍스트 편집 위젯
│   │
│   ├── sections/           # 섹션 (대 분할)
│   │   ├── main_left_section.py # 메인 왼쪽 섹션
│   │   ├── main_menu_bar.py # 메인 메뉴 바
│   │   ├── main_right_section.py # 메인 오른쪽 섹션
│   │   ├── main_status_bar.py # 메인 상태 바
│   │   └── main_tool_bar.py # 메인 도구 바
│   │
│   ├── panels/             # 패널 (중 단위)
│   │   ├── macro_panel.py # 매크로 패널
│   │   ├── manual_ctrl_panel.py # 수동 제어 패널
│   │   ├── packet_inspector_panel.py # 패킷 인스펙터 패널
│   │   ├── port_panel.py # 포트 패널
│   │   └── port_tab_panel.py # 포트 탭 패널
│   │
│   ├── widgets/            # 위젯 (소 단위)
│   │   ├── file_progress.py  # 파일 진행률 위젯
│   │   ├── manual_ctrl.py    # 수동 제어 위젯
│   │   ├── macro_list.py     # 매크로 리스트 위젯
│   │   ├── packet_inspector.py # 패킷 인스펙터 위젯
│   │   ├── port_settings.py  # 포트 설정 위젯
│   │   ├── port_stats.py     # 포트 통계 위젯
│   │   ├── received_area.py  # 수신 영역 위젯
│   │   └── system_log.py     # 시스템 로그 위젯
│   │
│   ├── dialogs/            # 대화상자
│   │   ├── about_dialog.py # 정보 대화상자
│   │   ├── font_settings_dialog.py # 폰트 설정 대화상자
│   │   └── preferences_dialog.py # 설정 대화상자
│   │
│   └── doc/                # View 계층 문서
│       └── implementation_plan.md  # View 구현 계획
│
├── config/                 # 설정 파일
│   ├── settings.json       # 앱 설정 (논리 그룹: serial, command, logging, ui)
│   └── languages/          # 다국어 리소스
│       ├── ko.json         # 한국어
│       └── en.json         # 영어
│
├── resources/              # 리소스 파일
│   ├── icons/              # SVG 아이콘
│   │   ├── light/          # 라이트 테마용
│   │   └── dark/           # 다크 테마용
│   └── themes/             # QSS 스타일시트
│       ├── dark_theme.qss
│       └── light_theme.qss
│
├── doc/                    # 프로젝트 문서
│   ├── Implementation_Specification.md  # 구현 명세서 (전체 설계)
│   ├── changelog.md                     # 변경 이력
│   └── session_summary_YYYYMMDD.md      # 작업 세션 요약
│
├── guide/                  # 개발 가이드
│   ├── code_style_guide.md # 코드 스타일 가이드
│   └── naming_convention.md # 명명 규칙 (언어 키, 변수명 등)
│
├── tools/                  # 유틸리티 도구
│   └── manage_lang_keys.py # 언어 키 관리 도구
│
├── tests/                  # 테스트 코드
│   ├── test_view.py
│   └── test_ui_translations.py
│
├── logs/                   # 로그 파일 (gitignore)
└── ignore/                 # 연습 파일 (gitignore)
```

---

## 아키텍처

### MVP 패턴

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│    View     │◄───────►│  Presenter   │◄───────►│    Model    │
│ (UI 전용)    │  Signal  │ (비즈니스 로직)│   Data   │ (데이터/통신)│
└─────────────┘         └──────────────┘         └─────────────┘
```

**설계 원칙**:
- **View**: UI 표시와 사용자 입력만 처리 (시그널 emit)
- **Presenter**: 비즈니스 로직 처리 (View ↔ Model 중재)
- **Model**: 데이터 및 시리얼 통신 담당

**최근 리팩토링 사례**:
- ManualCtrlWidget: Prefix/Suffix 로직 → Presenter로 이동
- PortSettingsWidget: 설정 접근 → SettingsManager 활용

### 설정 구조

**논리적 그룹 기반** (`config/settings.json`):
```json
{
  "serial": { "baudrate": 115200, ... },
  "command": { "prefix": "AT", "suffix": "\r\n" },
  "logging": { "log_path": "logs/", ... },
  "ui": { "theme": "dark", "font": {...} }
}
```

---

## 현재 개발 상태

### ✅ 완료 항목

**프로젝트 기반**:
- [x] 프로젝트 구조 및 기본 설정
- [x] Git 버전 관리 체계
- [x] 문서화 시스템
- [x] MVP 아키텍처 기반 리팩토링

**View 계층**:
- [x] UI 골격 및 위젯 구현
- [x] 테마 시스템 (Dark/Light)
- [x] 듀얼 폰트 시스템
- [x] SVG 아이콘 시스템
- [x] 다국어 지원 (한국어/영어)
- [x] 색상 규칙 (OK=녹색, ERROR=빨강)
- [x] 설정 관리 시스템
- [x] 코드 품질 개선 (타입 힌트, Docstring)
- [x] MVP 패턴 적용 (Signal 기반 통신)

**Core 유틸리티**:
- [x] Logger (Singleton, 견고한 패턴)
- [x] SettingsManager (Singleton, 논리 그룹)
- [x] 폴백 메커니즘 (설정 파일 복구)

### 🔄 진행 중

**View 계층 완성** (`view/doc/implementation_plan.md` 참조):
- [ ] StatusPanel 위젯
- [ ] 상태바 상세 정보 (6개 필드)
- [ ] Connect 버튼 색상 변경
- [ ] 단축키 시스템 (10개)
- [ ] 레이아웃 비율 조정
- [ ] 색상 코드 표준화
- [ ] Splitter 비율 복원
- [ ] Tooltip 개선

**Model/Presenter**:
- [ ] SerialWorker 완성
- [ ] PortController 통합
- [ ] Presenter 로직 확장

### ⏳ 예정

**단기 (Current Sprint)**:
- [ ] Macro(list 순차 반복 전송) 자동화 엔진
- [ ] 파일 전송 기능
- [ ] 패킷 파서 시스템

**중장기 (Future)**:
- [ ] 플러그인 시스템
- [ ] **통신 프로토콜 확장**:
  - [ ] SPI 지원 (FT4222 칩 등)
  - [ ] I2C 지원 (FT4222 칩 등)
  - [ ] 멀티 프로토콜 동시 지원 (Serial + SPI + I2C)
- [ ] 스크립트 언어 지원 (Python/Lua 임베딩)

---

## 개발 가이드라인

### 문서 참조

| 문서 | 목적 | 위치 |
|------|------|------|
| Implementation Specification | 전체 설계 및 명세 | `doc/Implementation_Specification.md` |
| View 구현 계획 | View 계층 구현 가이드 | `view/doc/implementation_plan.md` |
| 코딩 규칙 | 코드 스타일 | `guide/code_style_guide.md` |
| 명명 규칙 | 코드/언어 키 네이밍 | `guide/naming_convention.md` |
| 주석 가이드 | 주석/Docstring 작성법 | `guide/comment_guide.md` |
| Git 가이드 | 커밋/PR/이슈 규칙 | `guide/git_guide.md` |
| 변경 이력 | 세션별 변경 사항 | `doc/changelog.md` |
| 세션 요약 | 2025-12-09 작업 요약 | `doc/session_summary_20251209.md` |

### 코드 스타일

- **PEP 8** 준수
- **한국어** 주석 및 Docstring
- **타입 힌트** 필수
- **MVP 패턴** 준수 (View는 시그널만 emit)

### Git 버전 관리
* 본 프로젝트는 **Git을 통한 지속적인 백업**을 권장합니다:
* 모든 메시지는 한국어로 작성합니다.

```bash
# 커밋 메시지 형식 (한국어)
Feat: 기능 추가
Fix: 버그 수정
Docs: 문서 수정
Refactor: 리팩토링
Style: 스타일 변경
```

**브랜치 전략**:
- `main`: 안정 버전
- `feature/기능명`: 개발 브랜치

**권장 사항**:
- 기능 단위로 자주 커밋 (최소 하루 1회)
- 세션 종료 시 `doc/session_summary_YYYYMMDD.md` 작성

---

## 도구 및 유틸리티

### 언어 키 관리

```bash
# UI 파일에서 언어 키 자동 추출
python managers/manage_lang_keys.py extract

# 누락/미사용 키 확인
python managers/manage_lang_keys.py check
```

### 테스트 실행

```bash
# 전체 테스트
pytest

# 특정 테스트
pytest tests/test_view.py
```

---

## 기여 (Contributing)

버그 신고 및 기능 제안은 Issue를 통해 환영합니다.
Pull Request도 언제나 환영합니다.

---

## 라이선스

MIT License
