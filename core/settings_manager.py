"""
설정 관리자 (Settings Manager)
애플리케이션 설정을 로드하고 저장합니다.
"""
try:
    import commentjson as json
except ImportError:
    import json
from pathlib import Path
from typing import Dict, Any

class SettingsManager:
    """
    애플리케이션 설정 관리자 클래스입니다.
    AppConfig에서 제공하는 경로를 사용하여 설정을 로드하고 관리합니다.
    """

    _instance = None
    _initialized = False
    _app_config = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, app_config=None):
        """
        SettingsManager를 초기화하고 설정을 로드합니다.

        Args:
            app_config: AppConfig 인스턴스. None이면 기본 경로 사용 (하위 호환성)
        """
        if self._initialized:
            return

        # AppConfig 저장 (첫 초기화 시에만)
        if app_config is not None:
            SettingsManager._app_config = app_config

        self.settings: Dict[str, Any] = {}
        self.config_path = self._get_config_path
        self.user_settings_path = self._get_user_settings_path()

        # 설정 로드
        self.load_settings()
        self._initialized = True

    @property
    def _get_config_path(self) -> Path:
        """
        기본 설정 파일의 경로를 반환합니다.

        Returns:
            Path: config/settings.json 파일의 Path 객체.
        """
        if SettingsManager._app_config is not None:
            # AppConfig가 제공되었으면 그것을 사용
            return SettingsManager._app_config.settings_file
        else:
            # 하위 호환성: AppConfig가 없으면 기존 방식 사용
            import os
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
        개발 모드에서는 config/settings.json을 직접 사용합니다.

        Returns:
            Path: 사용자 설정 파일의 Path 객체.
        """
        # 개발 모드: config/settings.json을 직접 사용
        return self.config_path

    def load_settings(self) -> None:
        """
        설정을 로드합니다.
        config/settings.json 파일을 읽어옵니다.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        except (FileNotFoundError, ValueError, Exception) as e:
            print(f"설정 로드 실패: {e}")
            self.settings = self._get_fallback_settings()
            # 기본 설정으로 파일 생성
            self.save_settings()


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
        현재 설정을 config/settings.json 파일에 저장합니다.
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"설정 저장 실패: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 표기법을 사용하여 설정값을 가져옵니다.

        Args:
            key_path (str): 설정 키 경로 (예: 'settings.proportional_font_size').
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
            key_path (str): 설정 키 경로 (예: 'settings.proportional_font_size').
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

    @staticmethod
    def _get_fallback_settings() -> Dict[str, Any]:
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
                "rx_max_lines": 2000,
                "proportional_font_family": "Segoe UI",
                "proportional_font_size": 9,
                "fixed_font_family": "Consolas",
                "fixed_font_size": 9
            },
            "ports": {
                "default_config": {
                    "baudrate": 115200,
                    "parity": "N",
                    "datasize": 8,
                    "stopbits": 1
                }
            }
        }
