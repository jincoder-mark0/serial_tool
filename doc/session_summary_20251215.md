### 아키텍처 고도화 및 확장성 강화 (2025-12-15)

#### 리팩토링 (Refactoring)

- **Strict MVP 아키텍처 적용**
  - **DTO 도입**: `PreferencesState`, `MainWindowState`, `ManualControlState` DTO를 도입하여 View와 Presenter 간의 데이터 교환을 정형화했습니다.
  - **View 로직 제거**: `PreferencesDialog`의 설정 파싱 로직과 `MainWindow`의 상태 복원(`restore_state`) 로직을 Presenter로 이관했습니다.
  - **상태 관리 이관**: `ManualControlWidget`의 명령어 히스토리 관리와 `DataLogWidget`의 파일 다이얼로그 호출 로직을 각 Presenter로 이동시켜 View를 순수한 UI 컴포넌트로 전환했습니다.

#### 기능 추가 (Feat)

- **리소스 동적 로딩 및 확장성 강화**
  - **언어/테마 자동 감지**: `LanguageManager`와 `ThemeManager`가 폴더를 스캔하여 추가된 JSON/QSS 파일을 자동으로 인식하도록 개선했습니다.
  - **설정 변경 이벤트**: `EventBus`에 `SETTINGS_CHANGED` 토픽을 추가하여, 설정 변경 시 `MainPresenter`를 거치지 않고 각 컴포넌트가 독립적으로 반응하도록 개선했습니다.
  - **언어 메타데이터**: 언어 파일(`*.json`)에 `_meta_lang_name` 키를 추가하여 UI 표시 이름을 파일 내에서 정의하도록 했습니다.

#### 수정 사항 (Fixed)

- **안정성 강화**
  - `FileTransferEngine`(`QRunnable`)의 `run()` 메서드 전체에 예외 처리 안전망을 구축하고 `GlobalErrorHandler`와 연동하여, 백그라운드 스레드에서 발생하는 예외가 무시되지 않도록 수정했습니다.
  - **UI 스타일**: `common.qss`에 `QSmartTextEdit`의 기본 속성(Fallback)을 명시하여 테마 로드 실패 시에도 UI 가독성을 보장하도록 개선했습니다.
