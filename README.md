# SerialTool v1.0

**SerialTool**은 Python과 PyQt5로 개발된 강력한 시리얼 통신 유틸리티입니다. 기존 QCOM의 사용자 경험을 계승하면서, 멀티 포트 지원, 스크립트 자동화, 플러그인 시스템 등 현대적인 기능을 제공합니다.

## 주요 기능 (Key Features)

* **멀티 포트 지원 (Multi-Port Support)**: 탭 인터페이스를 통해 여러 시리얼 포트를 동시에 연결하고 제어할 수 있습니다.
* **강력한 수동 제어 (Manual Control)**:
  * HEX / ASCII 모드 지원
  * CR/LF 자동 추가 옵션
  * **Flow Control (RTS/DTR) 제어**
  * 파일 전송 기능
  * 로그 저장 및 화면 클리어
* **커맨드 리스트 자동화 (Command List Automation)**:
  * 여러 명령어를 리스트로 관리하고 순차적으로 실행
  * 자동 반복 실행 (Auto Run) 및 지연 시간(Delay) 설정
  * 스크립트 저장 및 불러오기 (JSON 형식)
* **실시간 모니터링 (Real-time Monitoring)**:
  * Tx/Rx 바이트 카운트
  * 패킷 인스펙터 (Packet Inspector)를 통한 상세 데이터 분석
* **사용자 친화적 UI**:
  * 직관적인 좌우 패널 구조 (Left: 포트/제어, Right: 리스트/인스펙터)
  * 모든 기능에 툴팁 제공
  * 다크/라이트 테마 전환 지원 (View → Theme)
  * 듀얼 폰트 시스템 (Ctrl+Shift+F로 설정)
  * SVG 기반 테마 적응형 아이콘
  * 컴팩트한 2줄 포트 설정 레이아웃
  * 3단계 Select All 체크박스 (전체/부분/없음)
  * **색상 규칙 (Color Rules)**: OK(녹색), ERROR(빨강) 등 패턴 강조
  * **설정 저장**: 창 크기, 위치, 테마, 폰트 설정 자동 저장
  * **견고성**: 설정/테마 파일 누락 시 자동 복구

## 설치 및 실행 (Installation & Usage)

### 요구 사항 (Requirements)

* Python 3.8 이상
* 필수 라이브러리: `PyQt5`, `pyserial`

### 설치 (Installation)

1. 저장소를 클론합니다.

    ```bash
    git clone https://github.com/yourusername/SerialTool.git
    cd SerialTool
    ```

2. 의존성 라이브러리를 설치합니다.

    ```bash
    # 가상 환경 생성 (권장)
    python -m venv .venv
    
    # 가상 환경 활성화
    # Windows:
    .venv\Scripts\activate
    # Linux/Mac:
    source .venv/bin/activate
    
    # 패키지 설치
    pip install -r requirements.txt
    ```

### 실행 (Running)

**가상 환경을 활성화한 상태에서** `main.py`를 실행합니다.

```bash
# 가상 환경 활성화 후
python main.py
```

## 현재 개발 상태 (Development Status)

### 완료 항목 ✅

* 프로젝트 구조 및 기본 설정
* UI 골격 및 위젯 구현
* 테마 시스템 (Dark/Light)
* 듀얼 폰트 시스템 (Proportional/Fixed)
* SVG 아이콘 시스템
* 레이아웃 최적화
* View 계층 개선 (색상 규칙, Trim, 타임스탬프)
* 설정 관리 시스템 (SettingsManager)
* 코드 품질 개선 (한국어화, 타입 힌트, Docstring)
* 견고성 개선 (폴백 메커니즘)

### 진행 중 🔄

* Core 유틸리티 (RingBuffer, ThreadSafeQueue, EventBus)
* Model 계층 (SerialWorker, PortController)
* Presenter 통합

### 예정 ⏳

* Command List 자동화 엔진
* 파일 전송 기능
* 플러그인 시스템

## 프로젝트 구조

```
serial_tool2/
├── core/           # 핵심 유틸리티
├── model/          # 비즈니스 로직
├── view/           # UI 컴포넌트
│   ├── panels/     # 패널 (LeftPanel, RightPanel)
│   ├── widgets/    # 위젯 (PortSettings, ReceivedArea 등)
│   └── dialogs/    # 대화상자 (FontSettingsDialog)
├── presenter/      # Presenter 계층
├── resources/      # 리소스 파일
│   ├── icons/      # SVG 아이콘
│   └── themes/     # QSS 테마 파일
├── config/         # 설정 파일
├── tests/          # 테스트 코드
├── doc/            # 문서
├── ignore/         # 연습용/테스트 파일 (Git 무시)
└── main.py         # 애플리케이션 진입점
```

## 개발 가이드라인

### Git 버전 관리
본 프로젝트는 **Git을 통한 지속적인 백업**을 권장합니다:
- 기능 단위로 자주 커밋 (최소 하루 1회 이상)
- 브랜치 전략: `main` (안정), `feature/기능명` (개발)
- 커밋 메시지는 한국어로 작성 (`Feat:`, `Fix:`, `Docs:` 등)
- 상세 가이드: [`doc/code_style_guide.md`](doc/code_style_guide.md) 참조

### 코드 스타일
- PEP 8 준수
- 모든 주석 및 Docstring은 한국어
- 타입 힌트 필수
- 상세 가이드: [`doc/code_style_guide.md`](doc/code_style_guide.md)

## 기여 (Contributing)

버그 신고 및 기능 제안은 Issue를 통해 환영합니다. Pull Request도 언제나 환영합니다.

## 라이선스

MIT License
