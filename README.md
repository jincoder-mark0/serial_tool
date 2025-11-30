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
  * 폰트 커스터마이징 (View → Font)
  * SVG 기반 테마 적응형 아이콘
  * 컴팩트한 2줄 포트 설정 레이아웃
  * 3단계 Select All 체크박스 (전체/부분/없음)

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
    pip install -r serial_manager/requirements.txt
    ```

### 실행 (Running)

**가상 환경을 활성화한 상태에서** `serial_manager` 디렉토리 내의 `main.py`를 실행합니다.

```bash
# 가상 환경 활성화 후
python serial_manager/main.py
```

## 현재 개발 상태 (Development Status)

### 완료 항목 ✅

* 프로젝트 구조 및 기본 설정

* UI 골격 및 위젯 구현
* 테마 시스템 (Dark/Light)
* SVG 아이콘 시스템
* 레이아웃 최적화
* Prefix/Suffix 기능

### 진행 중 🔄

* Core 유틸리티 (RingBuffer, ThreadSafeQueue)

* Model 계층 (SerialWorker, PortController)
* Presenter 통합

### 예정 ⏳

* 시리얼 통신 로직

* Command List 자동화
* 파일 전송
* 플러그인 시스템

## 프로젝트 구조 (Project Structure)

```
serial_manager/
├── core/           # 핵심 유틸리티 (EventBus, RingBuffer 등)
├── model/          # 데이터 모델 및 비즈니스 로직 (SerialWorker 등)
├── view/           # UI 컴포넌트
│   ├── panels/     # 주요 패널 (LeftPanel, RightPanel 등)
│   ├── widgets/    # 재사용 가능한 위젯 (CommandList, ManualControl 등)
│   └── theme_manager.py  # 테마 관리자
├── presenter/      # MVP 패턴의 Presenter 계층
├── resources/      # 리소스 파일
│   ├── icons/      # SVG 아이콘 (테마별 white/black 변형)
│   └── themes/     # QSS 테마 파일 (dark_theme.qss, light_theme.qss)
├── doc/            # 문서 (CHANGELOG, 명세서 등)
└── main.py         # 애플리케이션 진입점
```

## 기여 (Contributing)

버그 신고 및 기능 제안은 Issue를 통해 환영합니다. Pull Request도 언제나 환영합니다.

## 라이선스

MIT License
