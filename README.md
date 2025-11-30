# Serial Tool v1.0

**Serial Tool**는 Python 3와 PyQt5를 기반으로 개발된 고성능 멀티포트 시리얼 통신 관리 도구입니다. 임베디드 엔지니어 및 개발자를 위해 설계되었으며, 실시간 로그 모니터링, 자동화 스크립트 실행, 파일 전송 등의 기능을 제공합니다.

## 주요 기능

- **멀티포트 지원**: 여러 시리얼 포트를 동시에 열고 독립적으로 제어 가능
- **고성능 로그 뷰**: 대량의 로그 데이터를 끊김 없이 표시 (RingBuffer 및 배치 렌더링 적용)
- **Command List**: JSON 기반의 명령 리스트 관리 및 자동 실행 (Expect/Timeout 지원)
- **파일 전송**: Chunk 기반의 안정적인 파일 송수신
- **플러그인 시스템**: 사용자 정의 파서 및 기능 확장 지원

## 설치 및 실행

### 요구 사항

- Python 3.10 이상
- Windows, Linux, 또는 macOS

### 설치

1. 저장소를 클론하거나 다운로드합니다.
2. 의존성 패키지를 설치합니다:
   ```bash
   pip install -r requirements.txt
   ```

### 실행

```bash
python main.py
```

## 프로젝트 구조

- `core/`: 공통 유틸리티, 설정 관리, EventBus
- `model/`: 비즈니스 로직 (SerialWorker, PortController 등)
- `view/`: UI 위젯 및 메인 윈도우
- `presenter/`: View와 Model을 연결하는 Presenter
- `plugins/`: 확장 플러그인 디렉토리

## 라이선스

MIT License
