---
trigger: always_on
---

# Source Code Comment Guide (소스코드 주석 가이드)

이 문서는 `mkdocs`와 `mkdocstrings` 플러그인을 사용하여 프로젝트 문서를 자동화하기 위한 소스코드 주석 작성 규칙을 정의합니다. `code_style_guide.md`의 내용을 기반으로 하며, 자동화 도구가 인식할 수 있는 구체적인 형식을 제시합니다.

## 1. Docstring 스타일 (Style)

본 프로젝트는 **Google Style Docstring**을 표준으로 채택합니다.

### 1.1 Google Style이란?

Google Style은 Python 코드의 문서화를 위해 Google에서 정의한 표준 형식입니다.

*   **특징**: reStructuredText(Sphinx 기본값)보다 **가독성(Human-readable)**이 뛰어납니다. 기호(`:param:`, `:return:`) 대신 명확한 섹션 헤더(`Args:`, `Returns:`)를 사용합니다.
*   **호환성**: `mkdocstrings` 플러그인을 통해 완벽하게 파싱되어 깔끔한 웹 문서로 변환됩니다.
*   **참고 문서**: [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

### 1.2 기본 규칙

*   모든 Docstring은 삼중 따옴표(`"""`)를 사용합니다.
*   첫 줄은 요약문으로 작성하고, 한 줄 띄운 후 상세 내용을 작성합니다.
*   들여쓰기는 스페이스 4칸을 사용합니다.

## 2. 모듈 Docstring (Module Level)

모듈 파일의 최상단에 위치하며, `code_style_guide.md`에서 정의한 **WHY / WHAT / HOW** 섹션을 포함해야 합니다.

```python
"""
모듈의 역할을 한 줄로 요약합니다.

상세 설명은 여기에 작성합니다. 이 모듈은 ~~ 기능을 제공하며,
~~ 시스템과 상호작용합니다.

Attributes:
    DICT_SET (dict): 전역 설정 변수
    module_level_variable (int): 모듈 레벨 변수 설명

## WHY
*   이 모듈이 필요한 이유 1
*   이 모듈이 필요한 이유 2

## WHAT
*   주요 기능 1
*   주요 기능 2

## HOW
*   구현 방식 및 알고리즘
*   사용된 패턴
"""
```

> **Note**: `mkdocs`에서 `## Header` 문법을 사용하면 문서 페이지 내에서 섹션으로 렌더링됩니다.

## 3. 클래스 Docstring (Class Level)

클래스 정의 바로 아래에 위치합니다.

```python
class ExampleClass:
    """
    클래스의 목적을 한 줄로 요약합니다.

    클래스에 대한 상세 설명을 작성합니다.
    여러 줄에 걸쳐서 작성할 수 있습니다.

    Attributes:
        attr1 (str): 속성 1에 대한 설명
        attr2 (int): 속성 2에 대한 설명
    """
```

## 4. 함수/메서드 Docstring (Function/Method Level)

함수 또는 메서드 정의 바로 아래에 위치합니다. **Args**, **Returns**, **Raises**, **Yields** 등의 섹션을 사용합니다.

```python
def example_function(param1: int, param2: str = "default") -> bool:
    """
    함수의 기능을 한 줄로 요약합니다.

    함수의 동작 방식, 주의사항 등을 상세히 설명합니다.

    Logic:
        - 로직설명
        - 로직설명
        - 로직설명

    Args:
        param1 (int): 첫 번째 파라미터 설명.
        param2 (str, optional): 두 번째 파라미터 설명. 기본값은 "default".

    Returns:
        bool: 성공하면 True, 실패하면 False를 반환합니다.

    Raises:
        ValueError: param1이 음수일 경우 발생합니다.
        TypeError: param2가 문자열이 아닐 경우 발생합니다.

    Examples:
        함수 사용 예시를 작성할 수 있습니다.

        >>> example_function(10, "test")
        True
    """
    return True
```

### 4.1 주요 섹션 설명

* **Logic**: 설명이 필요한 로직 작성
* **Args**: 매개변수 설명. `이름 (타입): 설명` 형식.
* **Returns**: 반환값 설명. `타입: 설명` 형식.
* **Raises**: 발생 가능한 예외 설명. `예외타입: 설명` 형식.
* **Yields**: 제너레이터 함수인 경우 반환값 설명.
* **Examples**: 사용 예시 코드. `>>>` 프롬프트를 사용하면 테스트 가능한 코드로 인식될 수 있습니다.

## 5. 타입 힌트 (Type Hinting)

`mkdocstrings`는 소스코드의 타입 힌트를 자동으로 읽어 문서에 표시합니다. 따라서 Docstring에 타입을 중복해서 적는 것보다, 함수 시그니처에 타입 힌트를 명시하는 것을 권장합니다.

**권장 방식 (타입 힌트 사용):**

```python
def connect(self, host: str, port: int) -> None:
    """
    서버에 연결합니다.

    Args:
        host: 서버 호스트 주소
        port: 서버 포트 번호
    """
```

**비권장 방식 (Docstring에만 타입 명시):**

```python
def connect(self, host, port):
    """
    서버에 연결합니다.

    Args:
        host (str): 서버 호스트 주소
        port (int): 서버 포트 번호
    """
```

## 6. 인라인 및 블록 주석 (Inline & Block Comments)

Docstring이 외부 인터페이스를 설명한다면, 인라인 주석은 **내부 구현 로직**을 설명합니다. 복잡한 로직, 긴 메서드, 수식 등을 다룰 때 다음 규칙을 따릅니다.

### 6.1 긴 메서드 및 복잡한 로직 (Long Methods & Complexity)

메서드가 길어지거나(약 50~100줄 이상) 로직이 복잡한 경우, **블록 주석**을 사용하여 논리적 단위를 구분합니다.

```python
def complex_trading_logic(self):
    # ---------------------------------------------------------
    # 1. 초기 상태 검증 및 데이터 로드
    # ---------------------------------------------------------
    if not self.is_market_open():
        return

    data = self.load_market_data()

    # ---------------------------------------------------------
    # 2. 매수 신호 분석 (RSI + MACD)
    # ---------------------------------------------------------
    # RSI가 30 이하이고 MACD가 골든크로스인 경우 매수 후보로 선정
    if self.check_buy_signal(data):
        target_price = self.calculate_target(data)

        # -----------------------------------------------------
        # 3. 주문 실행 및 리스크 관리
        # -----------------------------------------------------
        if self.check_risk_limit(target_price):
            self.send_order("BUY", target_price)
```

### 6.2 분기문 설명 (Branching)

`if`, `elif`, `else` 등의 분기가 복잡할 경우, 각 조건이 **어떤 비즈니스 시나리오**를 의미하는지 주석으로 명시합니다.

```python
if order_status == "FILLED":
    # 체결 완료: 잔고를 갱신하고 다음 주문을 준비
    self.update_balance()
elif order_status == "PARTIALLY_FILLED":
    # 부분 체결: 미체결 수량을 계산하여 정정 주문 대기
    self.handle_partial_fill()
elif order_status == "REJECTED" and error_code == 9001:
    # 주문 거부 (예수금 부족): 리스크 레벨 상향 조정 후 재시도 중지
    self.stop_strategy("Insufficient Funds")
else:
    # 기타 대기 상태 또는 알 수 없는 오류
    self.log_warning(f"Unknown status: {order_status}")
```

### 6.3 수식 및 상수 (Formulas & Constants)

복잡한 계산식이나 매직 넘버(상수)가 사용될 때는 **수식의 의미, 출처, 상수의 정의**를 반드시 설명합니다.

```python
# 변동성 돌파 전략 목표가 계산
# Formula: 시가 + (전일 고가 - 전일 저가) * K
# K값 0.5는 백테스팅(2023-01 ~ 2023-12) 최적화 결과임
target_price = open_price + (prev_high - prev_low) * 0.5

# 수수료 계산 (키움증권 기준)
# 0.00015: 거래 수수료 (0.015%)
# 0.0020: 증권거래세 (0.20%, 매도 시에만 부과)
fee = amount * 0.00015
tax = amount * 0.0020 if side == "SELL" else 0
```

### 6.4 TODO 및 FIXME

코드 내에서 개선이 필요하거나 잠재적인 문제가 있는 부분은 태그를 사용하여 표시합니다.

* `# TODO`: 향후 구현해야 할 기능이나 개선 사항
* `# FIXME`: 알고 있는 버그나 수정이 시급한 문제
* `# NOTE`: 특별히 주의해야 할 사항이나 배경 지식

```python
# TODO: 향후 머신러닝 모델 연동 시 비동기 호출로 변경 필요
prediction = self.cmd_table_model.predict(data)

# FIXME: 가끔 데이터 수신 지연으로 인해 IndexError 발생 가능성 있음 (예외 처리 보강 필요)
last_price = data[-1]
```

## 7. MkDocs 설정 참고 (Reference)

`mkdocs.yml` 설정 시 다음과 같이 `python` 핸들러를 설정하여 Docstring을 파싱할 수 있습니다.

```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
```

## 8. 체크리스트 (Checklist)

### ✅ 작성 전 확인
- [ ] 모든 주석/Docstring을 한국어로 작성했는가?
- [ ] Google Style 형식을 따르는가?
- [ ] 타입 힌트를 함수 시그니처에 작성했는가?

### ✅ 모듈 Docstring
- [ ] WHY/WHAT/HOW 섹션이 있는가?
- [ ] 각 섹션에 최소 1개 이상의 bullet point가 있는가?

### ✅ 함수/메서드 Docstring
- [ ] 첫 줄 요약이 간결한가?
- [ ] Args/Returns 섹션이 완성되었는가?
- [ ] 복잡한 로직에 Logic 섹션을 추가했는가?

### ✅ 인라인 주석
- [ ] 복잡한 로직에 블록 주석으로 단위를 구분했는가?
- [ ] 분기문의 비즈니스 의미를 설명했는가?
- [ ] 수식/상수에 출처와 의미를 명시했는가?
