"""
색상 규칙 저장소 (Color Rule Repository)

색상 규칙(`ColorRule`) 리스트의 데이터 관리(기본값·CRUD·JSON 영속화)만 전담한다.
PyQt5를 import하지 않는 순수 데이터 로직 클래스로, `ColorManager`(Qt 어댑터)가
내부적으로 이 클래스에 위임한다 (S-054, `view/managers/color_manager.py` 분해).

## WHY
* `ColorManager`(511줄)가 데이터 로직(규칙 CRUD·영속화)과 Qt 어댑터(서식 생성)를
  한 클래스에 섞고 있어(S-050 조사) 단위 테스트가 PyQt5 없이는 불가능했다.
* 규칙 CRUD·영속화는 Qt 없이도 단위 테스트할 수 있는 순수 로직이므로 분리한다.

## WHAT
* 기본 색상 규칙 데이터(`DEFAULT_COLOR_RULES`).
* 규칙 리스트 보관(`_rules`) 및 CRUD(`add_custom_rule`/`remove_rule`/`toggle_rule`).
* JSON 영속화(`load_rules`/`save_rules`).
* 색상 코드 정규화(`_ensure_hex`) 및 규칙 조회(`get_rule_color`).

## HOW
* `ColorRule`(dataclass, `common/dtos.py`)과 표준 라이브러리(`json`, `pathlib`)만 사용.
* Qt 서식(QTextCharFormat 등) 생성이나 테마 팔레트(COLOR_* 상수) 동기화는 이 클래스의
  책임이 아니다 — 그 부분은 `ColorManager`(Qt 어댑터)에 남는다.
"""
import json
from typing import List

from common.dtos import ColorRule
from core.logger import logger
from common.constants import (
    LOG_COLOR_DARK_TIMESTAMP, LOG_COLOR_DARK_INFO, LOG_COLOR_DARK_ERROR,
    LOG_COLOR_DARK_WARN, LOG_COLOR_DARK_PROMPT, LOG_COLOR_DARK_SUCCESS,
    LOG_COLOR_LIGHT_TIMESTAMP, LOG_COLOR_LIGHT_INFO, LOG_COLOR_LIGHT_ERROR,
    LOG_COLOR_LIGHT_WARN, LOG_COLOR_LIGHT_PROMPT, LOG_COLOR_LIGHT_SUCCESS,
)


class ColorRuleRepository:
    """
    색상 규칙 리스트의 데이터 관리 전담 클래스 (Qt 의존 0).

    기본 규칙 데이터, JSON 영속화, CRUD를 담당한다. Qt 서식 변환이나 테마 팔레트
    동기화는 이 클래스가 아니라 이 클래스를 사용하는 Qt 어댑터(`ColorManager`)의
    책임이다.
    """

    # -------------------------------------------------------------------------
    # 기본 규칙 정의 (Default Rules)
    # -------------------------------------------------------------------------
    DEFAULT_COLOR_RULES = [
        ColorRule("AT_OK", r'\bOK\b',
                  light_color=LOG_COLOR_LIGHT_SUCCESS,
                  dark_color=LOG_COLOR_DARK_SUCCESS),
        ColorRule("AT_ERROR", r'\bERROR\b',
                  light_color=LOG_COLOR_LIGHT_ERROR,
                  dark_color=LOG_COLOR_DARK_ERROR),
        ColorRule("URC", r'(\+\w+:)',
                  light_color=LOG_COLOR_LIGHT_WARN,
                  dark_color=LOG_COLOR_DARK_WARN),
        ColorRule("PROMPT", r'^>',
                  light_color=LOG_COLOR_LIGHT_PROMPT,
                  dark_color=LOG_COLOR_DARK_PROMPT),
        # 시스템 로그 규칙
        ColorRule("SYS_INFO", r'\[INFO\]',
                  light_color=LOG_COLOR_LIGHT_INFO,
                  dark_color=LOG_COLOR_DARK_INFO),
        ColorRule("SYS_ERROR", r'\[ERROR\]',
                  light_color=LOG_COLOR_LIGHT_ERROR,
                  dark_color=LOG_COLOR_DARK_ERROR),
        ColorRule("SYS_WARN", r'\[WARN\]',
                  light_color=LOG_COLOR_LIGHT_WARN,
                  dark_color=LOG_COLOR_DARK_WARN),
        ColorRule("SYS_SUCCESS", r'\[SUCCESS\]',
                  light_color=LOG_COLOR_LIGHT_SUCCESS,
                  dark_color=LOG_COLOR_DARK_SUCCESS),
        # 타임스탬프 규칙
        ColorRule("TIMESTAMP", r'\[\d{2}:\d{2}:\d{2}\]',
                  light_color=LOG_COLOR_LIGHT_TIMESTAMP,
                  dark_color=LOG_COLOR_DARK_TIMESTAMP),
    ]

    def __init__(self) -> None:
        """규칙 리스트를 빈 상태로 초기화합니다 (기본값 채우기는 `init_default_rules`)."""
        self._rules: List[ColorRule] = []

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def _ensure_hex(self, color_code: str) -> str:
        """
        색상 코드가 HEX 형식이면 '#'을 보장합니다.

        Args:
            color_code (str): 입력 색상 코드 (예: 'FF0000', '#FF0000', 'red')

        Returns:
            str: '#'이 포함된 색상 코드
        """
        if not color_code:
            return ""

        # 6자리 또는 8자리 16진수 문자열인 경우 '#' 추가
        if not color_code.startswith("#") and len(color_code) in [6, 8]:
            # 모든 문자가 16진수인지 확인 (선택 사항이나 안전을 위해)
            try:
                int(color_code, 16)
                return f"#{color_code}"
            except ValueError:
                pass  # HEX가 아닌 이름(red, blue)일 수 있음

        return color_code

    def init_default_rules(self) -> None:
        """기본 규칙을 로드하고 색상 코드를 정규화합니다."""
        self._rules = []
        for rule in self.DEFAULT_COLOR_RULES:
            # DTO 복제 및 색상 정규화
            new_rule = ColorRule(
                name=rule.name,
                pattern=rule.pattern,
                color=self._ensure_hex(rule.color),
                light_color=self._ensure_hex(rule.light_color),
                dark_color=self._ensure_hex(rule.dark_color),
                regex_enabled=rule.regex_enabled,
                enabled=rule.enabled,
                bold=getattr(rule, 'bold', False)
            )
            self._rules.append(new_rule)

    # -------------------------------------------------------------------------
    # Logic & Management Methods
    # -------------------------------------------------------------------------
    def get_rule_color(self, rule_name: str) -> str:
        """
        특정 규칙의 현재(마지막으로 동기화된) HEX 색상 코드를 반환합니다.

        Args:
            rule_name (str): 규칙 이름.

        Returns:
            str: HEX 색상 코드.
        """
        for rule in self._rules:
            if rule.name == rule_name:
                return rule.color  # 이미 갱신된 값 사용
        return "#000000"

    def add_custom_rule(self, name: str, pattern: str, color: str, regex_enabled: bool = True) -> None:
        """
        사용자 정의 색상 규칙을 추가합니다.

        Args:
            name (str): 규칙 이름.
            pattern (str): 매칭 패턴.
            color (str): 색상 코드.
            regex_enabled (bool): 정규식 사용 여부.
        """
        self.remove_rule(name)

        # 입력받은 색상 코드 정규화
        safe_color = self._ensure_hex(color)

        new_rule = ColorRule(
            name=name,
            pattern=pattern,
            color=safe_color,
            light_color=safe_color,
            dark_color=safe_color,
            regex_enabled=regex_enabled,
            enabled=True
        )
        self._rules.append(new_rule)

    def remove_rule(self, name: str) -> None:
        """
        규칙을 삭제합니다.

        Args:
            name (str): 삭제할 규칙 이름.
        """
        self._rules = [r for r in self._rules if r.name != name]

    def toggle_rule(self, name: str) -> None:
        """
        규칙의 활성/비활성 상태를 토글합니다.

        Args:
            name (str): 대상 규칙 이름.
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                break

    def save_rules(self, file_path: str) -> None:
        """
        규칙 리스트를 JSON 파일로 저장합니다.

        Args:
            file_path (str): 저장할 파일 경로.
        """
        rules_data = [
            {
                'name': r.name,
                'pattern': r.pattern,
                'color': r.color,
                'light_color': r.light_color,
                'dark_color': r.dark_color,
                'regex_enabled': r.regex_enabled,
                'enabled': r.enabled
            }
            for r in self._rules
        ]
        data = {'color_rules': rules_data}
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Color rules saved to {file_path}")
        except IOError as e:
            logger.error(f"Error saving color rules: {e}")

    def load_rules(self, file_path: str) -> None:
        """
        JSON 파일에서 규칙을 로드합니다.
        파일을 읽을 때 색상 코드에 '#'이 없으면 자동으로 붙여서 메모리에 적재합니다.

        Logic:
            - 파일 읽기 및 JSON 파싱
            - DTO 변환 시 _ensure_hex 적용 (이 부분이 핵심 Fix)
            - 실패 시 기본 규칙 사용

        Args:
            file_path (str): 읽을 파일 경로.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 호환성 처리: "color_rules" 키가 없으면 데이터 자체가 리스트라고 가정
            rules_data = data.get('color_rules', data) if isinstance(data, dict) else data

            self._rules = []
            for r in rules_data:
                # 레거시 데이터 호환성 처리
                legacy_color = r.get('color', '')
                light_c = r.get('light_color', '')
                dark_c = r.get('dark_color', '')

                if not light_c:
                    light_c = legacy_color
                if not dark_c:
                    dark_c = legacy_color

                # [핵심] 로드 시점에 모든 색상 데이터 정규화 (# 붙이기)
                self._rules.append(ColorRule(
                    name=r.get('name', 'Unknown'),
                    pattern=r.get('pattern', ''),
                    color=self._ensure_hex(legacy_color),
                    light_color=self._ensure_hex(light_c),
                    dark_color=self._ensure_hex(dark_c),
                    regex_enabled=r.get('regex_enabled', True),
                    enabled=r.get('enabled', True),
                    bold=r.get('bold', False)
                ))

            logger.debug(f"Loaded {len(self._rules)} color rules.")
        except Exception as e:
            logger.error(f"Failed to load color rules ({file_path}): {e}")
            self.init_default_rules()
