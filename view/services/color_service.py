"""
색상 처리 서비스 모듈

텍스트에 대한 색상 규칙 적용, 정규식 매칭 등의 로직을 처리합니다.

## WHY
* ColorManager에서 로직을 분리하여 '상태 관리'와 '로직 수행'의 책임 분리
* 테스트 용이성 향상 (Stateless)
* 반복적인 정규식 컴파일로 인한 성능 저하 방지 (Caching)

## WHAT
* 텍스트에 색상 규칙 적용 (HTML 태그 생성)
* 정규식 및 단순 문자열 매칭
* 정규식 객체 캐싱

## HOW
* Stateless 클래스 (정적 메서드)로 구현
* 외부에서 규칙 리스트를 주입받아 처리
* 클래스 레벨 딕셔너리를 사용한 정규식 캐싱
"""
import re
from typing import List, Dict, Pattern
from common.dtos import ColorRule
from core.logger import logger

class ColorService:
    """
    색상 적용 및 패턴 매칭 서비스
    """

    # 정규식 컴파일 캐시 (패턴 문자열 -> 컴파일된 객체)
    _regex_cache: Dict[str, Pattern] = {}

    @staticmethod
    def apply_rules(text: str, rules: List[ColorRule]) -> str:
        """
        텍스트에 색상 규칙 리스트를 순차적으로 적용합니다.

        Args:
            text (str): 원본 텍스트
            rules (List[ColorRule]): 적용할 색상 규칙 리스트

        Returns:
            str: HTML 색상 태그가 적용된 텍스트
        """
        result = text
        for rule in rules:
            if rule.enabled:
                result = ColorService._apply_single_rule(result, rule)
        return result

    @classmethod
    def _apply_single_rule(cls, text: str, rule: ColorRule) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.

        Logic:
            - Regex 규칙: 캐시된 정규식 객체를 사용하여 치환 (성능 최적화)
            - 일반 규칙: str.replace를 사용하여 단순 치환
            - 에러 발생(잘못된 정규식 등) 시 원본 텍스트 반환

        Args:
            text (str): 텍스트
            rule (ColorRule): 규칙 객체

        Returns:
            str: 적용된 텍스트
        """
        if rule.is_regex:
            try:
                # 캐시 확인 및 컴파일
                if rule.pattern not in cls._regex_cache:
                    cls._regex_cache[rule.pattern] = re.compile(rule.pattern)

                pattern_obj = cls._regex_cache[rule.pattern]

                # 그룹 0(\g<0>)을 사용하여 매칭된 전체 문자열을 감쌈
                return pattern_obj.sub(
                    rf'<span style="color:{rule.color};">\g<0></span>',
                    text
                )
            except re.error as e:
                # 정규식 에러 시 로그를 남기고 무시 (원본 반환)
                # 빈번한 로그 출력을 막기 위해 디버그 레벨 권장하나, 여기선 안전하게 처리
                return text
        else:
            # 단순 문자열 치환
            return text.replace(
                rule.pattern,
                f'<span style="color:{rule.color};">{rule.pattern}</span>'
            )

    @classmethod
    def clear_cache(cls) -> None:
        """캐시된 정규식 객체를 초기화합니다."""
        cls._regex_cache.clear()
