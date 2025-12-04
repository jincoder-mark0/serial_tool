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
- **언어**: 모든 Docstring은 **한국어**로 작성합니다.
- **간결함**: 첫 줄은 마침표 없이 간단명료하게 작성합니다.
- **타입**: 타입 힌트는 함수 시그니처에 명시하므로 docstring에서는 생략 가능합니다.

### 기본 형식
- **요약**: 함수/클래스가 수행하는 작업에 대한 간략한 설명
- **Logic**: 핵심 알고리즘 또는 패턴
- **Args**: 각 매개변수에 대한 설명
- **Returns**: 반환값 설명 (복잡한 구조는 상세히 기술)
- **Raises**: (선택 사항) 발생 가능한 예외



### 예시 1: 모듈 Docstring
- Import 이전에 작성합니다.

**핵심 원칙:**
1. **WHY를 먼저**: 이 코드가 왜 존재하는지 명확히 설명
2. **WHAT은 구체적으로**: 제공하는 기능을 명확하게 나열
3. **HOW는 간결하게**: 핵심 알고리즘이나 패턴만 언급 (세부사항은 코드 참조)
4. **최소 3줄 이상**: 각 섹션은 최소 1개 이상의 bullet point

```python
"""
모듈의 주요 역할을 한 줄로 요약.

WHY (왜 필요한가):
    - 이 모듈이 해결하는 문제나 필요성
    - 비즈니스 또는 기술적 요구사항
    - 없으면 어떤 문제가 발생하는지

WHAT (무엇을 하는가):
    - 주요 기능 나열
    - 제공하는 클래스/함수/인터페이스
    - 관리하는 데이터 구조

HOW (어떻게 동작하는가):
    - 핵심 알고리즘 또는 패턴
    - 의존성 (다른 모듈과의 통신 방법)
    - 중요한 구현 세부사항
"""
import ...
```

### 예시 2: 간단한 함수
```python
def method_name(self, param1, param2):
    """
    메서드의 주요 기능을 한 줄로 요약.

    더 상세한 설명이 필요한 경우 여기에 작성합니다.
    여러 줄로 작성할 수 있으며, 메서드의 주요 기능과
    사용 목적을 명확히 설명합니다.

    Logic:
        - 로직설명

    Args:
        param1 (type): 파라미터 설명
        param2 (type): 파라미터 설명
            - 세부 항목이 있는 경우 들여쓰기로 표현
            - 추가 세부 정보

    Returns:
        type: 반환값 설명

    Raises:
        ExceptionType: 예외가 발생하는 조건 (필요시)

    Note:
        추가 참고사항 (필요시)
    """
```

### 예시 3: 복잡한 반환값
```python
def execute_rename(self) -> Dict[str, Any]:
    """리네임 실행

    Returns:
        Dict[str, Any]: 실행 결과
        {
            'success': int,     # 성공한 파일 수
            'failed': int,      # 실패한 파일 수
            'errors': List[str] # 오류 메시지 목록
        }
    """
```

### 예시 4: 클래스
```python
class SerialWorker(QThread):
    """시리얼 포트 통신을 처리하는 워커 스레드

    이 클래스는 별도 스레드에서 시리얼 포트 읽기/쓰기를 수행하여
    메인 UI 스레드의 블로킹을 방지합니다.

    Attributes:
        port_name: 연결할 시리얼 포트 이름
        baudrate: 통신 속도
    """
```

### 예시 5: 매개변수가 없는 함수
```python
def generate_rename_plan(self) -> List[Tuple[str, str]]:
    """현재 설정에 따른 리네임 계획 생성

    Returns:
        List[Tuple[str, str]]: (원본 경로, 새 경로) 튜플의 리스트
    """
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

- **클래스**: `PascalCase` (예: `SerialManager`, `MainWindow`)
- **함수/메서드**: `snake_case` (예: `connect_port`, `update_ui`)
- **변수**: `snake_case` (예: `port_name`, `is_connected`)
- **상수**: `UPPER_CASE` (예: `DEFAULT_BAUDRATE`, `MAX_RETRIES`)
- **비공개 멤버**: 밑줄 `_` 접두사 사용 (예: `_internal_helper`, `_buffer`)

### 5.1 언어 키 네이밍 규칙 (Language Key Naming Convention)

다국어 지원을 위한 언어 키는 다음 형식을 엄격히 준수해야 합니다:

**형식**: `[context]_[type]_[name]`

- **context**: 위젯/컴포넌트 이름 (예: `port`, `cmd_list`, `manual_ctrl`)
- **type**: UI 요소 타입
  - `btn`: 버튼 (Button)
  - `lbl`: 라벨 (Label)
  - `chk`: 체크박스 (Checkbox)
  - `combo`: 콤보박스 (ComboBox)
  - `input`: 입력 필드 (Input Field)
  - `grp`: 그룹박스 (GroupBox)
  - `col`: 테이블 컬럼 (Table Column)
  - `tab`: 탭 (Tab)
  - `dialog`: 다이얼로그 (Dialog)
  - `txt`: 텍스트 영역 (TextEdit/TextArea)
  - `tooltip`: 툴팁 (Tooltip) - 다른 요소의 툴팁인 경우 해당 요소 타입 뒤에 추가
- **name**: 구체적인 기능/용도 설명

#### 예시
```python
# 올바른 예시
"port_btn_connect"              # 포트 연결 버튼
"port_combo_baud_tooltip"       # 보드레이트 콤보박스의 툴팁
"cmd_list_col_command"          # 명령 리스트의 명령 컬럼
"manual_ctrl_grp_control"       # 수동 제어의 제어 그룹박스
"recv_txt_log_placeholder"      # 수신 영역의 로그 텍스트 플레이스홀더
"about_lbl_app_name"            # About 다이얼로그의 앱 이름 라벨
"font_grp_fixed_tooltip"        # 폰트 설정의 고정폭 그룹박스 툴팁

# 잘못된 예시
"port_baud_combo_tooltip"       # ❌ type이 name 뒤에 위치
"port_settings"                 # ❌ type 누락 (port_grp_settings가 올바름)
"inspector_field"               # ❌ type 누락 (inspector_col_field가 올바름)
"cmd_list_dialog_open_title"    # ❌ 순서 오류 (cmd_list_dialog_title_open이 올바름)
```

#### 특수 케이스
- **다이얼로그 타이틀**: `[context]_dialog_title_[name]`
  - 예: `cmd_list_dialog_title_save`, `pref_dialog_title_select_dir`
- **상태 메시지**: `[context]_status_[name]`
  - 예: `file_prog_status_completed`, `file_prog_status_sending`
- **필터 문자열**: `[context]_dialog_file_filter_[name]`
  - 예: `manual_ctrl_dialog_file_filter_txt`, `manual_ctrl_dialog_file_filter_all`


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
