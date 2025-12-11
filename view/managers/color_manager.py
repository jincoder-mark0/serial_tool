"""
색상 규칙 관리자 (Color Manager)
ReceivedArea에서 사용하는 패턴 매칭 색상 규칙을 관리합니다.
AppConfig를 통해 설정 파일 경로를 관리하며, 싱글톤 패턴을 따릅니다.
"""
import os
import re
from dataclasses import dataclass
from typing import List
from pathlib import Path

try:
    import commentjson as json
except ImportError:
    import json

# 상수 임포트 (하드코딩 제거)
from app_constants import (
    LOG_COLOR_SUCCESS,
    LOG_COLOR_ERROR,
    LOG_COLOR_WARN  # PROMPT용으로 대체 사용하거나 별도 정의 가능
)

@dataclass
class ColorRule:
    """단일 색상 규칙 데이터 클래스입니다."""
    name: str           # 규칙 이름 (예: "AT_OK")
    pattern: str        # 정규식 패턴 또는 문자열
    color: str          # HTML 색상 코드 (예: "#FF0000")
    is_regex: bool = True  # 정규식 사용 여부
    enabled: bool = True   # 규칙 활성화 여부

class ColorManager:
    """
    색상 규칙 관리자 클래스입니다 (Singleton).
    패턴 매칭을 통해 텍스트에 색상을 입히는 규칙들을 관리합니다.
    """

    _instance = None
    _app_config = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ColorManager, cls).__new__(cls)
        return cls._instance

    # 기본 규칙 정의 (상수 활용)
    DEFAULT_COLOR_RULES = [
        ColorRule("AT_OK", r'\bOK\b', LOG_COLOR_SUCCESS),     # 녹색
        ColorRule("AT_ERROR", r'\bERROR\b', LOG_COLOR_ERROR), # 빨강
        ColorRule("URC", r'(\+\w+:)', LOG_COLOR_WARN),        # 노랑 (경고색 활용)
        ColorRule("PROMPT", r'^>', '#00BCD4'),                # 청록 (특수 색상 유지)
    ]

    def __init__(self, app_config=None) -> None:
        """
        ColorManager를 초기화합니다.

        Args:
            app_config: AppConfig 인스턴스. 경로 설정을 위해 사용됩니다.
        """
        if self._initialized:
            return

        # AppConfig 설정 (첫 초기화 시 주입)
        if app_config is not None:
            ColorManager._app_config = app_config

        self.rules: List[ColorRule] = []
        self.config_path = self._get_config_path()

        # 설정 파일 로드 시도, 실패 시 기본 규칙 사용
        if self.config_path.exists():
            self.load_from_json(str(self.config_path))
        else:
            self.rules = self.DEFAULT_COLOR_RULES.copy()
            # 설정 디렉토리가 없으면 생성 (AppConfig가 보장하지만 안전장치)
            if not self.config_path.parent.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_to_json(str(self.config_path))

        self._initialized = True

    def apply_rules(self, text: str) -> str:
        """
        텍스트에 모든 활성화된 색상 규칙을 적용합니다.

        Args:
            text (str): 색상 규칙을 적용할 원본 텍스트.

        Returns:
            str: HTML span 태그로 색상이 적용된 텍스트.
        """
        result = text
        for rule in self.rules:
            if rule.enabled:
                result = self._apply_single_rule(result, rule)
        return result

    def add_custom_rule(self, name: str, pattern: str, color: str, is_regex: bool = True) -> None:
        """
        사용자 정의 색상 규칙을 추가합니다.

        Args:
            name (str): 규칙 이름.
            pattern (str): 매칭 패턴 (정규식 또는 일반 문자열).
            color (str): HTML 색상 코드 (예: '#FF0000').
            is_regex (bool, optional): 정규식 패턴 여부. 기본값은 True.
        """
        self.rules.append(ColorRule(name, pattern, color, is_regex))

    def remove_rule(self, name: str) -> None:
        """
        사용자 정의 색상 규칙을 추가합니다.

        Args:
            name (str): 규칙 이름.
            pattern (str): 매칭 패턴 (정규식 또는 일반 문자열).
            color (str): HTML 색상 코드 (예: '#FF0000').
            is_regex (bool, optional): 정규식 패턴 여부. 기본값은 True.
        """
        self.rules = [r for r in self.rules if r.name != name]

    def toggle_rule(self, name: str) -> None:
        """
        현재 규칙들을 JSON 파일로 저장합니다.

        Args:
            filepath (str): 저장할 파일 경로.
        """
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                break

    def save_to_json(self, filepath: str) -> None:
        """현재 규칙들을 JSON 파일로 저장합니다."""
        rules_data = [
            {
                'name': r.name,
                'pattern': r.pattern,
                'color': r.color,
                'is_regex': r.is_regex,
                'enabled': r.enabled
            }
            for r in self.rules
        ]

        data = {'color_rules': rules_data}

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Error saving color rules: {e}")

    def load_from_json(self, filepath: str) -> None:
        """
        JSON 파일에서 규칙들을 로드합니다.
        파일이 없거나 잘못된 경우 기본 규칙을 사용합니다.

        Args:
            filepath (str): 읽을 파일 경로.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 호환성: "color_rules" 키가 없으면 리스트 자체로 간주
            if isinstance(data, dict) and 'color_rules' in data:
                rules_data = data['color_rules']
            else:
                rules_data = data

            self.rules = [
                ColorRule(
                    r['name'],
                    r['pattern'],
                    r['color'],
                    r.get('is_regex', True),
                    r.get('enabled', True)
                )
                for r in rules_data
            ]
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            # 파일이 없거나 잘못된 경우 기본 규칙 사용
            self._logger.error(f"Failed to load color rules ({filepath}): {e}")
            self.rules = self.DEFAULT_COLOR_RULES.copy()

    @staticmethod
    def _get_config_path() -> 'Path':
        """
        색상 규칙 설정 파일의 경로를 반환합니다.

        Returns:
            Path: config/color_rules.json 파일의 Path 객체.
        """
        if ColorManager._app_config is not None:
            return ColorManager._app_config.config_dir / 'color_rules.json'

        # Fallback: 개발 환경 상대 경로
        # view/managers/ -> view/ -> root
        if hasattr(os, '_MEIPASS'):
            # PyInstaller 번들 환경
            base_path = Path(os._MEIPASS)
        else:
            # 개발 모드 환경
            base_path = Path(__file__).parent.parent.parent

        return base_path / 'config' / 'color_rules.json'

    @staticmethod
    def _apply_single_rule(text: str, rule: ColorRule) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.

        Args:
            text (str): 원본 텍스트.
            rule (ColorManager): 적용할 색상 규칙 객체.

        Returns:
            str: 규칙이 적용된 텍스트.
        """
        if rule.is_regex:
            try:
                return re.sub(
                    rule.pattern,
                    rf'<span style="color:{rule.color};">\g<0></span>',
                    text
                )
            except re.error:
                return text
        else:
            # 단순 문자열 치환
            return text.replace(
                rule.pattern,
                f'<span style="color:{rule.color};">{rule.pattern}</span>'
            )

# 전역 인스턴스 (Import하여 사용)
color_manager = ColorManager()