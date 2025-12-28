"""
색상 규칙 관리자 (Color Manager)

애플리케이션 전반의 구문 강조(Syntax Highlighting) 및 색상 규칙을 중앙에서 관리합니다.
데이터 관리(DTO/JSON)와 UI 렌더링 지원(Qt Format)을 동시에 수행하는 하이브리드 클래스입니다.

## WHY
* 색상 규칙의 영속성(JSON 저장/로드) 관리 및 사용자 설정 유지
* Qt 위젯(View)에 필요한 서식 객체(QTextCharFormat) 제공
* 로직(Service)과 뷰(Widget) 사이의 데이터 브리지 역할 (SSOT)

## WHAT
* 규칙 리스트 관리 (추가/삭제/토글) 및 파일 입출력
* ColorRule DTO를 Qt TextFormat으로 변환하여 반환
* 텍스트 기반의 HTML 태그 생성 위임 (ColorService)
* 테마(Dark/Light) 변경에 따른 내부 색상 팔레트 및 규칙 색상 동기화

## HOW
* Singleton 패턴으로 전역 접근 보장
* 내부적으로 ColorRule DTO 리스트를 유지하며, 요청 시 Qt 객체로 변환하여 제공
* ThemeManager와 연동하여 현재 테마에 맞는 색상 적용 (순환 참조 방지 적용)
"""
import os
import json
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor, QTextCharFormat, QBrush, QFont

from core.logger import logger
from core.resource_path import ResourcePath
from common.dtos import ColorRule
from view.services.color_service import ColorService
from common.constants import (
    LOG_COLOR_DARK_TIMESTAMP, LOG_COLOR_DARK_INFO, LOG_COLOR_DARK_ERROR,
    LOG_COLOR_DARK_WARN, LOG_COLOR_DARK_PROMPT, LOG_COLOR_DARK_SUCCESS,
    LOG_COLOR_LIGHT_TIMESTAMP, LOG_COLOR_LIGHT_INFO, LOG_COLOR_LIGHT_ERROR,
    LOG_COLOR_LIGHT_WARN, LOG_COLOR_LIGHT_PROMPT, LOG_COLOR_LIGHT_SUCCESS,
)


class ColorManager(QObject):
    """
    색상 규칙 관리자 클래스 (Singleton).
    설정 파일 관리, 규칙 로드/저장, Qt 서식 생성을 담당합니다.
    """

    _instance = None
    _initialized = False

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

    def __new__(cls, *args, **kwargs):
        """
        Singleton 인스턴스 보장
        """
        if not cls._instance:
            cls._instance = super(ColorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """
        ColorManager 초기화

        Logic:
            - 중복 초기화 방지
            - ResourcePath 설정 및 설정 파일 경로 계산
            - 기본 테마 색상 팔레트 초기화
            - 설정 파일 로드 (없으면 기본값 생성)

        Args:
            resource_path (Optional[ResourcePath]): 리소스 경로 관리 객체.
        """
        if self._initialized:
            # ResourcePath가 나중에 주입되는 경우를 대비해 업데이트
            if resource_path:
                self._resource_path = resource_path
            return

        super().__init__()

        # ResourcePath 설정 (없으면 생성)
        if resource_path is None:
            resource_path = ResourcePath()
        self._resource_path = resource_path

        self._rules: List[ColorRule] = []

        # 내부 색상 팔레트 변수 초기화 (기본값: Dark Theme)
        self.apply_theme('dark')

        # 설정 파일 경로 결정 (ResourcePath 활용)
        self.config_path = self._resource_path.config_dir / 'color_rules.json'

        # 초기 규칙 로드
        if self.config_path.exists():
            self.load_rules(str(self.config_path))
        else:
            # 기본 규칙을 복사해서 사용할 때도 sanitize 과정을 거침
            self._init_default_rules()

            # 디렉토리가 없으면 생성 (ResourcePath가 보통 보장하지만 안전장치)
            if not self.config_path.parent.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_rules(str(self.config_path))

        # [중요] 규칙 로드 후 현재 테마에 맞춰 색상 동기화 실행
        self.apply_theme('dark')

        self._initialized = True

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
                pass # HEX가 아닌 이름(red, blue)일 수 있음

        return color_code

    def _init_default_rules(self) -> None:
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
        return QColor("#000000")

    def apply_theme(self, theme_name: str) -> None:
        """
        테마 변경 시 내부 색상 팔레트 변수를 업데이트하고,
        모든 규칙(self._rules)의 .color 필드를 현재 테마에 맞게 갱신합니다.

        Args:
            theme_name (str): 테마 이름 ('dark' or 'light').
        """
        is_light = (theme_name.lower() == 'light')

        # 1. 상수 팔레트 업데이트 (HEX 코드 보장)
        if is_light:
            self.COLOR_TIMESTAMP = self._ensure_hex(LOG_COLOR_LIGHT_TIMESTAMP)
            self.COLOR_INFO = self._ensure_hex(LOG_COLOR_LIGHT_INFO)
            self.COLOR_WARNING = self._ensure_hex(LOG_COLOR_LIGHT_WARN)
            self.COLOR_ERROR = self._ensure_hex(LOG_COLOR_LIGHT_ERROR)
            self.COLOR_RX = "#0000FF"
            self.COLOR_TX = "#CC6600"
            self.COLOR_SYSTEM = "#7B1FA2"
            self.COLOR_DEBUG = "#0097A7"
            self.COLOR_DEFAULT = "#000000"
        else:
            self.COLOR_TIMESTAMP = self._ensure_hex(LOG_COLOR_DARK_TIMESTAMP)
            self.COLOR_INFO = self._ensure_hex(LOG_COLOR_DARK_INFO)
            self.COLOR_WARNING = self._ensure_hex(LOG_COLOR_DARK_WARN)
            self.COLOR_ERROR = self._ensure_hex(LOG_COLOR_DARK_ERROR)
            self.COLOR_RX = "#2196F3"
            self.COLOR_TX = "#FF9800"
            self.COLOR_SYSTEM = "#9C27B0"
            self.COLOR_DEBUG = "#00BCD4"
            self.COLOR_DEFAULT = "#CCCCCC"

        # 2. 규칙 리스트 색상 동기화
        for rule in self._rules:
            active_color = rule.light_color if is_light else rule.dark_color

            if not active_color:
                active_color = rule.color

            # 여기서 한번 더 HEX 보정하여 객체 상태를 완벽하게 유지
            rule.color = self._ensure_hex(active_color)

    # -------------------------------------------------------------------------
    # Logic & Management Methods
    # -------------------------------------------------------------------------
    def get_rule_color(self, rule_name: str) -> str:
        """
        특정 규칙의 현재 테마에 맞는 HEX 색상 코드를 반환합니다.

        Args:
            rule_name (str): 규칙 이름.

        Returns:
            str: HEX 색상 코드.
        """
        for rule in self._rules:
            if rule.name == rule_name:
                return rule.color # 이미 갱신된 값 사용
        return "#000000"

    def apply_rules(self, text: str) -> str:
        """
        텍스트에 HTML 태그 기반의 색상 규칙을 적용합니다. (ColorService 위임)

        Args:
            text (str): 원본 텍스트.

        Returns:
            str: HTML 태그가 적용된 텍스트.
        """
        # [중요] 순환 참조 방지
        from view.managers.theme_manager import theme_manager
        is_dark = theme_manager.is_dark_theme()

        # ColorService가 rule.color(또는 light/dark)를 참조할 때 #이 붙은 값을 쓰게 됨
        return ColorService.apply_rules(text, self._rules, is_dark)

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

                if not light_c: light_c = legacy_color
                if not dark_c: dark_c = legacy_color

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
            self._init_default_rules()

    @staticmethod
    def _get_config_path() -> Path:
        """
        설정 파일의 기본 경로를 반환합니다. (인스턴스가 없거나 초기화 전일 때 사용)

        Returns:
            Path: 'resources/configs/color_rules.json' 경로 객체.
        """
        if ColorManager._instance and hasattr(ColorManager._instance, 'config_path'):
             return ColorManager._instance.config_path
        return Path("resources/configs/color_rules.json")

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


# 전역 인스턴스 생성
color_manager = ColorManager()