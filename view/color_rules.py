"""
색상 규칙 관리
ReceivedArea에서 사용하는 패턴 매칭 색상 규칙을 관리합니다.
"""
from dataclasses import dataclass
from typing import List
import re
try:
    import commentjson as json
except ImportError:
    import json

@dataclass
class ColorRule:
    """단일 색상 규칙 데이터 클래스입니다."""
    name: str           # 규칙 이름 (예: "AT_OK")
    pattern: str        # 정규식 패턴 또는 문자열
    color: str          # HTML 색상 코드 (예: "#FF0000")
    is_regex: bool = True  # 정규식 사용 여부
    enabled: bool = True   # 규칙 활성화 여부

class ColorRulesManager:
    """
    색상 규칙 관리자 클래스입니다.
    패턴 매칭을 통해 텍스트에 색상을 입히는 규칙들을 관리합니다.
    """
    
    # 기본 규칙 (Implementation_Specification.md 섹션 11.3.1 기준)
    DEFAULT_RULES = [
        ColorRule("AT_OK", r'\bOK\b', '#4CAF50'),
        ColorRule("AT_ERROR", r'\bERROR\b', '#F44336'),
        ColorRule("URC", r'(\+\w+:)', '#FFEB3B'),
        ColorRule("PROMPT", r'^>', '#00BCD4'),
    ]
    
    def __init__(self) -> None:
        """
        ColorRulesManager를 초기화합니다.
        config/color_rules.json 파일이 있으면 로드하고, 없으면 기본 규칙을 생성하여 저장합니다.
        """
        self.rules: List[ColorRule] = []
        self.config_path = self._get_config_path()
        
        # 설정 파일 로드 시도, 실패 시 기본 규칙 사용
        if self.config_path.exists():
            self.load_from_json(str(self.config_path))
        else:
            self.rules = self.DEFAULT_RULES.copy()
            # 설정 디렉토리 생성 및 기본 규칙 저장
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_to_json(str(self.config_path))
    
    def _get_config_path(self) -> 'Path':
        """
        색상 규칙 설정 파일의 경로를 반환합니다.
        
        Returns:
            Path: config/color_rules.json 파일의 Path 객체.
        """
        from pathlib import Path
        import os
        
        # 애플리케이션 루트 디렉토리 확인
        if hasattr(os, '_MEIPASS'):
            # PyInstaller 번들 환경
            base_path = Path(os._MEIPASS)
        else:
            # 개발 모드 환경
            base_path = Path(__file__).parent.parent
        
        return base_path / 'config' / 'color_rules.json'
        
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
    
    def _apply_single_rule(self, text: str, rule: ColorRule) -> str:
        """
        단일 색상 규칙을 텍스트에 적용합니다.
        
        Args:
            text (str): 원본 텍스트.
            rule (ColorRule): 적용할 색상 규칙 객체.
            
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
        이름으로 색상 규칙을 제거합니다.
        
        Args:
            name (str): 제거할 규칙의 이름.
        """
        self.rules = [r for r in self.rules if r.name != name]
    
    def toggle_rule(self, name: str) -> None:
        """
        규칙의 활성화 상태를 토글합니다.
        
        Args:
            name (str): 토글할 규칙의 이름.
        """
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = not rule.enabled
                break
    
    def save_to_json(self, filepath: str) -> None:
        """
        현재 규칙들을 JSON 파일로 저장합니다.
        
        Args:
            filepath (str): 저장할 파일 경로.
        """
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
        
        # 구조 개선을 위해 color_rules 키로 래핑
        data = {'color_rules': rules_data}
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
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
            
            # 두 가지 형식 지원: 직접 배열 또는 "color_rules" 키로 래핑
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
            print(f"색상 규칙 로드 실패 ({filepath}): {e}")
            self.rules = self.DEFAULT_RULES.copy()
