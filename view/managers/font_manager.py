"""
폰트 관리자 모듈

애플리케이션의 가변폭(Proportional)/고정폭(Fixed) 폰트 설정을 관리합니다.

## WHY
* `ThemeManager`(833줄, S-050 조사)가 싱글톤 수명·아이콘·테마 파일 탐색·QSS 조립·
  폰트를 한 클래스에 담고 있어, 폰트 하나를 테스트하려 해도 QApplication·아이콘·
  QSS 로직이 전부 딸려왔다. 폰트 서브시스템은 나머지 관심사에 의존하지 않는
  가장 깨끗한 분리 후보였다 (S-053).
* 폰트를 바꾸면 테마(QSS)를 재적용해야 화면에 반영되지만, `FontManager`가
  `ThemeManager`를 직접 참조(역참조)하면 S-050에서 없앤 순환 참조가 되살아난다.
  그래서 재적용은 **콜백**으로만 통지한다 — `FontManager`는 `ThemeManager`의 존재를
  모른다.

## WHAT
* 가변폭/고정폭 폰트의 get/set, DTO 왕복(`get_font_settings`/
  `restore_fonts_from_settings`), QSS 폰트 규칙 생성(`_generate_font_stylesheet`),
  플랫폼별 기본 폰트 테이블.

## HOW
* 생성자에서 인자 없는 콜백(`on_font_applied`)을 주입받는다. `apply_now=True`로
  폰트를 바꾸면 QApplication 기본 폰트를 갱신한 뒤 이 콜백을 호출해 테마 재적용을
  호출자(ThemeManager)에게 위임한다.
"""
import platform
from typing import Any, Callable, Dict, Optional, Tuple

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from common.constants import (
    PLATFORM_WINDOWS, PLATFORM_LINUX, PLATFORM_MACOS,
    FONT_FAMILY_SEGOE, FONT_FAMILY_UBUNTU, FONT_FAMILY_CONSOLAS,
    FONT_FAMILY_MONOSPACE, FONT_FAMILY_MENLO, ConfigKeys
)
from common.dtos import FontConfig


class FontManager:
    """
    가변폭/고정폭 폰트 설정을 관리하는 클래스 (ThemeManager로부터 분리, S-053).

    ThemeManager와 달리 싱글톤이 아니다 — 소유자(ThemeManager)가 인스턴스를 하나
    만들어 들고 있는 구성 요소다.
    """

    # 플랫폼별 기본 폰트 설정
    _PROPORTIONAL_FONTS = {
        PLATFORM_WINDOWS: (FONT_FAMILY_SEGOE, 9),
        PLATFORM_LINUX: (FONT_FAMILY_UBUNTU, 9),
        PLATFORM_MACOS: ("SF Pro Text", 9)
    }

    _FIXED_FONTS = {
        PLATFORM_WINDOWS: (FONT_FAMILY_CONSOLAS, 9),
        PLATFORM_LINUX: (FONT_FAMILY_MONOSPACE, 9),
        PLATFORM_MACOS: (FONT_FAMILY_MENLO, 9)
    }

    def __init__(self, on_font_applied: Optional[Callable[[], None]] = None) -> None:
        """
        FontManager 초기화.

        Args:
            on_font_applied: `apply_now=True`로 폰트가 바뀌었을 때 호출되는 콜백
                (인자 없음). 테마(QSS) 재적용을 트리거하기 위한 것으로, 소유자가
                자기 자신을 역참조 없이 주입한다.
        """
        self._on_font_applied = on_font_applied

        # 플랫폼 확인 및 기본 폰트 설정
        system = platform.system()

        # 1. 가변폭 폰트 (Proportional)
        prop_family, prop_size = self._PROPORTIONAL_FONTS.get(system, ("Arial", 9))
        self._proportional_font = QFont(prop_family, prop_size)

        # 2. 고정폭 폰트 (Fixed)
        fixed_family, fixed_size = self._FIXED_FONTS.get(system, ("Courier New", 9))
        self._fixed_font = QFont(fixed_family, fixed_size)
        self._fixed_font.setStyleHint(QFont.Monospace)

    def set_proportional_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """
        UI 전반에 사용될 가변폭 폰트(Proportional Font)를 설정합니다.

        Logic:
            - 내부 변수 업데이트
            - Qt Application 기본 폰트 설정
            - apply_now=True일 경우 `on_font_applied` 콜백으로 재적용 요청

        Args:
            family (str): 폰트 패밀리명.
            size (int): 폰트 크기.
            apply_now (bool): 즉시 갱신 여부.
        """
        self._proportional_font = QFont(family, size)

        # Qt 애플리케이션 기본 폰트 설정
        app = QApplication.instance()
        if app:
            app.setFont(self._proportional_font)
            # 스타일시트에도 반영하기 위해 테마 재적용을 콜백으로 요청
            if apply_now and self._on_font_applied:
                self._on_font_applied()

    def get_proportional_font(self) -> QFont:
        """
        현재 설정된 가변폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._proportional_font)

    def get_proportional_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 가변폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._proportional_font.family(), self._proportional_font.pointSize()

    def set_fixed_font(self, family: str, size: int, apply_now: bool = True) -> None:
        """
        로그 및 데이터 뷰에 사용될 고정폭 폰트(Fixed Font)를 설정합니다.

        Args:
            family (str): 폰트 패밀리명.
            size (int): 폰트 크기.
            apply_now (bool): 즉시 갱신 여부.
        """
        self._fixed_font = QFont(family, size)
        self._fixed_font.setStyleHint(QFont.Monospace)
        if apply_now and self._on_font_applied:
            self._on_font_applied()

    def get_fixed_font(self) -> QFont:
        """
        현재 설정된 고정폭 폰트 객체를 반환합니다.

        Returns:
            QFont: 설정된 폰트.
        """
        return QFont(self._fixed_font)

    def get_fixed_font_info(self) -> Tuple[str, int]:
        """
        현재 설정된 고정폭 폰트 정보(이름, 크기)를 반환합니다. (데이터 저장용)

        Returns:
            Tuple[str, int]: (폰트패밀리, 크기)
        """
        return self._fixed_font.family(), self._fixed_font.pointSize()

    def get_font_settings(self) -> FontConfig:
        """
        현재 폰트 설정 전체를 DTO로 반환합니다.

        Returns:
            FontConfig: 폰트 설정 DTO.
        """
        prop_fam, prop_size = self.get_proportional_font_info()
        fixed_fam, fixed_size = self.get_fixed_font_info()
        return FontConfig(
            prop_family=prop_fam,
            prop_size=prop_size,
            fixed_family=fixed_fam,
            fixed_size=fixed_size
        )

    def restore_fonts_from_settings(self, settings: Dict[str, Any]) -> None:
        """
        설정 딕셔너리로부터 폰트 설정을 복원합니다.
        (앱 초기화 시 SettingsManager로부터 데이터를 주입받을 때 사용)

        Logic:
            - 설정 딕셔너리에서 ui 섹션 조회
            - 저장된 폰트 정보가 있으면 내부 상태 업데이트
            - 적용(Apply)은 수행하지 않음 (LifecycleManager에서 일괄 처리)

        Args:
            settings (Dict[str, Any]): 설정 데이터 딕셔너리.
        """
        ui_settings = settings.get("ui", {})

        # 가변폭 폰트 복원
        prop_family = ui_settings.get(ConfigKeys.PROP_FONT_FAMILY)
        prop_size = ui_settings.get(ConfigKeys.PROP_FONT_SIZE)
        if prop_family and prop_size:
            self._proportional_font = QFont(prop_family, prop_size)

        # 고정폭 폰트 복원
        fixed_family = ui_settings.get(ConfigKeys.FIXED_FONT_FAMILY)
        fixed_size = ui_settings.get(ConfigKeys.FIXED_FONT_SIZE)
        if fixed_family and fixed_size:
            self._fixed_font = QFont(fixed_family, fixed_size)
            self._fixed_font.setStyleHint(QFont.Monospace)

    def _generate_font_stylesheet(self) -> str:
        """
        현재 폰트 설정을 기반으로 CSS 폰트 규칙을 생성합니다.

        Logic:
            - 가변폭 폰트: 전역 위젯(*)에 적용 (일부 특수 위젯 제외)
            - 고정폭 폰트: 텍스트 에디터, 테이블 뷰, .fixed-font 클래스에 적용

        Returns:
            str: 폰트 관련 QSS 문자열.
        """
        prop_fam = self._proportional_font.family()
        prop_size = self._proportional_font.pointSize()
        fixed_fam = self._fixed_font.family()
        fixed_size = self._fixed_font.pointSize()

        return f"""
        /* Proportional Font (Global) */
        * {{
            font-family: "{prop_fam}", "Malgun Gothic", sans-serif;
            font-size: {prop_size}pt;
        }}

        /* Fixed Font (Log/Data Views) */
        .fixed-font, QTextEdit, QPlainTextEdit, QTableView, QSmartTextEdit, QSmartListView {{
            font-family: "{fixed_fam}", "Consolas", monospace;
            font-size: {fixed_size}pt;
        }}

        /* Table Header uses Proportional Font */
        QHeaderView::section {{
            font-family: "{prop_fam}", "Malgun Gothic", sans-serif;
            font-size: {prop_size}pt;
        }}
        """
