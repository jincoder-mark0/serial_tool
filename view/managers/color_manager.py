"""
색상 규칙 관리자 (Color Manager)

애플리케이션 전반의 구문 강조(Syntax Highlighting) 및 색상 규칙을 중앙에서 관리합니다.
규칙 데이터 관리(JSON 영속화·CRUD)는 `ColorRuleRepository`(S-054, Qt 의존 0)에
위임하고, 이 클래스는 Qt 어댑터(서식 생성·테마 팔레트 동기화)만 담당합니다.

## WHY
* 색상 규칙의 영속성(JSON 저장/로드) 관리 및 사용자 설정 유지
* Qt 위젯(View)에 필요한 서식 객체(QTextCharFormat) 제공
* 로직(Service)과 뷰(Widget) 사이의 데이터 브리지 역할 (SSOT)

## WHAT
* 규칙 리스트 관리(추가/삭제/토글) 및 파일 입출력 — `ColorRuleRepository`에 위임.
* ColorRule DTO를 Qt TextFormat으로 변환하여 반환 (Qt 접촉면, 이 클래스의 책임).
* 텍스트 기반의 HTML 태그 생성 위임 (ColorService)
* 테마(Dark/Light) 변경에 따른 내부 색상 팔레트 및 규칙 색상 동기화

## HOW
* composition root가 한 번 생성해 주입한다 (class singleton / module 전역 없음)
* 규칙 데이터(`_rules`)는 내부 `ColorRuleRepository` 인스턴스가 소유하며, 이 클래스는
  `_rules` 프로퍼티로 위임해 기존 공개 계약(속성 직접 접근·CRUD 메서드 시그니처)을
  그대로 유지한다(S-054, `tests/test_theme_color_managers.py` 무수정 통과가 계약).
* 현재 테마가 dark 계열인지는 ThemeManager를 직접 참조하지 않고 공유 리프 모듈
  `theme_state`를 통해 조회 (ThemeManager<->ColorManager 순환 참조 해소, S-050)
"""
from typing import List, Optional, Tuple
from pathlib import Path

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor, QTextCharFormat, QBrush, QFont

from core.resource_path import ResourcePath
from common.dtos import ColorRule
from view.services.color_service import ColorService
from view.managers import theme_state
from view.managers.color_rule_repository import ColorRuleRepository
from view.managers.theme_resource_loader import ThemeResourceLoader


class ColorManager(QObject):
    """
    색상 규칙 관리자 클래스.
    설정 파일 관리·규칙 CRUD는 `ColorRuleRepository`에 위임하고, Qt 서식 생성 및
    테마 팔레트 동기화를 담당합니다.

    WHY instance:
        과거에는 `__new__` 기반 class singleton + module-level 전역 인스턴스였다.
        그 조합이 두 가지 결함을 만들었다.

        1. `main.py`가 넘긴 ResourcePath가 **적용되지 않았다.** import 시점에 이미
           초기화가 끝나 있어 `_initialized` 가드가 early-return했고, `_resource_path`만
           갈아끼운 채 `config_path`는 재계산하지 않았다. 색 규칙은 언제나 import
           시점의 기본 경로에서 로드됐다.
        2. **import만으로 파일 I/O가 일어났다.** 모듈을 읽는 것만으로
           `color_rules.json`을 읽었고, PyInstaller 분석 단계에서도 그 로그가 찍혔다.

        지금은 composition root가 한 번 생성해 주입한다 (P2-C #6의 SettingsManager와
        같은 결정).
    """

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """
        ColorManager 초기화

        Logic:
            - ResourcePath 설정 및 설정 파일 경로 계산
            - 기본 테마 색상 팔레트 초기화
            - 설정 파일 로드 (없으면 기본값 생성)

        Args:
            resource_path (Optional[ResourcePath]): 리소스 경로 관리 객체.
                None이면 기본 ResourcePath를 만든다 (SettingsManager와 동일한 관례).
        """
        super().__init__()

        # ResourcePath 설정 (없으면 생성)
        if resource_path is None:
            resource_path = ResourcePath()
        self._resource_path = resource_path

        # 규칙 데이터·영속화 담당 저장소 (Qt 의존 0, S-054)
        self._repo = ColorRuleRepository()

        # 내부 색상 팔레트 변수 초기화 (기본값: Dark Theme)
        self.apply_theme('dark')

        # 설정 파일 경로 결정 (ResourcePath 활용)
        self.config_path = self._resource_path.config_dir / 'color_rules.json'

        # 초기 규칙 로드
        if self.config_path.exists():
            self.load_rules(str(self.config_path))
        else:
            # 기본 규칙을 복사해서 사용할 때도 sanitize 과정을 거침
            self._repo.init_default_rules()

            # 디렉토리가 없으면 생성 (ResourcePath가 보통 보장하지만 안전장치)
            if not self.config_path.parent.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_rules(str(self.config_path))

        # [중요] 규칙 로드 후 현재 테마에 맞춰 색상 동기화 실행
        self.apply_theme('dark')

    # -------------------------------------------------------------------------
    # Rule Data Access (ColorRuleRepository 위임)
    # -------------------------------------------------------------------------
    @property
    def _rules(self) -> List[ColorRule]:
        """
        규칙 리스트 접근자. 실제 데이터는 `ColorRuleRepository`가 소유하며, 이 프로퍼티는
        기존 코드/테스트의 `color_manager._rules` 직접 접근 계약을 그대로 유지하기 위한
        위임 통로다 (S-054). 리스트 재할당(`color_manager._rules = [...]`)도 setter를
        통해 repository에 반영된다.

        Returns:
            List[ColorRule]: 현재 규칙 리스트 (repository가 소유한 실제 객체).
        """
        return self._repo._rules

    @_rules.setter
    def _rules(self, value: List[ColorRule]) -> None:
        self._repo._rules = value

    def _ensure_hex(self, color_code: str) -> str:
        """
        색상 코드가 HEX 형식이면 '#'을 보장합니다. (ColorRuleRepository 위임)

        Args:
            color_code (str): 입력 색상 코드 (예: 'FF0000', '#FF0000', 'red')

        Returns:
            str: '#'이 포함된 색상 코드
        """
        return self._repo._ensure_hex(color_code)

    # -------------------------------------------------------------------------
    # Qt Specific Methods (View Support)
    # -------------------------------------------------------------------------
    def _create_format(self, color_input: str, bold: bool = False) -> QTextCharFormat:
        """
        HEX 색상 코드 또는 색상 키를 사용하여 QTextCharFormat 객체를 생성합니다.

        Logic:
            - 입력값이 키(예: 'info')인지 HEX('#FF0000')인지 확인
            - 키라면 내부 팔레트 매핑(self.COLOR_...)을 사용해 HEX로 변환
            - QBrush, QFont 설정

        Args:
            color_input (str): HEX 색상 코드 또는 키.
            bold (bool): 굵게 표시 여부.

        Returns:
            QTextCharFormat: 생성된 서식 객체.
        """
        # 색상 키 매핑
        color_map = {
            "timestamp": self.COLOR_TIMESTAMP,
            "info": self.COLOR_INFO,
            "warning": self.COLOR_WARNING,
            "error": self.COLOR_ERROR,
            "rx": self.COLOR_RX,
            "tx": self.COLOR_TX,
            "system": self.COLOR_SYSTEM,
            "debug": self.COLOR_DEBUG,
            "default": self.COLOR_DEFAULT
        }

        # 1. 키로 조회 시도, 없으면 입력값(HEX) 그대로 사용
        hex_code = color_map.get(color_input.lower(), color_input)

        # 2. 안전장치: HEX 보정
        hex_code = self._ensure_hex(hex_code)

        # 3. Format 생성
        fmt = QTextCharFormat()
        if QColor.isValidColor(hex_code):
            fmt.setForeground(QBrush(QColor(hex_code)))
        else:
            fmt.setForeground(QBrush(QColor(self.COLOR_DEFAULT)))

        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _init_rules(self) -> None:
        """규칙 초기화 메서드"""
        pass

    @property
    def rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """
        Qt View(SyntaxHighlighter)에서 사용하기 위한 (패턴, 포맷) 튜플 리스트를 반환합니다.

        Returns:
            List[Tuple[str, QTextCharFormat]]: Qt 호환 규칙 리스트.
        """
        qt_rules = []
        for rule in self._rules:
            if not rule.enabled:
                continue

            # 색상 결정 (이미 apply_theme에서 동기화됨)
            final_color = rule.color

            is_bold = getattr(rule, 'bold', False)
            fmt = self._create_format(final_color, bold=is_bold)

            qt_rules.append((rule.pattern, fmt))

        return qt_rules

    def get_color_for_key(self, key: str) -> QColor:
        """
        규칙 이름(Key)에 해당하는 현재 테마의 QColor를 반환합니다.

        Args:
            key (str): 규칙 이름 (예: 'TIMESTAMP', 'INFO').

        Returns:
            QColor: 색상 객체.
        """
        hex_color = self.get_rule_color(key)

        # HEX 보정
        hex_color = self._ensure_hex(hex_color)

        if QColor.isValidColor(hex_color):
            return QColor(hex_color)

        # 잘못된 색이 들어왔을 때의 폴백. 검은색을 박아 두면 어두운 테마에서
        # 글씨가 배경에 묻혀 아예 보이지 않는다 (S-078). 현재 테마의 기본
        # 텍스트 색을 쓰면 어느 테마에서도 읽힌다.
        return QColor(self.COLOR_DEFAULT)

    def apply_theme(self, theme_name: str) -> None:
        """
        테마 변경 시 내부 색상 팔레트 변수를 업데이트하고,
        모든 규칙(self._rules)의 .color 필드를 현재 테마에 맞게 갱신합니다.

        Args:
            theme_name (str): 테마 이름 ('dark' or 'light').
        """
        # 색과 밝기 분류는 **테마 리소스**(resources/themes/palette.json)가 답한다
        # (S-078). 예전에는 여기서 `theme_name == 'light'`로 판정하고 색을 코드에
        # 박아 뒀는데, 그 탓에 밝은 테마인 classic이 다크용 색을 받아 흰 배경에서
        # 11개 중 10개가 WCAG 4.5:1 미달이었다(기본 텍스트는 1.61).
        loader = ThemeResourceLoader(self._resource_path)
        is_light = loader.is_light_theme(theme_name)
        palette = loader.get_log_colors(theme_name)

        # 1. 팔레트 반영 (HEX 코드 보장)
        self.COLOR_TIMESTAMP = self._ensure_hex(palette["timestamp"])
        self.COLOR_INFO = self._ensure_hex(palette["info"])
        self.COLOR_WARNING = self._ensure_hex(palette["warn"])
        self.COLOR_ERROR = self._ensure_hex(palette["error"])
        self.COLOR_RX = self._ensure_hex(palette["rx"])
        self.COLOR_TX = self._ensure_hex(palette["tx"])
        self.COLOR_SYSTEM = self._ensure_hex(palette["system"])
        self.COLOR_DEBUG = self._ensure_hex(palette["debug"])
        self.COLOR_DEFAULT = self._ensure_hex(palette["default"])

        # 2. 규칙 리스트 색상 동기화
        for rule in self._rules:
            active_color = rule.light_color if is_light else rule.dark_color

            if not active_color:
                active_color = rule.color

            # 여기서 한번 더 HEX 보정하여 객체 상태를 완벽하게 유지
            rule.color = self._ensure_hex(active_color)

    # -------------------------------------------------------------------------
    # Logic & Management Methods (ColorRuleRepository 위임)
    # -------------------------------------------------------------------------
    def get_rule_color(self, rule_name: str) -> str:
        """
        특정 규칙의 현재 테마에 맞는 HEX 색상 코드를 반환합니다. (ColorRuleRepository 위임)

        Args:
            rule_name (str): 규칙 이름.

        Returns:
            str: HEX 색상 코드.
        """
        return self._repo.get_rule_color(rule_name)

    def apply_rules(self, text: str) -> str:
        """
        텍스트에 HTML 태그 기반의 색상 규칙을 적용합니다. (ColorService 위임)

        Args:
            text (str): 원본 텍스트.

        Returns:
            str: HTML 태그가 적용된 텍스트.
        """
        # theme_state는 ThemeManager/ColorManager 어느 쪽도 참조하지 않는 리프 모듈이라
        # 순환 참조 없이 최상단에서 import해 사용한다 (S-050).
        is_dark = theme_state.is_dark_theme()

        # ColorService가 rule.color(또는 light/dark)를 참조할 때 #이 붙은 값을 쓰게 됨
        return ColorService.apply_rules(text, self._rules, is_dark)

    def add_custom_rule(self, name: str, pattern: str, color: str, regex_enabled: bool = True) -> None:
        """
        사용자 정의 색상 규칙을 추가합니다. (ColorRuleRepository 위임)

        Args:
            name (str): 규칙 이름.
            pattern (str): 매칭 패턴.
            color (str): 색상 코드.
            regex_enabled (bool): 정규식 사용 여부.
        """
        self._repo.add_custom_rule(name, pattern, color, regex_enabled)

    def remove_rule(self, name: str) -> None:
        """
        규칙을 삭제합니다. (ColorRuleRepository 위임)

        Args:
            name (str): 삭제할 규칙 이름.
        """
        self._repo.remove_rule(name)

    def toggle_rule(self, name: str) -> None:
        """
        규칙의 활성/비활성 상태를 토글합니다. (ColorRuleRepository 위임)

        Args:
            name (str): 대상 규칙 이름.
        """
        self._repo.toggle_rule(name)

    def save_rules(self, file_path: str) -> None:
        """
        규칙 리스트를 JSON 파일로 저장합니다. (ColorRuleRepository 위임)

        Args:
            file_path (str): 저장할 파일 경로.
        """
        self._repo.save_rules(file_path)

    def load_rules(self, file_path: str) -> None:
        """
        JSON 파일에서 규칙을 로드합니다. (ColorRuleRepository 위임)

        Args:
            file_path (str): 읽을 파일 경로.
        """
        self._repo.load_rules(file_path)

    def _get_config_path(self) -> Path:
        """
        이 인스턴스의 색 규칙 설정 파일 경로를 반환합니다.

        과거에는 class singleton(`ColorManager._instance`)을 뒤져 경로를 찾는
        staticmethod였다. 인스턴스가 주입되는 지금은 자기 상태만 보면 된다.

        Returns:
            Path: 색 규칙 JSON 경로.
        """
        return self.config_path

    @staticmethod
    def _apply_single_rule(text: str, rule: ColorRule) -> str:
        """
        단일 규칙 적용 (Helper). ColorService에 위임합니다.

        Args:
            text (str): 대상 텍스트.
            rule (ColorRule): 적용할 규칙.

        Returns:
            str: 변환된 텍스트.
        """
        return ColorService._apply_single_rule(text, rule.pattern, rule.color, rule.regex_enabled)
