"""
색상 처리 서비스 모듈

텍스트에 대한 색상 규칙 적용, 정규식 매칭, 테마별 색상 보정 로직을 처리합니다.
UI(View)나 상태(Manager)와 독립적으로 순수 로직만을 수행합니다.

## WHY
* ColorManager에서 로직을 분리하여 '상태 관리'와 '로직 수행'의 책임 분리 (SoC)
* 반복적인 정규식 컴파일로 인한 성능 저하 방지 (Caching)
* 테마(Dark/Light) 변경 시 가독성을 위해 색상 명도(Lightness) 자동 보정 필요

## WHAT
* 텍스트에 색상 규칙 적용 (HTML span 태그 생성)
* 정규식(Regex) 및 단순 문자열 매칭
* 정규식 객체 캐싱 관리
* HLS 색상 모델을 이용한 명도 자동 보정 알고리즘
* 기본 구문 강조 규칙 정의 및 DTO 변환 (get_syntax_rules)

## HOW
* 상태를 가지지 않는(Stateless) 클래스와 정적 메서드(@staticmethod)로 구현
* 클래스 레벨 딕셔너리(_regex_cache)를 사용하여 컴파일된 정규식 재사용
* colorsys 모듈을 사용하여 RGB <-> HLS 변환 수행
"""
import re
import colorsys
from typing import List, Dict, Pattern, Optional

from common.dtos import ColorRule
from core.logger import logger


class ColorService:
    """
    색상 적용, 패턴 매칭, 색상 보정을 담당하는 정적 서비스 클래스
    """

    # 정규식 컴파일 캐시 (패턴 문자열 -> 컴파일된 객체)
    _regex_cache: Dict[str, Pattern] = {}

    # -------------------------------------------------------------------------
    # 기본 규칙 데이터 (Default Rules Data)
    # -------------------------------------------------------------------------
    # (Pattern, Name/ColorKey, Regex Enabled, Bold)
    # 참고: Bold 정보는 현재 ColorRule DTO에 없으므로 객체 생성 시 무시되거나 추후 확장을 위해 남겨둠
    _DEFAULT_RULES_DATA = [
        (r"^\d{2}:\d{2}:\d{2}\.\d{3}", "timestamp", True, False),
        (r"\[INFO\]", "info", True, True),
        (r"\[WARN\]", "warning", True, True),
        (r"\[ERROR\]", "error", True, True),
        (r"\[CRITICAL\]", "error", True, True),
        (r"\[DEBUG\]", "debug", True, False),
        (r"\[RX\]", "rx", True, True),
        (r"\[TX\]", "tx", True, True),
        (r"\[SYSTEM\]", "system", True, True),
        (r"\b[0-9A-Fa-f]{2}\b", "default", True, False),  # Hex Pairs
    ]

    @staticmethod
    def get_syntax_rules() -> List[ColorRule]:
        """
        기본 구문 강조 규칙 목록을 ColorRule 객체 리스트로 반환합니다.

        Returns:
            List[ColorRule]: 초기화된 규칙 리스트.
        """
        rules = []
        for pattern, name, regex_enabled, _ in ColorService._DEFAULT_RULES_DATA:
            # ColorRule DTO 정의에 맞춰 객체 생성
            # name: 규칙 식별자이자 색상 키로 사용
            # color: 기본 색상 키 (ColorManager가 이를 HEX로 매핑하거나, HEX 코드가 직접 들어갈 수 있음)
            rule = ColorRule(
                name=name,
                pattern=pattern,
                color=name,         # 기본적으로 이름을 색상 키로 사용 (예: "info")
                regex_enabled=regex_enabled,
                enabled=True
                # light_color, dark_color는 기본값("") 사용
            )
            rules.append(rule)
        return rules

    @staticmethod
    def apply_rules(text: str, rules: List[ColorRule], is_dark_theme: bool) -> str:
        """
        텍스트에 색상 규칙 리스트를 순차적으로 적용합니다.

        Logic:
            1. 활성화된(enabled) 규칙만 필터링
            2. 현재 테마(Dark/Light)에 맞는 색상 결정 및 보정
            3. 텍스트 내 패턴 매칭 및 HTML 태그(<span style...>) 치환

        Args:
            text (str): 원본 텍스트.
            rules (List[ColorRule]): 적용할 색상 규칙 리스트 (DTO).
            is_dark_theme (bool): 현재 테마가 어두운 배경인지 여부.

        Returns:
            str: HTML 색상 태그가 적용된 텍스트.
        """
        if not rules:
            return text

        result = text
        for rule in rules:
            # DTO의 enabled 속성 확인
            if hasattr(rule, 'enabled') and rule.enabled:
                target_color = ColorService._resolve_color(rule, is_dark_theme)

                # 유효한 색상이 없으면 규칙 적용 스킵
                if not target_color:
                    continue

                result = ColorService._apply_single_rule(
                    result, rule.pattern, target_color, rule.regex_enabled
                )
        return result

    @classmethod
    def _resolve_color(cls, rule: ColorRule, is_dark_theme: bool) -> Optional[str]:
        """
        규칙과 테마에 맞는 최적의 색상을 결정합니다.

        Logic:
            1. 테마별(Dark/Light) 지정 색상이 DTO에 존재하면 우선 사용
            2. 지정 색상이 없으면, 공통 색상(color) 필드 사용
            3. 공통 색상을 사용하는 경우, 현재 테마 배경과 대비되도록 HLS 보정 수행

        Args:
            rule (ColorRule): 색상 규칙 객체.
            is_dark_theme (bool): 다크 테마 여부.

        Returns:
            Optional[str]: 적용할 최종 HEX 색상 코드 (예: '#FF0000'). 없으면 None.
        """
        target_color = None

        # 1. 테마별 명시적 색상 확인 (DTO 필드 존재 시)
        if is_dark_theme and hasattr(rule, 'dark_color') and rule.dark_color:
            target_color = rule.dark_color
        elif not is_dark_theme and hasattr(rule, 'light_color') and rule.light_color:
            target_color = rule.light_color

        # 2. 폴백: 공통 color 필드 사용
        if not target_color and hasattr(rule, 'color') and rule.color:
            raw_color = rule.color

            # 색상 코드가 HEX 형식이면 테마에 맞춰 명도 보정 시도
            if raw_color.startswith('#'):
                target_color = cls._adjust_color_for_theme(raw_color, is_dark_theme)
            else:
                # 'info', 'error' 같은 키워드라면 보정 없이 반환
                # (View에서 처리하거나 CSS 클래스로 매핑됨)
                target_color = raw_color

        return target_color

    @staticmethod
    def _adjust_color_for_theme(hex_color: str, is_dark_theme: bool) -> str:
        """
        HLS 색상 모델을 사용하여 배경색에 맞춰 명도(Lightness)를 자동 조절합니다.

        Logic:
            - HEX -> RGB -> HLS 변환
            - 다크 테마(어두운 배경) -> 명도를 높임 (글자를 밝게)
            - 라이트 테마(밝은 배경) -> 명도를 낮춤 (글자를 어둡게)
            - HLS -> RGB -> HEX 변환

        Args:
            hex_color (str): 원본 색상 코드 (#RRGGBB).
            is_dark_theme (bool): 다크 테마 여부.

        Returns:
            str: 보정된 HEX 색상 코드.
        """
        # 유효하지 않은 HEX 코드는 원본 반환
        if not hex_color or not hex_color.startswith('#') or len(hex_color) != 7:
            return hex_color

        try:
            # HEX -> RGB (0.0 ~ 1.0)
            r = int(hex_color[1:3], 16) / 255.0
            g = int(hex_color[3:5], 16) / 255.0
            b = int(hex_color[5:7], 16) / 255.0

            # RGB -> HLS
            h, l, s = colorsys.rgb_to_hls(r, g, b)

            # 명도(Lightness) 조정 로직
            if is_dark_theme:
                # 어두운 배경: 글자는 밝아야 함 (최소 0.6 이상 보장)
                if l < 0.5:
                    l = 0.6 + (0.4 * l)  # 어두운 색을 밝게 보정
            else:
                # 밝은 배경: 글자는 어두워야 함 (최대 0.4 이하 보장)
                if l > 0.5:
                    l = 0.4 * l  # 밝은 색을 어둡게 보정

            # HLS -> RGB
            r, g, b = colorsys.hls_to_rgb(h, l, s)

            # 0~255 정수 변환 및 클램핑(Clamping)
            r = max(0, min(255, int(r * 255)))
            g = max(0, min(255, int(g * 255)))
            b = max(0, min(255, int(b * 255)))

            return '#{:02x}{:02x}{:02x}'.format(r, g, b)

        except ValueError:
            # 변환 실패 시 원본 색상 반환 (안전장치)
            logger.warning(f"Invalid hex color format: {hex_color}")
            return hex_color

    @classmethod
    def _apply_single_rule(cls, text: str, pattern: str, color: str, regex_enabled: bool) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.

        Logic:
            - Regex 규칙: 캐시된 정규식 객체를 사용하여 매칭된 부분을 HTML 태그로 감쌈
            - 일반 규칙: str.replace를 사용하여 단순 치환

        Args:
            text (str): 대상 텍스트.
            pattern (str): 매칭 패턴 (정규식 또는 문자열).
            color (str): 적용할 HEX 색상 코드.
            regex_enabled (bool): 정규식 사용 여부.

        Returns:
            str: 태그가 적용된 텍스트.
        """
        if regex_enabled:
            try:
                # 정규식 컴파일 및 캐시 확인
                if pattern not in cls._regex_cache:
                    cls._regex_cache[pattern] = re.compile(pattern)

                pattern_obj = cls._regex_cache[pattern]

                # 그룹 0(\g<0>)을 사용하여 매칭된 전체 문자열을 태그로 감쌈
                return pattern_obj.sub(
                    rf'<span style="color:{color};">\g<0></span>',
                    text
                )
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
                return text
        else:
            # 단순 문자열 치환 (정규식 오버헤드 없음)
            return text.replace(
                pattern,
                f'<span style="color:{color};">{pattern}</span>'
            )

    @classmethod
    def clear_cache(cls) -> None:
        """
        캐시된 정규식 객체들을 메모리에서 제거합니다.
        (설정이 대거 변경되거나 메모리 정리가 필요할 때 사용)
        """
        cls._regex_cache.clear()