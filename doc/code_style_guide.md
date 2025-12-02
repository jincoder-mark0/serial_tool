# SerialTool 코드 스타일 가이드

이 문서는 SerialTool 프로젝트의 코딩 표준 및 스타일 가이드라인을 설명합니다. 이 가이드라인을 준수함으로써 코드의 일관성, 가독성 및 유지보수성을 보장합니다.

## 1. 일반 Python 표준
- **PEP 8**: Python 코드에 대한 표준 [PEP 8](https://peps.python.org/pep-0008/) 스타일 가이드를 따릅니다.
- **들여쓰기**: 들여쓰기에는 4개의 공백을 사용합니다. 탭(Tab)은 사용하지 않습니다.
- **줄 길이**: 가능한 한 줄 길이를 79자로 제한하지만, 복잡한 표현식이나 긴 문자열의 경우 최대 100자까지 허용됩니다.
- **Import**:
    - 표준 라이브러리 import를 가장 먼저 작성합니다.
    - 서드파티 라이브러리 import를 두 번째로 작성합니다 (예: PyQt5, serial).
    - 로컬 애플리케이션 import를 마지막에 작성합니다.
    - 와일드카드 import (`from module import *`)는 피합니다.

## 2. 한글화 (Localization)
- **주석**: 모든 코드 주석은 **한국어**로 작성해야 합니다.
- **Docstring**: 모든 Docstring은 **한국어**로 작성해야 합니다.
- **커밋 메시지**: Git 커밋 메시지는 **한국어**로 작성해야 합니다.

## 3. Docstrings
- **형식**: Google 스타일 Docstring 형식을 사용합니다.
- **내용**:
    - **요약**: 클래스나 함수가 수행하는 작업에 대한 간략한 설명.
    - **Args**: 각 인수에 대한 상세 설명 및 타입.
    - **Returns**: 반환 값 및 타입에 대한 설명.
    - **Raises**: (선택 사항) 발생할 수 있는 예외 목록.

### 예시
```python
def connect_to_port(self, port_name: str, baudrate: int) -> bool:
    """
    지정된 시리얼 포트에 연결합니다.
    
    Args:
        port_name (str): 연결할 포트 이름 (예: "COM3").
        baudrate (int): 통신 속도 (예: 115200).
        
    Returns:
        bool: 연결 성공 시 True, 실패 시 False.
    """
    # 구현 내용...
```

## 4. 타입 힌팅 (Type Hinting)
- **필수**: 모든 함수 인수 및 반환 값에 대해 타입 힌트가 필수입니다.
- **Typing 모듈**: 복잡한 타입의 경우 `typing` 모듈(예: `List`, `Dict`, `Optional`, `Any`)을 사용합니다.
- **클래스 타입**: 적절한 경우 클래스 이름을 타입 힌트로 사용합니다.

### 예시
```python
from typing import List, Optional

def get_available_ports() -> List[str]:
    """
    사용 가능한 시리얼 포트 목록을 반환합니다.
    
    Returns:
        List[str]: 포트 이름 리스트.
    """
    # 구현 내용...
```

## 5. 명명 규칙 (Naming Conventions)
- **클래스**: `PascalCase` (예: `SerialManager`, `MainWindow`)
- **함수/메서드**: `snake_case` (예: `connect_port`, `update_ui`)
- **변수**: `snake_case` (예: `port_name`, `is_connected`)
- **상수**: `UPPER_CASE` (예: `DEFAULT_BAUDRATE`, `MAX_RETRIES`)
- **비공개 멤버**: 밑줄 `_` 접두사 사용 (예: `_internal_helper`, `_buffer`)

## 6. Git 관리 가이드 (Git Management Guide)

### 6.1 지속적인 백업 (Continuous Backup)
> [!IMPORTANT]
> **Git을 통한 지속적인 백업은 필수입니다.**
> - 작업 중 최소 **하루 1회 이상** 커밋하여 변경사항을 기록합니다.
> - 중요한 기능 구현 후에는 **즉시 커밋**하여 작업 내용을 보존합니다.
> - 정기적으로 원격 저장소(GitHub 등)에 **push**하여 백업하세요.

### 6.2 브랜치 전략 (Branch Strategy)
- **main**: 배포 가능한 안정 버전.
- **develop**: 개발 중인 최신 버전 (선택 사항).
- **feature/기능명**: 새로운 기능 개발 (예: `feature/dual-font-system`).
- **fix/버그명**: 버그 수정 (예: `fix/connection-error`).
- **refactor/대상**: 리팩토링 (예: `refactor/theme-manager`).

### 6.3 커밋 메시지 (Commit Messages)
- **언어**: 반드시 **한국어**로 작성합니다.
- **형식**: `태그: 설명` 형식을 권장합니다.
- **태그 목록**:
    - `Feat`: 새로운 기능 추가
    - `Fix`: 버그 수정
    - `Docs`: 문서 수정
    - `Style`: 코드 포맷팅, 세미콜론 누락 등 (코드 변경 없음)
    - `Refactor`: 코드 리팩토링
    - `Test`: 테스트 코드 추가/수정
    - `Chore`: 빌드 업무 수정, 패키지 매니저 수정 등

### 6.4 권장 워크플로우
```bash
# 1. 새 기능 시작 시 브랜치 생성
git checkout -b feature/새기능명

# 2. 작업 중 자주 커밋 (하루 1회 이상)
git add .
git commit -m "Feat: 기능 설명"

# 3. 원격 저장소에 백업
git push origin feature/새기능명

# 4. 기능 완료 시 main으로 병합
git checkout main
git merge feature/새기능명
git push origin main
```

### 예시
```
Feat: 듀얼 폰트 시스템 구현
Fix: 포트 연결 실패 시 크래시 수정
Docs: README.md 사용법 업데이트
```

## 7. 프로젝트 구조 (Project Structure)
- **Core**: 핵심 로직 및 유틸리티 (`core/`).
- **Model**: 데이터 모델 및 비즈니스 로직 (`model/`).
- **View**: UI 컴포넌트 및 위젯 (`view/`).
- **Presenter**: View와 Model을 연결하는 로직 (`presenter/`).
- **Resources**: 테마 및 아이콘과 같은 정적 자산 (`resources/`).
- **Config**: 구성 파일 (`config/`).
