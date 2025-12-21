"""
색상 규칙 관리자 (Color Manager)

애플리케이션 전반의 패턴 매칭 색상 규칙의 상태, 설정(JSON), 활성화 여부를 관리합니다.
실제 텍스트 파싱 및 HTML 태그 적용 로직은 `ColorService`에 위임하여 처리합니다.

## WHY
* 색상 규칙의 영속성(저장/로드)을 관리하여 사용자 설정을 유지
* UI 전반에서 접근 가능한 전역적인 규칙 데이터 제공 (SSOT)
* 로그 가독성을 위해 테마(Dark/Light)에 따른 듀얼 컬러 정책 지원

## WHAT
* 규칙 리스트 관리 (추가/삭제/토글/조회)
* 설정 파일(color_rules.json) 로드 및 저장
* 기본 규칙 제공 (타임스탬프, 시스템 로그 등)

## HOW
* Singleton 패턴으로 전역 인스턴스 보장
* ColorService를 통한 로직 위임 (Logic Delegation)
* JSON 직렬화/역직렬화를 통한 설정 관리
"""
import os
import json
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor, QTextCharFormat, QBrush, QFont

from core.logger import logger
from common.dtos import ColorRule
from view.services.color_service import ColorService
from common.constants import (
    LOG_COLOR_DARK_TIMESTAMP, LOG_COLOR_DARK_INFO, LOG_COLOR_DARK_ERROR,
    LOG_COLOR_DARK_WARN, LOG_COLOR_DARK_PROMPT, LOG_COLOR_DARK_SUCCESS,
    LOG_COLOR_LIGHT_TIMESTAMP, LOG_COLOR_LIGHT_INFO, LOG_COLOR_LIGHT_ERROR,
    LOG_COLOR_LIGHT_WARN, LOG_COLOR_LIGHT_PROMPT, LOG_COLOR_LIGHT_SUCCESS,
)
from view.managers.theme_manager import theme_manager
from view.services.color_service import ColorService

class ColorManager(QObject):
    """
    색상 규칙 관리자 클래스입니다 (Singleton).
    규칙의 로드, 저장, 활성화/비활성화 상태를 관리하며,
    실제 적용 로직은 ColorService에 위임합니다.
    """
    _instance = None
    _initialized = False

    # -------------------------------------------------------------------------
    # 색상 팔레트 정의 (Dark Theme 기준 - Fallback용)
    # -------------------------------------------------------------------------
    # 실제 색상 값은 ColorService의 로직이나 테마 설정에 따라 달라질 수 있으나,
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
    # 여기서는 UI 객체 생성을 위한 기본값을 정의합니다.
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
        Singleton 인스턴스 보장 및 초기화 플래그 설정
        """
        if not cls._instance:
            # QObject 상속 시 super().__new__에는 인자를 전달하지 않는 것이 안전함
            cls._instance = super(ColorManager, cls).__new__(cls)
            # 인스턴스 생성 직후 플래그 초기화
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path: Optional[str] = None) -> None:
        """
        ColorManager 초기화

        Logic:
            - 중복 초기화 방지
            - 리소스 경로 설정 (설정 파일 위치 결정)
            - 설정 파일 로드 시도, 실패 시 기본 규칙 적용

        Args:
            resource_path (Optional[str]): 리소스 루트 디렉토리 경로.
        """
        # 싱글톤 중복 초기화 방지
        if hasattr(self, '_initialized') and self._initialized:
            return

        super().__init__()

        self._rules: List[ColorRule] = []
        self._resource_path = resource_path
        
        # 설정 파일 경로 결정
        # resource_path가 있으면 사용, 없으면 현재 위치 기준 Fallback
        if self._resource_path:
            self.config_path = Path(self._resource_path) / 'configs' / 'color_rules.json'
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.config_path = base_dir / 'resources' / 'configs' / 'color_rules.json'

        # 초기 로드
        if self.config_path.exists():
            self.load_rules(str(self.config_path))
        else:
            self.rules = self.DEFAULT_COLOR_RULES.copy()
            # 디렉토리 생성 및 기본값 저장
            if not self.config_path.parent.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_rules(str(self.config_path))

        self._initialized = True

    def _create_format(self, color_input: str, bold: bool = False) -> QTextCharFormat:
        """
        색상 키(Key) 또는 HEX 코드를 사용하여 QTextCharFormat 객체를 생성합니다.

        Logic:
            - 입력값이 키('info')인지 HEX('#FF0000')인지 확인
            - 키라면 내부 팔레트 매핑을 사용해 HEX로 변환
            - QBrush, QFont 설정

        Args:
            color_input (str): 색상 키(예: 'info') 또는 HEX 코드.
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

        # 키로 조회 시도, 없으면 입력값(HEX) 그대로 사용
        hex_code = color_map.get(color_input.lower(), color_input)

        # 유효한 HEX 형식이 아니면 기본값 사용
        if not hex_code.startswith("#"):
            hex_code = self.COLOR_DEFAULT

        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(QColor(hex_code)))
        if bold:
            fmt.setFontWeight(QFont.Bold)
        return fmt

    def _init_rules(self) -> None:
        """
        ColorService로부터 구문 강조 규칙(DTO)을 가져와 Qt 서식으로 변환합니다.

        Logic:
            - ColorService.get_syntax_rules() 호출
            - 반환된 ColorRule 객체들을 순회
            - (정규식 패턴, QTextCharFormat) 튜플 리스트 생성
        """
        self._rules.clear()
            # 1. 타임스탬프 (HH:mm:ss.zzz)

        rule_dtos: List[ColorRule] = ColorService.get_syntax_rules()
            # 2. 로그 레벨 태그
        for rule in rule_dtos:
            if not rule.enabled:
                continue

            # 3. 데이터 송수신 태그

            # 4. 시스템 메시지 태그
            fmt = self._create_format(rule.color, bold=getattr(rule, 'bold', False))

            # 5. 특수 패턴 (예: HEX 데이터 강조)
            self._rules.append((rule.pattern, fmt))


    @property
    def rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """
        현재 설정된 하이라이팅 규칙 목록을 반환합니다.

        Returns:
            List[Tuple[str, QTextCharFormat]]: (정규식 패턴, 서식) 튜플의 리스트.
        """
        return self._rules

    def get_color_for_key(self, key: str) -> QColor:
        """
        특정 키에 해당하는 QColor 객체를 반환합니다.
        (커스텀 위젯에서 직접 색상을 사용할 때 유용)

        Args:
            key (str): 색상 키 (예: 'RX', 'TX', 'ERROR').

        Returns:
            QColor: 매핑된 색상 객체. 없을 경우 흰색 반환.
        """
        color_map = {
            "RX": self.COLOR_RX,
            "TX": self.COLOR_TX,
            "INFO": self.COLOR_INFO,
            "ERROR": self.COLOR_ERROR,
            "WARNING": self.COLOR_WARNING,
            "SYSTEM": self.COLOR_SYSTEM,
            "DEBUG": self.COLOR_DEBUG
        }

        hex_code = color_map.get(key.upper(), "#FFFFFF")
        return QColor(hex_code)

    def update_theme(self, theme_name: str) -> None:
        """
        테마 변경 시 색상 팔레트를 업데이트하고 규칙을 재생성합니다.
        (현재는 Dark 테마 위주이나, 추후 Light 테마 지원 시 확장 가능)

        Args:
            theme_name (str): 테마 이름 ('dark' or 'light').
        """
        if theme_name == 'light':
            # 라이트 테마용 색상 변경
            self.COLOR_TIMESTAMP = "#555555"
            self.COLOR_RX = "#0000FF"
            self.COLOR_TX = "#CC6600"
            self.COLOR_INFO = "#2E7D32"
            self.COLOR_WARNING = "#F57F17"
            self.COLOR_ERROR = "#D32F2F"
            self.COLOR_SYSTEM = "#7B1FA2"
            self.COLOR_DEBUG = "#0097A7"
            self.COLOR_DEFAULT = "#000000"
        else:
            # 다크 테마 기본값 복원
            self.COLOR_TIMESTAMP = "#808080"
            self.COLOR_INFO = "#4CAF50"
            self.COLOR_WARNING = "#FFC107"
            self.COLOR_ERROR = "#FF5252"
            self.COLOR_RX = "#2196F3"
            self.COLOR_TX = "#FF9800"
            self.COLOR_SYSTEM = "#9C27B0"
            self.COLOR_DEBUG = "#00BCD4"
            self.COLOR_DEFAULT = "#CCCCCC"

        # 규칙 재생성
        self._init_rules()

    def apply_rules(self, text: str) -> str:
        """
        텍스트에 모든 활성화된 색상 규칙을 적용합니다.
        
        Logic:
            - 현재 테마 상태(Dark/Light)를 확인 (ThemeManager 연동)
            - ColorService에 위임하여 HTML 태그 생성

        Args:
            text (str): 색상 규칙을 적용할 원본 텍스트.

        Returns:
            str: HTML span 태그로 색상이 적용된 텍스트.
        """       
        is_dark = theme_manager.is_dark_theme()
        return ColorService.apply_rules(text, self.rules, is_dark)

    def add_custom_rule(self, name: str, pattern: str, color: str, regex_enabled: bool = True) -> None:
        """
        사용자 정의 색상 규칙을 추가합니다.

        Args:
            name (str): 규칙 이름.
            pattern (str): 매칭 패턴 (정규식 또는 일반 문자열).
            color (str): HTML 색상 코드 (예: '#FF0000').
            regex_enabled (bool, optional): 정규식 패턴 여부. 기본값은 True.
        """
        # 중복 이름 확인 및 제거 (덮어쓰기)
        self.remove_rule(name)
        
        new_rule = ColorRule(
            name=name, 
            pattern=pattern, 
            color=color, # Legacy 필드 호환
            light_color=color, # 단일 색상 입력 시 Light/Dark 동일하게 설정
            dark_color=color,
            regex_enabled=regex_enabled
        )
        self.rules.append(new_rule)

    def remove_rule(self, name: str) -> None:
        """
        사용자 정의 색상 규칙을 삭제합니다.

        Args:
            name (str): 규칙 이름.
        """
        self._rules = [r for r in self._rules if r.name != name]

    def toggle_rule(self, name: str) -> None:
        """
        사용자 정의 색상 규칙의 활성/비활성 상태를 토글합니다.

        Args:
            name (str): 규칙 이름.
        """
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                break

    def save_rules(self, file_path: str) -> None:
        """
        현재 규칙들을 JSON 파일로 저장합니다.

        Logic:
            - ColorRule 객체들을 딕셔너리로 직렬화
            - JSON 파일 쓰기

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
        JSON 파일에서 규칙들을 로드합니다.

        Logic:
            - 파일 읽기 및 JSON 파싱
            - DTO(ColorRule) 객체로 변환하여 리스트 갱신
            - 실패 시 기본 규칙 복원

        Args:
            file_path (str): 읽을 파일 경로.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 호환성: "color_rules" 키가 없으면 리스트 자체로 간주
            if isinstance(data, dict) and 'color_rules' in data:
                rules_data = data['color_rules']
            else:
                rules_data = data

            self._rules = [
                ColorRule(
                    name=r.get('name', 'Unknown'),
                    pattern=r.get('pattern', ''),
                    color=r.get('color', ''),
                    light_color=r.get('light_color', ''),
                    dark_color=r.get('dark_color', ''),
                    regex_enabled=r.get('regex_enabled', True),
                    enabled=r.get('enabled', True)
                )
                for r in rules_data
            ]
            logger.debug(f"Loaded {len(self._rules)} color rules.")
            
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load color rules ({file_path}): {e}")
            self._rules = self.DEFAULT_COLOR_RULES.copy()

    @staticmethod
    def _get_config_path() -> Path:
        """
        (내부용) 색상 규칙 설정 파일의 경로를 반환합니다.
        
        Note:
            __init__에서 이미 self.config_path를 설정하므로 보조적인 용도로 사용됩니다.

        Returns:
            Path: 설정 파일 경로 객체.
        """
        if ColorManager._instance and hasattr(ColorManager._instance, 'config_path'):
             return ColorManager._instance.config_path
        return Path("resources/configs/color_rules.json")

    @staticmethod
    def _apply_single_rule(text: str, rule: ColorRule) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.
        (ColorService의 기능을 래핑하거나 독립적으로 사용할 때 활용)

        Args:
            text (str): 원본 텍스트.
            rule (ColorRule): 적용할 색상 규칙 객체.

        Returns:
            str: 규칙이 적용된 텍스트.
        """
        # 편의상 현재 ColorService에 위임 (일관성 유지)
        # Note: 실제 서비스 로직과 동일하게 동작해야 함
        
        return ColorService._apply_single_rule(text, rule.pattern, rule.color, rule.regex_enabled)

# 전역에서 접근 가능한 싱글톤 인스턴스
color_manager = ColorManager()