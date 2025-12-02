# SerialTool 작업 목록 (Task List)

## 프로젝트 개요
Python 3 + PyQt5 + PySerial 기반 멀티포트 시리얼 통신 관리 애플리케이션 개발
- **아키텍처**: Layered MVP (Model-View-Presenter)
- **목표**: 고성능, 안정성, 확장성을 갖춘 전문 엔지니어링 도구

---

## Phase 1: 프로젝트 초기 설정 및 구조 확립
- [x] 프로젝트 구조 생성
  - [x] 폴더 구조 생성 (`core/`, `model/`, `view/`, `presenter/`, `plugins/`, `tests/`, `doc/`)
  - [x] `requirements.txt` 작성 (PyQt5, pyserial, requests 등)
  - [x] `README.md` 작성 (프로젝트 개요, 설치 가이드)
  - [x] `version.py` 및 `default_settings.json` 템플릿 작성
  - [x] `main.py` 진입점 작성
- [x] 프로젝트 명칭 변경
  - [x] `SerialManager` → `SerialTool` 변경
  - [x] 관련 코드 및 문서 업데이트

---

## Phase 2: UI 구현 및 테마 시스템 (✅ 완료)
- [x] UI 기본 골격 구현
  - [x] `MainWindow` (레이아웃, 스플리터, 메뉴, 툴바)
  - [x] `LeftPanel` (포트 탭 + 수동 제어)
  - [x] `RightPanel` (커맨드 리스트 + 패킷 인스펙터)
- [x] 위젯 구현 및 리팩토링
  - [x] `PortSettingsWidget` (컴팩트 2줄 레이아웃)
  - [x] `ReceivedArea` (로그 뷰, 색상 규칙, 타임스탬프, Trim)
  - [x] `ManualControlWidget` (수동 전송, 파일 선택 UI)
  - [x] `CommandListWidget` (Prefix/Suffix, 3단계 체크박스, Send 버튼)
  - [x] `CommandControlWidget` (스크립트 저장/로드, Auto Run 설정)
  - [x] `PacketInspectorWidget` (패킷 상세 뷰)
- [x] 테마 및 스타일링 시스템
  - [x] `ThemeManager` 구현 (QSS 로딩 및 동적 전환)
  - [x] 듀얼 폰트 시스템 구현
    - [x] Proportional Font: UI 요소 (메뉴, 상태바, 레이블, 버튼 등)
    - [x] Fixed Font: 텍스트 데이터 (TextEdit, LineEdit, CommandList 등)
    - [x] ThemeManager에 폰트 관리 기능 추가
    - [x] 폰트 설정 대화상자 개선
  - [x] `common.qss` (공통 스타일)
  - [x] `dark_theme.qss` (다크 테마)
  - [x] `light_theme.qss` (라이트 테마)
  - [x] SVG 아이콘 시스템 (테마별 색상 자동 변경)
  - [x] 폰트 커스터마이징 기능 (View → Font 메뉴)
- [x] 디렉토리 구조 재정리
  - [x] `view/resources/` → `resources/` (루트로 이동)
  - [x] `view/styles/` → `resources/themes/`
  - [x] 모든 경로 참조 업데이트
- [x] 코드 품질 개선
  - [x] 전체 코드베이스 한국어 주석 및 Docstring 번역
  - [x] 타입 힌트 검증 및 개선 (모든 함수/메서드)
  - [x] Docstring 표준화 (Args, Returns 포함)
- [x] 견고성 개선
  - [x] ThemeManager 폴백 스타일시트 구현
  - [x] SettingsManager 폴백 메커니즘 검증
- [x] View 계층 보완 (Spec 10, 11, 17)
  - [x] PreferencesDialog 구현 (Spec 17)
  - [x] AboutDialog 구현 (Spec 10.4.1)
  - [x] ReceivedArea 검색 바 (Regex 지원) 구현 (Spec 11.3.1)
  - [x] PortSettingsWidget BaudRate Validator 추가 (Spec 11.1.2)
  - [x] FileProgressWidget UI 구현 (Spec 11.2.3)
- [x] View 계층 마무리 및 다국어 지원
  - [x] settings.json command_list 기본값 추가
  - [x] LanguageManager 구현 (i18n)
  - [x] test_view.py 테스트 케이스 보완 (Dialogs, FileProgress, Language)
- [x] Command List Persistence (자동 저장)
  - [x] CommandListWidget 데이터 내보내기/가져오기 구현
  - [x] CommandListPanel 설정 연동 (자동 저장/로드)


---

## Phase 3: Core 유틸리티 구현 (🔄 진행 중)
- [ ] `core/utils.py`
  - [ ] `RingBuffer` 구현 (512KB 원형 버퍼)
    - [ ] 고속 데이터 수신 처리
    - [ ] 오버플로우 처리
    - [ ] 단위 테스트 작성
  - [ ] `ThreadSafeQueue` 구현
    - [ ] TX 큐 관리 (최대 128 chunks)
    - [ ] 스레드 안전성 보장
    - [ ] 단위 테스트 작성
- [ ] `core/event_bus.py`
  - [ ] EventBus 아키텍처 구현
  - [ ] Publish/Subscribe 메커니즘
  - [ ] 표준 이벤트 타입 정의
  - [ ] 플러그인 연동 인터페이스
- [x] `core/settings_manager.py`
  - [x] JSON 기반 설정 저장/로드
  - [x] 전역 설정 관리
  - [x] 포트별 프로파일 관리
  - [x] 백업/복원 기능
- [ ] `core/logger.py`
  - [ ] 로깅 계층 구현 (UI, File, Performance)
  - [ ] RotatingFileHandler 구성
  - [ ] 색상 규칙 및 타임스탬프
  - [ ] 로그 필터링 및 검색

---

## Phase 4: Model 계층 구현 (🔄 진행 중)
- [ ] `model/serial_worker.py`
  - [ ] `SerialWorker(QThread)` 구현
    - [ ] Non-blocking I/O 루프
    - [ ] RingBuffer 연동
    - [ ] 수신 데이터 시그널 발행
    - [ ] 안전 종료 시퀀스
  - [ ] TX 큐 처리 로직
  - [ ] 에러 처리 및 복구
  - [ ] 단위 테스트 (Virtual Serial Port)
- [ ] `model/port_controller.py`
  - [ ] 포트 라이프사이클 관리
  - [ ] 상태 머신 구현 (Closed/Opening/Open/Error)
  - [ ] 포트별 Worker 관리
  - [ ] 멀티포트 격리 보장
  - [ ] 통합 테스트
- [ ] `model/serial_manager.py`
  - [ ] PortRegistry 구현
  - [ ] 멀티포트 관리
  - [ ] 포트 스캔 기능
  - [ ] 포트 상태 모니터링
- [ ] `model/packet_parser.py`
  - [ ] Parser Factory 패턴 구현
  - [ ] DelimiterParser (개행, 커스텀 구분자)
  - [ ] FixedLengthParser (고정 길이 패킷)
  - [ ] ATParser (AT 명령 응답 파싱)
  - [ ] HexParser (바이너리 데이터)
  - [ ] Expect/Timeout 처리
  - [ ] 단위 테스트
- [ ] `model/command_entry.py`
  - [ ] CommandEntry DTO 정의
  - [ ] JSON 직렬화/역직렬화
  - [ ] 검증 규칙
- [ ] `model/cl_runner.py`
  - [ ] Command List 실행 엔진
  - [ ] 상태 머신 (Idle/Running/Paused/Stopped)
  - [ ] 순차 실행, 반복, 지연 처리
  - [ ] Expect 매칭 및 Timeout
  - [ ] 조건부 분기 (선택 기능)
  - [ ] 변수 치환 (선택 기능)
  - [ ] 실행 결과 리포트
  - [ ] 통합 테스트
- [ ] `model/file_transfer.py`
  - [ ] FileTransferEngine 구현 (QRunnable)
  - [ ] Chunk 기반 전송
  - [ ] 적응형 Chunk Size
  - [ ] 진행률 업데이트 시그널
  - [ ] 취소 및 재시도 메커니즘
  - [ ] 에러 처리
  - [ ] 통합 테스트 (대용량 파일)

---

## Phase 5: Presenter 계층 구현 및 통합 (⏳ 대기)
- [ ] `presenter/event_router.py`
  - [ ] EventBus 기반 이벤트 라우팅
  - [ ] View ↔ Model 연결
  - [ ] 플러그인 이벤트 처리
- [ ] `presenter/main_presenter.py`
  - [ ] 중앙 제어 로직
  - [ ] 애플리케이션 초기화
  - [ ] 설정 로드/저장
  - [ ] 종료 시퀀스
- [ ] `presenter/port_presenter.py`
  - [ ] 포트 열기/닫기 로직
  - [ ] 설정 변경 처리
  - [ ] 데이터 송수신 연동
  - [ ] 상태 업데이트 (UI ↔ Model)
  - [ ] 통합 테스트
- [ ] `presenter/command_presenter.py`
  - [ ] Command List 실행 제어
  - [ ] Run/Stop/Pause 로직
  - [ ] 스크립트 저장/로드
  - [ ] Auto Run 스케줄링
  - [ ] 통합 테스트
- [ ] `presenter/file_presenter.py`
  - [ ] 파일 전송 제어
  - [ ] 진행률 업데이트
  - [ ] 취소 처리
  - [ ] 통합 테스트

---

## Phase 6: 고급 기능 구현 (⏳ 대기)
- [ ] 설정 및 프로파일 시스템
  - [x] SettingsManager 기본 구현
  - [ ] Preferences Dialog 구현
    - [ ] 탭 구조 (General, Port, UI, Advanced)
    - [ ] 실시간 미리보기
    - [ ] Reset to Defaults
  - [ ] 포트 프로파일 관리
    - [ ] 프로파일 저장/로드
    - [ ] 프로파일 목록 UI
  - [ ] Command List 프로파일
  - [ ] Import/Export 기능
  - [ ] 버전 마이그레이션
- [ ] 로깅 시스템 고도화
  - [ ] 파일 로깅 (RotatingFileHandler)
  - [ ] 성능 모니터링 로그 (CSV)
  - [ ] 로그 내보내기 (TXT, CSV, HTML)
  - [ ] 분석 리포트 자동 생성
  - [ ] 민감 정보 마스킹
- [ ] 패킷 인스펙터 고급 기능
  - [ ] 실시간 패킷 표시
  - [ ] 필터링 및 검색
  - [ ] HEX/ASCII 듀얼 뷰
  - [ ] 패킷 통계
  - [ ] 내보내기 기능

---

## Phase 7: 플러그인 시스템 (⏳ 대기)
- [ ] `core/plugin_base.py`
  - [ ] PluginBase 인터페이스 정의
  - [ ] AppContext 제공 객체
  - [ ] 플러그인 메타데이터
- [ ] `core/plugin_loader.py`
  - [ ] 동적 플러그인 로딩
  - [ ] 부팅 시 자동 로드
  - [ ] 핫 리로딩 지원
  - [ ] 예외 격리
  - [ ] 샌드박싱 (선택)
- [ ] `plugins/example_plugin.py`
  - [ ] 샘플 플러그인 구현
  - [ ] EventBus 연동 예제
  - [ ] UI 확장 예제
- [ ] 플러그인 관리 UI
  - [ ] Plugins 대화상자
  - [ ] 활성화/비활성화
  - [ ] 설치/제거
  - [ ] 설정 관리

---

## Phase 8: 테스트 및 품질 보증 (⏳ 대기)
- [ ] 단위 테스트 (Unit Tests)
  - [ ] Core 모듈 테스트 (RingBuffer, Queue, EventBus)
  - [ ] Model 모듈 테스트 (Parser, CLRunner, FileTransfer)
  - [ ] 커버리지 70%+ 목표
- [ ] 통합 테스트 (Integration Tests)
  - [ ] Virtual Serial Port 환경 구축
  - [ ] 포트 열기/닫기 시퀀스
  - [ ] 데이터 송수신 루프백
  - [ ] 멀티포트 동시성
  - [ ] Command List 실행
  - [ ] 파일 전송
- [ ] E2E 테스트 (pytest-qt)
  - [ ] UI 워크플로우 테스트
  - [ ] 사용자 시나리오 재현
  - [ ] 장기 런 테스트 (24시간+)
- [ ] 성능 벤치마크
  - [ ] Rx 처리량 (2MB/s 목표)
  - [ ] UI 렌더링 (10K lines/s)
  - [ ] 패킷 파서 지연 (1ms 이하)
  - [ ] 파일 전송 속도 (100KB/s+)
- [ ] 코드 품질
  - [ ] 타입 힌트 검증 (mypy)
  - [ ] 코드 포맷팅 (black)
  - [ ] Lint 검사 (pylint/flake8)
  - [ ] 문서화 (docstring)

---

## Phase 9: 배포 및 패키징 (⏳ 대기)
- [ ] PyInstaller 설정
  - [ ] `pyinstaller.spec` 작성
  - [ ] Windows 빌드 (단일 실행 파일)
  - [ ] Linux 빌드 (AppImage)
  - [ ] macOS 빌드 (선택)
  - [ ] 크기 최적화
- [ ] 배포 아티팩트 구성
  - [ ] 실행 파일
  - [ ] 설정 파일 템플릿
  - [ ] 샘플 플러그인
  - [ ] 문서 (README, CHANGELOG)
- [ ] CI/CD 파이프라인
  - [ ] GitHub Actions 워크플로우
  - [ ] 자동 테스트 실행
  - [ ] 자동 빌드
  - [ ] 릴리스 자동화
- [ ] 자동 업데이트 (선택)
  - [ ] GitHub Release API 연동
  - [ ] 버전 체크
  - [ ] 다운로드 및 설치
- [ ] 사용자 문서
  - [ ] 사용자 가이드
  - [ ] 개발자 문서
  - [ ] API 레퍼런스
  - [ ] 플러그인 개발 가이드

---

## Phase 10: 최종 검증 및 릴리스 (⏳ 대기)
- [ ] 수락 기준 검증
  - [ ] 포트 관리 기능
  - [ ] 데이터 수신/표시
  - [ ] Command List / Auto Run
  - [ ] 파일 송수신
  - [ ] 설정 저장·복원
  - [ ] 플러그인 / EventBus
- [ ] 플랫폼별 검증
  - [ ] Windows 10/11
  - [ ] Ubuntu 20.04+
  - [ ] Debian 11+
  - [ ] macOS 12.0+ (선택)
- [ ] 성능 검증
  - [ ] 멀티포트 (최대 16개)
  - [ ] 고속 스트림 (2MB/s)
  - [ ] UI 반응성 (60fps)
  - [ ] 장기 런 안정성
- [ ] 문서 최종 업데이트
  - [ ] CHANGELOG.md
  - [ ] README.md
  - [ ] Implementation_Specification.md
  - [ ] 릴리스 노트
- [ ] v1.0.0 릴리스
  - [ ] GitHub Release 생성
  - [ ] 배포 패키지 업로드
  - [ ] 릴리스 공지

---

## 현재 상태 (2025-12-02 기준)
- ✅ **Phase 1**: 프로젝트 초기 설정 완료
- ✅ **Phase 2**: UI 구현 및 테마 시스템 완료 (듀얼 폰트 시스템, 코드 품질 개선, 견고성 개선 포함)
- 🔄 **Phase 3**: Core 유틸리티 구현 진행 중 (SettingsManager 완료)
- 🔄 **Phase 4**: Model 계층 구현 진행 중 (SerialWorker, PortController 작업 필요)
- ⏳ **Phase 5-10**: 대기 중

## 다음 단계 우선순위
1. **Core 유틸리티 완성**: RingBuffer, ThreadSafeQueue, EventBus 구현
2. **Model 계층 구현**: SerialWorker, PortController 구현 및 테스트
3. **Presenter 연동**: UI와 Model 연결, 실제 시리얼 통신 활성화
4. **Command List 자동화**: CLRunner 구현 및 Auto Run 기능
5. **파일 전송 기능**: FileTransferEngine 구현
6. **테스트 및 검증**: 단위/통합 테스트 작성 및 실행
7. **배포 준비**: PyInstaller 빌드 및 최종 검증

---

**범례:**
- ✅ 완료
- 🔄 진행 중
- ⏳ 대기
- ❌ 차단됨
