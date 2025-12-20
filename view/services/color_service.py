"""
색상 처리 서비스 모듈

텍스트에 대한 색상 규칙 적용, 정규식 매칭 등의 로직을 처리합니다.

## WHY
* ColorManager에서 로직을 분리하여 '상태 관리'와 '로직 수행'의 책임 분리
* 테스트 용이성 향상 (Stateless)
* 반복적인 정규식 컴파일로 인한 성능 저하 방지 (Caching)
* 테마(Dark/Light)에 따른 최적화된 색상 적용 및 자동 보정(HLS)

## WHAT
* 텍스트에 색상 규칙 적용 (HTML 태그 생성)
* 정규식 및 단순 문자열 매칭
* 정규식 객체 캐싱
* HLS 색상 모델을 이용한 명도 자동 보정

## HOW
* Stateless 클래스 (정적 메서드)로 구현
* 외부에서 규칙 리스트를 주입받아 처리
* 클래스 레벨 딕셔너리를 사용한 정규식 캐싱
* colorsys 모듈을 이용한 색상 변환
"""
import re
import colorsys
from typing import List, Dict, Pattern, Optional
from common.dtos import ColorRule
from core.logger import logger

class ColorService:
    """
    색상 적용 및 패턴 매칭 서비스
    """

    # 정규식 컴파일 캐시 (패턴 문자열 -> 컴파일된 객체)
    _regex_cache: Dict[str, Pattern] = {}

    @staticmethod
    def apply_rules(text: str, rules: List[ColorRule], is_dark_theme: bool) -> str:
        """
        텍스트에 색상 규칙 리스트를 순차적으로 적용합니다.

        Args:
            text (str): 원본 텍스트
            rules (List[ColorRule]): 적용할 색상 규칙 리스트
            is_dark_theme (bool): 현재 테마가 어두운 배경인지 여부

        Returns:
            str: HTML 색상 태그가 적용된 텍스트
        """
        result = text
        for rule in rules:
            if rule.enabled:
                target_color = ColorService._resolve_color(rule, is_dark_theme)

                # 색상이 없으면 규칙 적용 스킵
                if not target_color:
                    continue

                result = ColorService._apply_single_rule(result, rule.pattern, target_color, rule.regex_enabled)
        return result

    @classmethod
    def _resolve_color(cls, rule: ColorRule, is_dark_theme: bool) -> Optional[str]:
        """
        테마에 맞는 색상을 결정하고 필요시 자동 보정합니다.

        Logic:
            1. 테마별 지정 색상이 있으면 우선 사용
            2. 없으면 반대 테마 색상을 가져와 HLS 알고리즘으로 명도 보정
            3. 레거시 'color' 필드도 확인

        Args:
            rule: 색상 규칙 객체
            is_dark_theme: 다크 테마 여부

        Returns:
            Optional[str]: 적용할 최종 색상 코드 (Hex), 없으면 None
        """
        target_color = None

        # 1. 테마별 명시적 색상 확인
        if is_dark_theme and rule.dark_color:
            target_color = rule.dark_color
        elif not is_dark_theme and rule.light_color:
            target_color = rule.light_color

        # 2. 폴백: 반대 테마 색상이나 레거시 색상 사용 및 자동 보정
        if not target_color:
            # 우선순위: 지정된 반대 색상 -> 레거시 color
            base_color = rule.light_color if is_dark_theme else rule.dark_color
            if not base_color:
                base_color = rule.color

            if base_color:
                target_color = cls._adjust_color_for_theme(base_color, is_dark_theme)

        return target_color

    @staticmethod
    def _adjust_color_for_theme(hex_color: str, is_dark_theme: bool) -> str:
        """
        HLS 색상 모델을 사용하여 배경색에 맞춰 명도를 자동 조절합니다.

        Logic:
            - HEX -> RGB -> HLS 변환
            - 다크 테마 배경 -> 명도를 높임 (밝게)
            - 라이트 테마 배경 -> 명도를 낮춤 (어둡게)
            - HLS -> RGB -> HEX 변환

        Args:
            hex_color: 원본 색상 코드 (#RRGGBB)
            is_dark_theme: 다크 테마 여부

        Returns:
            str: 보정된 색상 코드
        """
        if not hex_color or not hex_color.startswith('#') or len(hex_color) != 7:
            return hex_color

        try:
            # HEX -> RGB
            r = int(hex_color[1:3], 16) / 255.0
            g = int(hex_color[3:5], 16) / 255.0
            b = int(hex_color[5:7], 16) / 255.0

            # RGB -> HLS
            h, l, s = colorsys.rgb_to_hls(r, g, b)

            # 명도(Lightness) 조정
            if is_dark_theme:
                # 어두운 배경: 글자는 밝아야 함 (최소 0.6 이상)
                if l < 0.5:
                    l = 0.6 + (0.4 * l) # 어두운 색을 밝게 보정
            else:
                # 밝은 배경: 글자는 어두워야 함 (최대 0.4 이하)
                if l > 0.5:
                    l = 0.4 * l # 밝은 색을 어둡게 보정

            # HLS -> RGB -> HEX
            r, g, b = colorsys.hls_to_rgb(h, l, s)
            r, g, b = int(r * 255), int(g * 255), int(b * 255)

            # 클램핑 (0~255 범위 보장)
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            return '#{:02x}{:02x}{:02x}'.format(r, g, b)

        except ValueError:
            return hex_color

    @classmethod
    def _apply_single_rule(cls, text: str, pattern: str, color: str, regex_enabled: bool) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.

        Logic:
            - Regex 규칙: 캐시된 정규식 객체를 사용하여 치환
            - 일반 규칙: str.replace를 사용하여 단순 치환

        Args:
            text (str): 텍스트
            pattern (str): 매칭 패턴
            color (str): 적용할 색상 코드
            regex_enabled (bool): 정규식 여부

        Returns:
            str: 적용된 텍스트
        """
        if regex_enabled:
            try:
                # 캐시 확인 및 컴파일
                if pattern not in cls._regex_cache:
                    cls._regex_cache[pattern] = re.compile(pattern)

                pattern_obj = cls._regex_cache[pattern]

                # 그룹 0(\g<0>)을 사용하여 매칭된 전체 문자열을 감쌈
                return pattern_obj.sub(
                    rf'<span style="color:{color};">\g<0></span>',
                    text
                )
            except re.error:
                return text
        else:
            # 단순 문자열 치환
            return text.replace(
                pattern,
                f'<span style="color:{color};">{pattern}</span>'
            )

    @classmethod
    def clear_cache(cls) -> None:
        """캐시된 정규식 객체를 초기화합니다."""
        cls._regex_cache.clear()
