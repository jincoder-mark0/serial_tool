---
trigger: always_on
---

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
- **주석**: 모든 코드 주석은 **한국어**로 **간결한 단답형**으로 작성해야 합니다.
- **Docstring**: 모든 Docstring은 **한국어**로 **간결한 단답형**으로 작성해야 합니다.
- **커밋 메시지**: Git 커밋 메시지는 **한국어**로 **간결한 단답형**으로 작성해야 합니다.
- * 기술 용어나 고유명사는 영어 원문을 병기하거나 그대로 사용할 수 있습니다. (예: `WebSocket`, `Queue`, `Backtesting`)

## 3. 주석 및 Docstrings

**주석 작성에 대한 상세 가이드는 별도 문서를 참조하세요:**

👉 **[주석 가이드 (Comment Guide)](comment_guide.md)**

### 3.1 기본 원칙
- **언어**: 모든 주석 및 Docstring은 **한국어**로 작성
- **형식**: Google Style Docstring 사용
- **타입 힌트**: 함수 시그니처에 타입 힌트 필수

### 3.2 간단한 예시

```python
def get_available_ports() -> List[str]:
    """사용 가능한 시리얼 포트 목록을 반환합니다

    Returns:
        List[str]: 포트 이름 리스트
    """
    # 구현 내용...
```

> [!NOTE]
> 모듈 Docstring의 WHY/WHAT/HOW 구조, 복잡한 함수 작성법, 인라인 주석 규칙 등 상세한 내용은 [주석 가이드](comment_guide.md)를 참조하세요.


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

자세한 명명 규칙은 [**Naming Convention Guide**](../guide/naming_convention.md)를 참조하세요.

### 5.1 기본 규칙 요약
- **클래스**: `PascalCase` (예: `SerialManager`, `MainWindow`)
- **함수/메서드**: `snake_case` (예: `connect_port`, `update_ui`)
- **변수**: `snake_case` (예: `port_name`, `is_connected`)
- **상수**: `UPPER_CASE` (예: `DEFAULT_BAUDRATE`, `MAX_RETRIES`)
- **비공개 멤버**: `_prefix` (예: `_internal_helper`, `_buffer`)
- **언어 키**: `[context]_[type]_[name]` 형식 (예: `port_btn_connect`, `manual_ctrl_chk_hex`)

> [!NOTE]
> 언어 키의 상세 규칙, 특수 케이스, 적용 가이드는 별도 문서를 참조하세요.


## 6. Git 관리 (Git Management)

**Git 사용에 대한 상세 가이드는 별도 문서를 참조하세요:**

👉 **[Git 관리 가이드 (Git Guide)](git_guide.md)**

### 6.1 핵심 요약
- **언어**: 커밋 메시지, PR, 이슈는 **한국어**로 작성
- **커밋 주기**: 최소 **하루 1회 이상** 권장
- **메시지 형식**: `태그: 제목` (예: `Feat: 로그인 기능 구현`)

### 6.2 주요 태그
- `Feat`: 기능 추가
- `Fix`: 버그 수정
- `Docs`: 문서 수정
- `Refactor`: 리팩토링

> [!TIP]
> 커밋 수정(amend), 되돌리기(reset/revert), 임시 저장(stash) 등 유용한 실무 명령어는 [Git 관리 가이드](git_guide.md)의 **실무 Git 레시피** 섹션을 확인하세요.

## 7. 프로젝트 구조 (Project Structure)
- **Core**: 핵심 로직 및 유틸리티 (`core/`).
- **Model**: 데이터 모델 및 비즈니스 로직 (`model/`).
- **View**: UI 컴포넌트 및 위젯 (`view/`).
- **Presenter**: View와 Model을 연결하는 로직 (`presenter/`).
- **Resources**: 테마 및 아이콘과 같은 정적 자산 (`resources/`).
- **Config**: 구성 파일 (`config/`).