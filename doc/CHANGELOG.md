# 변경 이력 (CHANGELOG)

## [미배포] (Unreleased)

### UI/UX 개선 및 버그 수정 (2025-12-08)

#### 추가 사항 (Added)

- **SmartNumberEdit 위젯**
  - `view/widgets/common/smart_number_edit.py` 신규 생성
  - HEX 모드와 일반 텍스트 모드 지원
  - HEX 모드 시 0-9, A-F, 공백만 입력 허용
  - 자동 대문자 변환 기능
  - `ManualControlWidget` 입력 필드에 적용

- **PortTabWidget 위젯**
  - `view/widgets/port_tab_widget.py` 신규 생성
  - 포트 탭 관리 로직 캡슐화 (추가/삭제/플러스 탭)
  - `LeftSection`에서 `QTabWidget` 대신 `PortTabWidget` 사용
  - 코드 재사용성 및 유지보수성 향상

- **테마별 SVG 아이콘 지원**
  - `ThemeManager.get_icon()` 메서드 추가
  - 테마에 따라 `resources/icons/{name}_{theme}.svg` 로드
  - `add_dark.svg`, `add_light.svg` 아이콘 생성
  - 플러스 탭에 테마별 아이콘 적용

- **포트 탭 이름 수정 기능**
  - 탭 이름 형식: `[커스텀명]:포트명`
  - 탭 더블클릭 시 커스텀 이름 수정 다이얼로그 표시
  - 포트 변경 시 자동으로 탭 제목 업데이트
  - 커스텀 이름 저장/복원 기능
  - `PortPanel`에 `tab_title_changed` 시그널 추가

#### 수정 사항 (Fixed)

- **CommandListWidget Send 버튼 상태 버그**
  - 행 이동 시 Send 버튼 활성화 상태가 초기화되는 문제 수정
  - `_move_row` 메서드에서 이동 전 버튼 상태 저장 후 복원

- **포트 탭 닫기 버튼 문제**
  - `insertTab` 사용 시 닫기 버튼이 사라지는 버그 수정
  - 플러스 탭 제거 → 새 탭 추가 → 플러스 탭 재추가 방식으로 변경
  - 모든 탭의 닫기 버튼이 정상적으로 표시됨

#### 변경 사항 (Changed)

- **설정 키 일관성 확보**
  - `SettingsManager`, `PreferencesDialog`, `MainWindow`에서 `menu_theme`, `menu_language` 키 통일
  - `settings.json`의 `global.theme`, `global.language`와 내부 키 간 명확한 매핑 확립

- **LeftSection 리팩토링**
  - `PortTabWidget` 사용으로 탭 관리 코드 간소화
  - `add_new_port_tab`, `close_port_tab`, `on_tab_changed` 등 메서드 제거 (캡슐화)

#### 이점 (Benefits)

- **사용자 경험 향상**: HEX 모드 입력 제한으로 오류 방지, 탭 이름 수정으로 사용자 정의 가능
- **코드 품질 개선**: 위젯 캡슐화로 재사용성 및 유지보수성 향상
- **테마 일관성**: 모든 UI 요소에 테마가 올바르게 적용됨
- **안정성 향상**: 버튼 상태 및 탭 닫기 버그 수정으로 사용자 경험 개선

---

### 문서화 및 가이드 개선 (2025-12-05)

### 문서화 및 가이드 개선 (2025-12-05)

#### 추가 사항 (Added)

- **주석 가이드 문서**
  - `guide/comment_guide.md` 신규 생성: Google Style Docstring 표준 가이드
  - Google Style 정의 및 공식 문서 링크 추가
  - 모듈/클래스/함수 Docstring 작성 규칙 상세화
  - 인라인 주석 작성 규칙 (블록 주석, 분기문, 수식, TODO/FIXME/NOTE 태그)
  - MkDocs 자동 문서화 설정 가이드
  - 체크리스트 제공

- **Git 관리 가이드 문서**
  - `guide/git_guide.md` 신규 생성
  - 커밋 메시지 규칙 (Header/Body/Footer, 태그별 예시)
  - PR 및 이슈 템플릿 가이드
  - 실무 Git 레시피 (Amend, Stash, Reset/Revert 등 복구 명령어)
  - 브랜치 전략 상세

- **View 구현 계획 보강**
  - `view/doc/implementation_plan.md`에 Packet Inspector 설정 섹션 추가
  - Parser 타입 선택 (Auto/AT/Delimiter/Fixed Length/Raw)
  - Delimiter 설정 (기본값 + 사용자 정의)
  - AT Parser 색상 규칙 설정
  - Inspector 동작 옵션 (버퍼 크기, 실시간 추적, 자동 스크롤)
  - Preferences 다이얼로그 탭 UI 레이아웃 정의

#### 변경 사항 (Changed)

- **README.md 업데이트**
  - 프로젝트 설명: "시리얼 통신 유틸리티" → "통신 유틸리티" (SPI, I2C 확장 예정 명시)
  - 폴더 구조 정리: `guide/` 폴더 분리, 중복 파일 제거
  - 향후 계획 상세화: 단기/중장기 구분, FT4222/SPI/I2C 지원 로드맵 추가
  - 문서 참조 표 보강: 코딩 규칙, 명명 규칙 추가
  - Git 관리 가이드 강화: 지속적 백업 권장 명시

- **코드 스타일 가이드 간소화**
  - `guide/code_style_guide.md`에서 Docstring 상세 내용 제거 (117줄 → 31줄)
  - 주석 관련 내용을 `guide/comment_guide.md` 참조로 대체
  - 기본 원칙과 간단한 예시만 유지

- **구현 계획 우선순위 조정**
  - `view/doc/implementation_plan.md` 우선순위 섹션에서 일정 표기 제거
  - Packet Inspector 설정을 선택적 항목으로 추가

#### 이점 (Benefits)

- **문서 체계화**: 주석 가이드를 독립 문서로 분리하여 관리 용이
- **확장성 명시**: README에 향후 프로토콜 확장 계획 명확히 전달
- **개발 가이드 강화**: Google Style Docstring 표준 및 작성 규칙 상세화
- **View 계층 완성도**: Packet Inspector UI 설정 요구사항 문서화

### MVP 아키텍처 리팩토링 및 코드 품질 개선 (2025-12-05)

#### 변경 사항 (Changed)

- **MVP 아키텍처 준수**
  - `ManualControlWidget`에서 `SettingsManager` 직접 호출 제거
  - `send_command_requested` 시그널 변경: 3개 파라미터 → 4개 파라미터 (text, hex_mode, use_prefix, use_suffix)
  - View는 원본 사용자 입력과 체크박스 상태만 전달
  - prefix/suffix 처리 로직을 `MainPresenter.on_send_command_requested()`로 이동
  - View 계층에서 비즈니스 로직 40+ 라인 제거

- **네이밍 규칙 문서 통합**
  - `docs/naming_convention.md`에 모든 네이밍 규칙 통합 (클래스, 함수, 변수, 상수, 언어 키 등)
  - `doc/code_style_guide.md`에서 중복 내용 제거, 참조 링크로 대체
  - 단일 문서로 일관성 및 유지보수성 향상

- **Logger 싱글톤 패턴 개선**
  - 예외 발생 방식에서 `__new__` + `_initialized` 패턴으로 변경
  - `SettingsManager`와 동일한 구현 방식 적용
  - 다중 인스턴스 생성 시도 시 안전하게 동일 인스턴스 반환

- **설정 구조 리팩토링**
  - 평탄한 `global.*` 네임스페이스에서 논리적 그룹으로 재구조화
  - 새로운 그룹: `serial.*`, `command.*`, `logging.*`, `ui.*`
  - `main_window.py` `apply_preferences()` 메서드에 settings_map 추가
  - `main_presenter.py`에서 `global.command_prefix` → `command.prefix` 경로 변경
  - `settings.json` 구조 개선

#### 이점 (Benefits)

- **아키텍처 개선**: View와 Presenter 책임 분리 명확화, MVP 패턴 준수
- **문서 통합**: 단일 소스로 네이밍 규칙 참조, 문서 관리 일원화
- **안정성 향상**: Logger 싱글톤 패턴 개선으로 애플리케이션 안정성 증대
- **설정 관리**: 논리적 그룹화로 장기 유지보수 용이

### 문서 및 Preferences 다이얼로그 개선 (2025-12-04)

#### 변경 사항 (Changed)

- **코딩 스타일 가이드 업데이트**
  - `doc/code_style_guide.md`에 언어 키 네이밍 규칙 섹션(5.1) 추가
  - `[context]_[type]_[name]` 형식 엄격히 정의
  - UI 요소 타입별 분류 (`btn`, `lbl`, `chk`, `combo`, `input`, `grp`, `col`, `tab`, `dialog`, `txt`, `tooltip`)
  - 올바른/잘못된 예시 제공
  - 특수 케이스 문서화 (다이얼로그 타이틀, 상태 메시지, 필터 문자열)

- **설정 키 일관성 확보**
  - `SettingsManager`의 Fallback 설정 키를 `menu_theme`, `menu_language`로 통일
  - `PreferencesDialog`와 `MainWindow` 간의 설정 키 매핑 불일치 해결
  - `settings.json`의 `global.theme`, `global.language`와 내부 키(`menu_theme`, `menu_language`) 간의 명확한 매핑 로직 확립

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
