# 변경 이력 (CHANGELOG)

## [미배포] (Unreleased)

### 문서 및 Preferences 다이얼로그 개선 (2025-12-04)

#### 변경 사항 (Changed)

- **코딩 스타일 가이드 업데이트**
  - `doc/code_style_guide.md`에 언어 키 네이밍 규칙 섹션(5.1) 추가
  - `[context]_[type]_[name]` 형식 엄격히 정의
  - UI 요소 타입별 분류 (`btn`, `lbl`, `chk`, `combo`, `input`, `grp`, `col`, `tab`, `dialog`, `txt`, `tooltip`)
  - 올바른/잘못된 예시 제공
  - 특수 케이스 문서화 (다이얼로그 타이틀, 상태 메시지, 필터 문자열)

- **Preferences 다이얼로그 접근성 수정**
  - `view/main_window.py`에서 `preferences_requested` 시그널 연결
  - `open_preferences_dialog()` 및 `apply_preferences()` 메서드 추가
  - 메뉴바 → View → Preferences 정상 작동
  - 테마 및 언어 변경 즉시 적용

#### 이점 (Benefits)

- 언어 키 네이밍에 대한 명확한 가이드라인 제공
- 신규 개발자 온보딩 시 참고 자료 확보
- Preferences 다이얼로그 접근성 개선
- 일관성 있는 코드베이스 유지

### UI 아키텍처 리팩토링 (2025-12-04)

#### 변경 사항 (Changed)

- **4단계 계층 구조 확립 (Window → Section → Panel → Widget)**
  - 기존 `LeftPanel`, `RightPanel`을 `LeftSection`, `RightSection`으로 리팩토링
  - 새 디렉토리 `view/sections/` 생성
  - `ManualControlPanel`, `PacketInspectorPanel` 래퍼 추가
  - 각 계층의 역할 명확화:
    - **Window**: 최상위 애플리케이션 셸 (`MainWindow`)
    - **Section**: 화면 구획 분할, Panel만 포함 (`LeftSection`, `RightSection`)
    - **Panel**: 기능 단위 그룹, Widget만 포함 (`PortPanel`, `CommandListPanel`, `ManualControlPanel` 등)
    - **Widget**: 실제 UI 요소 및 로직 (`PortSettingsWidget`, `ManualControlWidget` 등)
  - Presenter 계층 업데이트 (`port_presenter.py`, `main_presenter.py`)

#### 이점 (Benefits)
- 코드 구조의 일관성 및 가독성 향상
- 컴포넌트 책임 범위 명확화
- 유지보수 및 확장성 개선

### UI 개선 및 기능 강화 (2025-12-04)

#### 추가 사항 (Added)

- **ManualControlWidget 기능 확장**
  - 접두사(Prefix) 및 접미사(Suffix) 입력 필드 및 체크박스 추가
  - 데이터 전송 시 포맷팅 옵션 적용 기능

- **스크립트 저장/로드**
  - Command List 및 실행 설정을 JSON 파일로 저장/로드하는 기능 구현 (`CommandListPanel`)
  - `save_script_to_file`, `load_script_from_file` 메서드 추가

- **아이콘**
  - 검색 탐색 버튼용 아이콘 추가 (`find_prev`, `find_next`)

#### 수정 사항 (Fixed)

- **UI 아이콘 표시**
  - `CommandListWidget` 버튼의 objectName 불일치 수정 (`btn_add` → `add_btn` 등)으로 아이콘 미표시 문제 해결
- **테마 스타일**
  - 다크 테마에서 Placeholder 텍스트 색상 문제 수정 (`placeholder-text-color` 추가)

### 언어 키 표준화 및 로깅 프레임워크 (2025-12-03)

#### 추가 사항 (Added)

- **로깅 프레임워크**
  - `core/logger.py` 구현: 싱글톤 패턴 기반 Logger 클래스
  - 로그 레벨: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - 파일 로깅: RotatingFileHandler (10MB x 5개 파일)
  - 콘솔 로깅: 색상 구분 출력
  - 타임스탬프 자동 추가

- **자동화 테스트**
  - `tests/test_ui_translations.py`: UI 컴포넌트 번역 자동 검증
  - 8개 위젯/패널 언어 전환 테스트 (6개 통과)

- **도구**
  - `tools/manage_lang_keys.py` 개선: 자동 모듈 탐지 기능

#### 변경 사항 (Changed)

- **언어 키 표준화**
  - 모든 언어 키를 `[context]_[type]_[name]` 규칙으로 리팩토링
  - `en.json`, `ko.json` 업데이트 (192개 키)
  - 모든 UI 컴포넌트의 `get_text()` 호출 수정
  - 주석 제거 및 JSON 구조 정리

- **MainWindow 구조 개선**
  - `MainMenuBar`를 별도 위젯으로 분리 (`view/widgets/main_menu_bar.py`)
  - `MainStatusBar`를 별도 위젯으로 분리 (`view/widgets/main_status_bar.py`)
  - 코드 재사용성 및 가독성 향상

- **로깅 개선**
  - `ThemeManager`, `LanguageManager`의 print 문을 logger 호출로 교체
  - 구조화된 로그 메시지 형식

#### 수정 사항 (Fixed)

- **About Dialog**: `MainWindow`에서 시그널 연결 누락 수정
- **manage_lang_keys.py**: 하드코딩된 모듈 리스트 제거, 자동 탐지로 개선

### View 계층 마무리 및 다국어 지원 (2025-12-02)


#### 추가 사항 (Added)

- **다국어 지원 (Phase 1)**
  - LanguageManager 확장: 50+ UI 문자열 추가 (한국어/영어)
  - MainWindow 메뉴 시스템 한글화 (파일, 보기, 도움말 메뉴)
  - 윈도우 제목 및 상태바 한글화
  - 언어 동적 변경 핸들러 구현 (on_language_changed)
  - PortSettingsWidget 부분 한글화 (포트, 스캔, 보레이트 버튼)
  - **리팩토링**: 언어 리소스를 코드에서 JSON 파일로 분리 (`config/languages/*.json`)

- **commentjson 지원**
  - 모든 JSON 파일 처리에 commentjson 라이브러리 적용
  - JSON 파일에 주석 사용 가능 (가독성 향상)
  - 설정 파일 및 언어 파일에 설명 주석 추가 가능

- **설정 관리 개선**
  - 설정 저장 위치를 `config/settings.json`으로 변경 (프로젝트 루트에서 config 폴더로)
  - SettingsManager에 싱글톤 패턴 적용하여 설정 동기화 문제 해결

- **위젯 상태 저장/복원 구현**
  - ManualControlWidget: 입력 텍스트, HEX 모드, RTS/DTR 상태 저장/복원
  - ReceivedArea: 검색어, HEX 모드, 타임스탬프, 일시정지 상태 저장/복원
  - CommandControl: 초기화 문제 수정 및 상태 저장/복원 안정화
  - CommandListPanel: 초기화 순서 변경으로 load_state 오류 해결

#### 수정 사항 (Fixed)

- **ThemeManager**: `load_theme()` 메서드의 `@staticmethod` 데코레이터 제거 (NameError 방지)
- **ColorRulesManager**: 설정 파일 경로 계산 오류 수정 (`parent.parent.parent` → `parent.parent`)
- **MainWindow**:
  - Import 구문을 파일 상단으로 이동 (코드 스타일 가이드 준수)
  - `on_language_changed` 및 `_save_window_state` 메서드 복구
- **PortSettingsWidget**: 필수 메서드 복원 (`set_port_list`, `set_connected`)
- **CommandControl**: SyntaxError 수정 (중복 코드 제거)
- **CommandListPanel**: 초기화 순서 변경으로 상태 복원 시 오류 해결
- **탭 관리**:
  - 포트 탭 증식 문제 수정 (재시작 시 탭이 계속 추가되던 버그)
  - LeftPanel의 탭 추가 로직 개선
- **About Dialog**: 구현 완료 및 manage_lang_keys.py JSON 주석 처리 개선
- **manage_lang_keys.py**: JSON 파싱 오류 처리 추가

#### 변경 사항 (Changed)

- **test_view.py**: PreferencesDialog, AboutDialog, FileProgressWidget, Language 테스트 케이스 추가
- **디버그 로깅**:
  - 모든 주요 컴포넌트에 저장/복구 디버그 로그 추가 (개발 중)
  - 검증 완료 후 디버그 로그 제거


### 듀얼 폰트 시스템 (2025-12-01)

#### 추가 사항 (Added)

- **폰트 시스템 개선**
  - Proportional Font (가변폭): UI 요소 (메뉴, 상태바, 레이블, 버튼 등)에 적용
  - Fixed Font (고정폭): TextEdit, CommandList 등 데이터 표시 영역에 적용
  - 폰트 설정 대화상자 구현

- **테마 시스템**
  - 중앙 집중식 QSS 기반 테마 관리 구현 (`view/theme_manager.py`)
  - 다크 테마 (`resources/themes/dark_theme.qss`) 및 라이트 테마 (`resources/themes/light_theme.qss`) 생성
  - View 메뉴를 통한 동적 테마 전환
  - 폰트 커스터마이징 메뉴 (사전 정의 폰트 및 커스텀 폰트 대화상자)

- **SVG 아이콘 시스템**
  - 아이콘 리소스 디렉토리 생성 (`resources/icons/`)
  - 테마 인식 SVG 아이콘 구현 (다크 테마용 흰색, 라이트 테마용 검은색)
  - 아이콘: Add, Delete, Up, Down, Close, ComboBox 화살표
  - objectName 선택자를 통한 QSS 기반 아이콘 로딩 적용

- **UI 컴포넌트**
  - `PortSettingsWidget`: 컴팩트한 2줄 레이아웃
    - 1행: 포트 | 스캔 | 보레이트 | 열기
    - 2행: 데이터 | 패리티 | 정지 | 흐름 | DTR | RTS
  - `CommandListWidget`:
    - Prefix/Suffix 컬럼 추가 (이전 Head/Tail에서 변경)
    - 3단계 Select All 체크박스 (선택 안함, 부분 선택, 전체 선택)
    - 세로 스크롤바 항상 표시
    - 행별 Send 버튼
  - `CommandControlWidget`:
    - 전역 명령 수정을 위한 Prefix/Suffix 입력 필드 추가
    - 스크립트 저장/로드 버튼
    - 자동 실행 설정 (지연시간, 최대 실행 횟수)

#### 변경 사항 (Changed)

- **디렉토리 구조 재정리**
  - `view/resources/` → `resources/` (루트로 이동)
  - `view/styles/` → `resources/themes/` (테마 파일 통합)
  - `view/styles/theme_manager.py` → `view/theme_manager.py`
  - 모든 QSS 파일 내 아이콘 경로 업데이트 (`view/resources/` → `resources/`)

- **레이아웃 최적화**
  - `CommandControl`에서 `CommandList` 헤더로 Select All 체크박스 이동
  - 일관성을 위한 컴포넌트 크기 조정
  - Port combo 너비를 Baud combo와 동일하게 맞춤
  - 명확성을 위해 UI 요소 간 간격 추가

- **명명 규칙**
  - `CommandList` 및 `CommandControl` 전체에서 "Head/Tail"을 "Prefix/Suffix"로 변경
  - 관련된 모든 레이블, 툴팁 및 변수명 업데이트

#### 수정 사항 (Fixed)

- 두 테마 모두에서 ComboBox 드롭다운 화살표가 이제 표시됨
- 탭 닫기 버튼 아이콘이 올바르게 테마 적용됨
- Select All 체크박스가 이제 개별 행 체크박스 변경에 반응함
- Import 오류 수정 (QCheckBox, QSizePolicy)

### View 계층 개선 및 설정 관리 (2025-12-01)

#### 추가 사항 (Added)

- **View 기능 강화**
  - **색상 규칙 (Color Rules)**: `ReceivedArea`에 특정 패턴(OK, ERROR 등) 강조 기능 추가 (`config/color_rules.json`)
  - **로그 최적화 (Log Trim)**: 2000줄 초과 시 자동 삭제 기능으로 메모리 관리
  - **타임스탬프**: 수신 데이터에 타임스탬프(`[HH:MM:SS]`) 표시 옵션 추가
  - **파일 전송 UI**: ManualControlWidget에 파일 선택 및 전송 UI 추가

- **설정 관리 시스템**
  - `SettingsManager` 구현: `config/settings.json` 및 사용자 설정 관리
  - 상태 저장: 창 크기, 위치, 테마 설정을 종료 시 자동 저장 및 시작 시 복원

- **테스트 도구**
  - 독립 테스트 앱 (`tests/test_view.py`): View 컴포넌트(위젯)를 메인 로직 없이 독립적으로 테스트 가능

#### 수정 사항 (Fixed)

- `ManualControlWidget`: `file_selected` 시그널 누락 수정
- `LeftPanel`: 탭 추가 로직(`add_plus_tab`) 오류 수정
- `PortPresenter`: 파일 손상 복구 및 안정화
- `MainPresenter`: 문법 오류 수정

### UI/UX 개선 및 테마 리팩토링 (2025-12-01)

#### 변경 사항 (Changed)

- **ManualControlWidget 개선**:
  - 레이아웃을 컴팩트하게 조정 (불필요한 여백 제거)
  - 입력창을 `QTextEdit`에서 `QLineEdit`으로 변경하여 높이 축소
  - Send 버튼 높이 조정 및 스타일 적용
  - Flow Control (RTS/DTR) 체크박스 추가
- **CommandControlWidget 개선**:
  - 레이아웃 정리 및 버튼 배치 최적화
  - Start Auto Run (녹색), Stop (붉은색) 버튼에 강조 스타일 적용
- **MainWindow 개선**:
  - 좌우 패널 스플리터 비율을 2:1에서 1:1로 조정하여 균형 개선
- **테마 시스템 리팩토링**:
  - `common.qss` 도입으로 공통 스타일 통합 관리
  - `ThemeManager`가 공통 스타일과 개별 테마를 병합하여 로드하도록 개선
  - 라이트 테마에서 비활성화된 버튼의 시인성 개선 (틴트 색상 적용)

### 프로젝트 구조 (2025-11-30)

#### 추가 사항 (Added)

- Layered MVP 아키텍처 확립
- 모듈식 폴더 구조 생성:
  - `view/panels/`: LeftPanel, RightPanel, PortPanel, CommandListPanel
  - `view/widgets/`: PortSettings, CommandList, CommandControl, ManualControl
  - `resources/themes/`: 테마 관리자 및 QSS 파일
  - `resources/icons/`: SVG 아이콘
  - `doc/`: 문서 및 계획 파일

#### 변경 사항 (Changed)

- 프로젝트 이름을 "SerialManager"에서 "SerialTool"로 변경
- UI를 LeftPanel(포트 + 수동 제어) 및 RightPanel(커맨드 리스트 + 패킷 인스펙터)을 사용하도록 리팩토링
- 미사용 파일 제거 (rx_log_view.py, status_bar.py 등)

## 버전 이력 (Version History)

### [1.0.0] - 개발 중

#### 완료 (Completed)

- ✅ 프로젝트 설정 및 구조
- ✅ UI 골격 구현
- ✅ 테마 및 스타일링 시스템
- ✅ UI 레이아웃 최적화
- ✅ SVG 아이콘 시스템
- ✅ 위젯 개선 및 다듬기
- ✅ 디렉토리 구조 재정리
- ✅ View 계층 마무리 (다이얼로그, 다국어 지원)
- ✅ Command List 영속성 구현

#### 진행 중 (In Progress)

- 🔄 Core 유틸리티 (RingBuffer, ThreadSafeQueue)
- 🔄 Model 계층 (SerialWorker, PortController)
- 🔄 Presenter 통합

#### 계획 (Planned)

- ⏳ Command List 자동화 엔진
- ⏳ 파일 전송 기능
- ⏳ 플러그인 시스템
- ⏳ 테스트 및 배포

---

**범례:**

- ✅ 완료
- 🔄 진행 중
- ⏳ 계획됨
- 🐛 버그 수정
- ⚡ 성능 개선
- 🎨 UI/UX 향상
