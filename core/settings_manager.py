"""
설정 관리자 (Settings Manager)
애플리케이션 설정을 로드하고 저장합니다.
"""
try:
    import commentjson as json
except ImportError:
    import json
from pathlib import Path
from typing import Dict, Any, Optional
import os

class SettingsManager:
    """
    애플리케이션 설정 관리자 클래스입니다.
    config/settings.json에서 기본 설정을 로드하고, 사용자별 설정을 관리합니다.
    """
    
    def __init__(self):
        """SettingsManager를 초기화하고 설정을 로드합니다."""
        self.settings: Dict[str, Any] = {}
        self.config_path = self._get_config_path()
        self.user_settings_path = self._get_user_settings_path()
        
        # 설정 로드
        self.load_settings()
    
    def _get_config_path(self) -> Path:
        """
        기본 설정 파일의 경로를 반환합니다.
        
        Returns:
            Path: config/settings.json 파일의 Path 객체.
        """
        if hasattr(os, '_MEIPASS'):
            # PyInstaller 번들 환경
            base_path = Path(os._MEIPASS)
        else:
            # 개발 모드 환경
            base_path = Path(__file__).parent.parent
        
        return base_path / 'config' / 'settings.json'
    
    def _get_user_settings_path(self) -> Path:
        """
        사용자 설정 파일의 경로를 반환합니다.
        OS별 표준 사용자 데이터 디렉토리를 사용합니다.
        
        Returns:
            Path: 사용자 설정 파일(user_settings.json)의 Path 객체.
        """
        # OS별 사용자 설정 디렉토리 결정
        if os.name == 'nt':  # Windows
            settings_dir = Path(os.environ.get('APPDATA', '')) / 'SerialTool'
        else:  # Linux/Mac
            settings_dir = Path.home() / '.config' / 'serial_tool'
        
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / 'user_settings.json'
    
    def load_settings(self) -> None:
        """
        설정을 로드합니다.
        기본 설정을 먼저 로드한 후, 사용자 설정이 존재하면 덮어씁니다.
        """
        # 기본 설정 로드
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"기본 설정 로드 실패: {e}")
            self.settings = self._get_fallback_settings()
        
        # 사용자 설정이 있으면 병합
        if self.user_settings_path.exists():
            try:
                with open(self.user_settings_path, 'r', encoding='utf-8') as f:
                    user_settings = json.load(f)
                    self._merge_settings(user_settings)
            except json.JSONDecodeError as e:
                print(f"사용자 설정 로드 실패: {e}")
    
    def _merge_settings(self, user_settings: Dict[str, Any]) -> None:
        """
        사용자 설정을 기본 설정에 재귀적으로 병합합니다.
        
        Args:
            user_settings (Dict[str, Any]): 병합할 사용자 설정 딕셔너리.
        """
        def merge_dict(base: Dict, override: Dict) -> None:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
        
        merge_dict(self.settings, user_settings)
    
    def save_settings(self) -> None:
        """
        현재 설정을 사용자 설정 파일에 저장합니다.
        """
        try:
            with open(self.user_settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"설정 저장 실패: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 표기법을 사용하여 설정값을 가져옵니다.
        
        Args:
            key_path (str): 설정 키 경로 (예: 'ui.font_size').
            default (Any, optional): 키가 없을 경우 반환할 기본값. 기본값은 None.
            
        Returns:
            Any: 설정값 또는 기본값.
        """
        keys = key_path.split('.')
        value = self.settings
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        점(.) 표기법을 사용하여 설정값을 설정합니다.
        중간 경로의 키가 없으면 자동으로 생성합니다.
        
        Args:
            key_path (str): 설정 키 경로 (예: 'ui.font_size').
            value (Any): 저장할 값.
        """
        keys = key_path.split('.')
        current = self.settings
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        전체 설정 딕셔너리를 반환합니다.
        
        Returns:
            Dict[str, Any]: 전체 설정 딕셔너리.
        """
        return self.settings
    
    def _get_fallback_settings(self) -> Dict[str, Any]:
        """
        기본 설정 파일 로드 실패 시 사용할 최소 설정을 반환합니다.
        
        Returns:
            Dict[str, Any]: 최소 설정 딕셔너리.
        """
        return {
            "version": "1.0",
            "global": {
                "theme": "dark",
                "language": "ko"
            },
            "ui": {
                "log_max_lines": 2000,
                "proportional_font_family": "Segoe UI",
                "proportional_font_size": 9,
                "fixed_font_family": "Consolas",
                "fixed_font_size": 9
            },
            "ports": {
                "default_config": {
                    "baudrate": 115200,
                    "parity": "N",
                    "bytesize": 8,
                    "stopbits": 1
                }
            }
        }
