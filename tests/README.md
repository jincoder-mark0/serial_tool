# 도구 및 테스트 가이드 (Tools & Testing Guide)

이 문서는 `tools/` 디렉토리에 포함된 유틸리티 스크립트의 사용법과 `pytest`를 이용한 프로젝트 테스트 실행 및 결과 해석 방법을 설명합니다.

## 1. 유틸리티 도구 (Utility Tools)

프로젝트 루트 디렉토리에서 다음 Command들을 실행하십시오.

### 언어 키 관리 (`manage_lang_keys.py`)

소스 코드에서 다국어 키를 스캔하거나 정합성을 검사하는 도구입니다.

- **키 추출 (Extract)**: 소스 코드에서 `LangKeys.KEY_NAME` 패턴을 찾아 `languages/` 폴더의 JSON 파일과 동기화합니다.
  ```bash
  python tools/manage_lang_keys.py extract
  ```

- **키 검사 (Check)**: 소스 코드에 사용된 키가 JSON 파일에 정의되어 있는지, 혹은 미사용 키가 있는지 확인합니다.
  ```bash
  python tools/manage_lang_keys.py check
  ```

---

## 2. 테스트 실행 (Running Tests)

본 프로젝트는 `pytest` 프레임워크를 사용하여 단위 테스트(Unit Test)와 통합 테스트(Integration Test)를 수행합니다.

### 2.1 사전 준비
가상 환경이 활성화되어 있어야 합니다.
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 2.2 기본 실행 방법

- **전체 테스트 실행**:
  ```bash
  pytest
  ```

- **특정 파일 테스트 실행**:
  ```bash
  pytest tests/test_core_refinement.py
  ```

- **특정 테스트 함수만 실행**:
  ```bash
  # 파일명::함수명 형식
  pytest tests/test_core_refinement.py::test_data_logger_lifecycle
  ```

### 2.3 자주 사용하는 Pytest 옵션 (Arguments)

테스트 실행 시 유용한 옵션들입니다. 여러 옵션을 조합하여 사용할 수 있습니다. (예: `pytest -v -s`)

| 옵션 (Short) | 옵션 (Long) | 설명 | 추천 상황 |
| :---: | :--- | :--- | :--- |
| **`-v`** | `--verbose` | **상세 모드**. 각 테스트 파일과 케이스별 성공/실패 여부를 목록으로 보여줍니다. | 어떤 테스트가 실행되고 있는지 확인할 때 |
| **`-s`** | `--capture=no` | **표준 출력 표시**. 코드 내의 `print()` 문이나 로그가 콘솔에 그대로 출력됩니다. (기본적으로는 숨겨짐) | 디버깅을 위해 로그를 확인해야 할 때 |
| **`-k`** | `--keyword` | **키워드 검색**. 특정 문자열이 이름에 포함된 테스트만 실행합니다. | 특정 기능(예: `Macro`) 관련 테스트만 돌릴 때 (`-k "Macro"`) |
| **`-x`** | `--exitfirst` | **첫 실패 시 중단**. 테스트가 하나라도 실패하면 즉시 실행을 멈춥니다. | 에러를 빠르게 잡고 싶을 때 |
| **`-lf`** | `--last-failed` | **실패한 테스트만 재실행**. 직전 실행에서 실패했던 케이스들만 다시 돌립니다. | 수정 후 확인 시 유용 |
| | `--durations=0` | **소요 시간 표시**. 실행 시간이 가장 오래 걸린 테스트 순으로 보여줍니다. (0은 전체 표시) | 테스트 속도 최적화가 필요할 때 |

---

## 3. 테스트 결과 해석 (Interpreting Results)

`pytest` 실행 후 출력되는 결과의 의미는 다음과 같습니다.

### 3.1 진행 상태 표시 (Progress)
테스트 실행 중 각 점(`.`)이나 글자는 하나의 테스트 케이스를 의미합니다.

- **`.` (Dot)**: **성공 (PASSED)**. 테스트가 문제없이 통과됨.
- **`F` (Fail)**: **실패 (FAILED)**. `assert` 문이 실패하거나 예상치 못한 결과 발생.
- **`E` (Error)**: **에러 (ERROR)**. 테스트 코드 자체의 오류나 픽스처(Fixture) 설정 중 예외 발생.
- **`s` (Skip)**: **건너뜀 (SKIPPED)**. `@pytest.mark.skip` 등으로 인해 실행되지 않음.
- **`x` (XFail)**: **예상된 실패 (XFAIL)**. 실패할 것을 알고 있는 테스트 (실패해도 통과로 간주).

### 3.2 결과 요약 예시

```text
tests/test_model.py::test_port_controller_eventbus_bridge PASSED         [ 25%]
tests/test_model.py::test_macro_runner_basic_flow FAILED                 [ 50%]
...
=================================== FAILURES ===================================
_________________________ test_macro_runner_basic_flow _________________________
... (에러 상세 내용 및 Traceback 표시) ...
E       pytestqt.exceptions.TimeoutError: Signal macro_finished() not emitted after 2000 ms

=========================== short test summary info ============================
FAILED tests/test_model.py::test_macro_runner_basic_flow - TimeoutError...
========================= 1 failed, 3 passed in 3.35s ==========================
```

1.  **FAILURES 섹션**: 실패한 테스트의 상세 원인과 코드 위치를 보여줍니다.
2.  **Summary Info**: 실패한 테스트의 목록을 요약해 줍니다.
3.  **마지막 줄**: 전체 성공/실패 개수와 소요 시간을 보여줍니다. **초록색**이면 전체 성공, **빨간색**이면 하나 이상의 실패가 있음을 의미합니다.
