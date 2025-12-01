# 변경 이력 (CHANGELOG)

## [미배포] (Unreleased)

### 듀얼 폰트 시스템 (2025-12-01)

#### 추가 사항 (Added)

- **폰트 시스템 개선**
  - Proportional Font (가변폭): UI 요소 (메뉴, 상태바, 레이블, 버튼 등)에 적용
    - Windows 기본: "Segoe UI" 9pt
    - Linux 기본: "Ubuntu" 9pt
  - Fixed Font (고정폭): 텍스트 데이터 (TextEdit, LineEdit, CommandList 등)에 적용
    - Windows 기본: "Consolas" 9pt
    - Linux 기본: "Monospace" 9pt
  - ThemeManager에 폰트 관리 기능 추가
    - `set_proportional_font()`, `set_fixed_font()`
    - `get_proportional_font()`, `get_fixed_font()`
  - 폰트 설정 대화상자 개선
    - Proportional/Fixed 폰트 개별 선택
    - 실시간 프리뷰
    - 크기 조절 (6pt ~ 16pt)
    - 기본값 복원 버튼

#### 변경 사항 (Changed)

- **QSS 테마 시스템**
  - 폰트 클래스 추가: `.proportional-font`, `.fixed-font`
  - 모든 위젯에 적절한 폰트 클래스 적용
- **설정 관리**
  - `settings.json`에 폰트 정보 저장/복원 기능 추가

---

### UI 구현 (2025-12-01)

#### 추가 사항 (Added)

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
  - `SettingsManager` 구현: `config/default_settings.json` 및 사용자 설정 관리
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
