"""
설정 관리자 모듈

애플리케이션 설정을 로드하고 저장하는 중앙 관리 시스템입니다.

## WHY
* 사용자 설정의 영속화 (앱 재시작 후에도 유지)
* 설정 파일 손상 시 자동 복구 (Fallback)
* 점(.) 표기법으로 중첩된 설정 접근 편의성 제공
* 싱글톤 패턴으로 전역 일관성 보장

## WHAT
* JSON 기반 설정 파일 관리
* 점(.) 표기법 설정 접근 (예: 'ui.theme')
* 기본값(Fallback) 자동 생성
* ResourcePath를 통한 동적 경로 관리
* 주석 지원 JSON (commentjson) 파싱

## HOW
* 싱글톤 패턴으로 전역 인스턴스 제공
* commentjson으로 주석 포함 JSON 파싱
* 재귀적 딕셔너리 병합으로 설정 통합
* 파일 로드 실패 시 Fallback 설정 자동 생성
* ResourcePath로 개발/배포 환경 경로 자동 처리
"""
try:
    import commentjson as json
except ImportError:
    import json
from pathlib import Path
from typing import Dict, Any
from common.constants import DEFAULT_BAUDRATE, DEFAULT_LOG_MAX_LINES
from core.logger import logger
import os

class SettingsManager:
    """
    애플리케이션 설정 관리 (Singleton)
    설정 로드/저장 및 경로 관리
    """

    _instance = None
    _initialized = False
    _resource_path = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, resource_path=None):
        """
        SettingsManager를 초기화하고 설정을 로드합니다.

        Args:
            resource_path: ResourcePath 인스턴스. None이면 기본 경로 사용 (하위 호환성)
        """
        if self._initialized:
            return

        # ResourcePath 저장 (첫 초기화 시에만)
        if resource_path is not None:
            SettingsManager._resource_path = resource_path

        self.settings: Dict[str, Any] = {}
        # 프로퍼티를 통해 경로 접근
        self.config_path = self._get_config_path
        # 개발 모드에서는 설정 파일과 사용자 설정 파일이 동일
        self.user_settings_path = self._get_user_settings_path()

        # 설정 로드
        self.load_settings()
        self._initialized = True

    @property
    def _get_config_path(self) -> Path:
        """
        기본 설정 파일의 경로를 반환합니다.

        Returns:
            Path: config/settings.json 파일의 ResourcePath 객체.
        """
        if SettingsManager._resource_path is not None:
            # AppConfig가 제공되었으면 그것을 사용
            return SettingsManager._resource_path.settings_file
        else:
            # 하위 호환성: AppConfig가 없으면 기존 방식 사용
            if hasattr(os, '_MEIPASS'):
                # PyInstaller 번들 환경
                base_path = Path(os._MEIPASS)
            else:
                # 개발 모드 환경 (core/ -> project_root/)
                base_path = Path(__file__).parent.parent

            return base_path / 'config' / 'settings.json'

    def _get_user_settings_path(self) -> Path:
        """
        사용자 설정 파일의 경로를 반환합니다.
        (현재는 기본 설정 파일과 동일한 경로를 사용합니다)

        Returns:
            Path: 사용자 설정 파일의 ResourcePath 객체.
        """
        return self.config_path

    def load_settings(self) -> None:
        """
        설정을 로드합니다.
        파일이 없거나 손상된 경우 기본값(Fallback)을 사용하고 파일을 재생성합니다.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        except (FileNotFoundError, ValueError, Exception) as e:
            logger.error(f"설정 로드 실패: {e}")
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
            # 상위 디렉토리가 없으면 생성 (안전장치)
            if not self.config_path.parent.exists():
                self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"설정 저장 실패: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 표기법을 사용하여 설정값을 가져옵니다.

        Args:
            key_path (str): 설정 키 경로 (예: 'ui.theme').
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
        전체 설정 반환

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
                "rx_max_lines": DEFAULT_LOG_MAX_LINES,
                "proportional_font_family": "Segoe UI",
                "proportional_font_size": 9,
                "fixed_font_family": "Consolas",
                "fixed_font_size": 9
            },
            "ports": {
                "default_config": {
                    "baudrate": DEFAULT_BAUDRATE,
                    "parity": "N",
                    "bytesize": 8,
                    "stopbits": 1
                }
            }
        }
