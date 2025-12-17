"""
색상 처리 서비스 모듈

텍스트에 대한 색상 규칙 적용, 정규식 매칭 등의 로직을 처리합니다.

## WHY
* ColorManager에서 로직을 분리하여 '상태 관리'와 '로직 수행'의 책임을 명확히 함
* 테스트 용이성 향상 (상태 의존성 없이 로직 테스트 가능)
* 향후 색상 처리 로직이 복잡해질 경우를 대비한 확장성 확보

## WHAT
* 텍스트에 색상 규칙 적용 (HTML 태그 생성)
* 정규식 및 단순 문자열 매칭

## HOW
* Stateless 클래스 (또는 정적 메서드)로 구현
* 외부에서 규칙 리스트를 주입받아 처리
"""
import re
from typing import List
from common.dtos import ColorRule

class ColorService:
    """
    색상 적용 및 패턴 매칭 서비스
    """

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

    @staticmethod
    def _apply_single_rule(text: str, rule: ColorRule) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.

        Logic:
            - Regex 규칙: re.sub를 사용하여 패턴 매칭 후 색상 태그로 치환
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
                # 그룹 0(\g<0>)을 사용하여 매칭된 전체 문자열을 감쌈
                return re.sub(
                    rule.pattern,
                    rf'<span style="color:{rule.color};">\g<0></span>',
                    text
                )
            except re.error:
                # 정규식 에러 시 무시하고 원본 반환
                return text
        else:
            # 단순 문자열 치환
            return text.replace(
                rule.pattern,
                f'<span style="color:{rule.color};">{rule.pattern}</span>'
            )