"""
테마 공유 상태 모듈 (Shared Theme State)

`ThemeManager`와 `ColorManager`가 서로를 함수-지역 import로 참조하며 순환 참조를
우회하던 문제(S-050)를 없애기 위해, 두 매니저가 실제로 공유해야 하는 **단 하나의
상태**("현재 테마 이름")를 어느 매니저도 아닌 제3의 리프 모듈로 분리한다.

## WHY
* `ThemeManager.apply_theme()`는 `ColorManager.apply_theme()`를 호출해야 하고,
  `ColorManager.apply_rules()`는 현재 테마가 dark 계열인지 알아야 한다. 서로를 직접
  import하면 순환 참조가 생겨 기존 코드는 함수 내부 지연(lazy) import로 우회했다
  (코드 스스로 "[중요] 순환 참조 방지"라고 주석을 남긴 상태).
* 단순히 "현재 테마 문자열"을 이 모듈에 캐시(복제)하는 방식은 위험하다 — 테스트
  픽스처(`tests/conftest.py::reset_ui_manager_state`)가 `theme_manager._current_theme`을
  `apply_theme()`을 거치지 않고 **직접 대입**해서 스냅샷/복원하기 때문에, 캐시가 있으면
  복원 후 캐시와 실제 값이 어긋날 수 있다.
* 그래서 이 모듈은 캐시가 아니라 **유일한 저장소**다 — `ThemeManager._current_theme`은
  이 모듈에 위임하는 property로 바뀌므로(`ThemeManager` 자체는 값을 들고 있지 않음),
  `theme_manager._current_theme = "light"` 같은 기존 대입 코드(테스트 포함)가 그대로
  동작하면서도 두 매니저가 항상 같은 값을 본다 — 동기화가 필요 없어 어긋날 수 없다.

## WHAT
* `get_current_theme() -> str`: 현재 테마 이름 조회.
* `set_current_theme(theme_name: str) -> None`: 현재 테마 이름 갱신.
* `is_dark_theme() -> bool`: 현재 테마가 dark 계열(dark/dracula)인지 조회.

## HOW
* 모듈 전역 변수 하나(`_current_theme`)로 상태를 보관한다.
* Import 방향은 단방향이다: `ThemeManager`/`ColorManager` 모두 이 모듈을 import하지만,
  이 모듈은 어느 쪽도 import하지 않는다 — 그래서 순환이 생기지 않는다.
"""
from common.enums import ThemeType

# 기본값은 ThemeManager의 기존 기본 테마(dark)와 동일하게 유지한다.
_current_theme: str = ThemeType.DARK.value


def get_current_theme() -> str:
    """현재 테마 이름을 반환합니다."""
    return _current_theme


def set_current_theme(theme_name: str) -> None:
    """현재 테마 이름을 갱신합니다 (주로 ThemeManager가 호출)."""
    global _current_theme
    _current_theme = theme_name


def is_dark_theme() -> bool:
    """현재 테마가 dark 계열(dark/dracula)인지 여부를 반환합니다."""
    return _current_theme.lower() in (ThemeType.DARK.value, ThemeType.DRACULA.value)
