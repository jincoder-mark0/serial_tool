"""
설정 관리자 모듈

애플리케이션 설정을 로드하고 저장하는 중앙 관리 시스템입니다.

## WHY
* 사용자 설정의 영속화 (앱 재시작 후에도 유지)
* 설정 파일 손상 시 자동 복구 (Fallback)
* 점(.) 표기법으로 중첩된 설정 접근 편의성 제공

## WHAT
* JSON 기반 설정 파일 관리 및 스키마 검증
* 점(.) 표기법 설정 접근 (예: 'ui.theme')
* 기본값(Fallback) 자동 생성 및 파일 복구
* ResourcePath를 통한 동적 경로 관리
* 설정 마이그레이션 로직 추가

## HOW
* 싱글톤 패턴으로 전역 인스턴스 제공
* commentjson으로 주석 포함 JSON 파싱
* jsonschema를 사용하여 데이터 구조 무결성 검증
"""
try:
    import commentjson as json
except ImportError:
    import json
import jsonschema
from jsonschema import validate, ValidationError
from pathlib import Path
from typing import Dict, Any
from common.constants import DEFAULT_BAUDRATE, DEFAULT_LOG_MAX_LINES
from core.settings_schema import CORE_SETTINGS_SCHEMA
from core.logger import logger
import os
from common.defaults import create_fallback_settings

class SettingsManager:
    """
    애플리케이션 설정 관리 (Singleton)
    설정 로드/저장, 경로 관리, 마이그레이션
    """

    _instance = None
    _initialized = False
    _resource_path = None

    # 현재 애플리케이션 설정 버전
    CURRENT_VERSION = "1.0"

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

        # 설정 초기화(Reset) 발생 여부 플래그
        self.config_was_reset = False
        self.reset_reason = ""

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

            return base_path / 'resources' / 'configs' / 'settings.json'

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
        설정을 로드하고 유효성을 검사합니다.
        파일이 없거나 손상되었거나 스키마가 일치하지 않는 경우
        기본값(Fallback)을 사용하고 파일을 복구합니다.
        """
        fallback_settings = self._get_fallback_settings()
        self.config_was_reset = False

        try:
            if not self.config_path.exists():
                raise FileNotFoundError("Settings file not found")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)

            # 마이그레이션 체크
            if self._needs_migration(loaded_settings):
                logger.info("Settings migration required.")
                loaded_settings = self._migrate_settings(loaded_settings)
                # 마이그레이션 후 저장
                self._save_to_file(loaded_settings)

            # JSON Schema 검증 (Optional: 스키마가 있다면)
            validate(instance=loaded_settings, schema=CORE_SETTINGS_SCHEMA)

            # 검증 성공 시 설정 적용 (기본값 위에 덮어쓰기하여 누락된 키 보완)
            self.settings = fallback_settings.copy()
            self._merge_settings(loaded_settings)

            logger.info("Settings loaded and validated successfully.")

        except (FileNotFoundError, ValueError) as e:
            # json.JSONDecodeError 대신 ValueError를 사용하여
            # commentjson 라이브러리 사용 시 발생하는 AttributeError 방지
            # (JSONDecodeError는 ValueError의 하위 클래스임)
            logger.warning(f"Settings load failed ({type(e).__name__}): {e}. Using fallback.")
            self.settings = fallback_settings
            self.save_settings() # 복구된 설정 저장

            # 리셋 플래그 설정
            self.config_was_reset = True
            self.reset_reason = f"Load failed: {str(e)}"

        except ValidationError as e:
            logger.error(f"Settings validation failed: {e.message}. Reverting to fallback.")
            # 스키마 불일치 시 Fallback 우선 사용
            self.settings = fallback_settings
            self._backup_corrupted_settings()
            self.save_settings()

            # 리셋 플래그 설정
            self.config_was_reset = True
            self.reset_reason = f"Validation failed: {e.message}"

        except Exception as e:
            logger.error(f"Unexpected error loading settings: {e}")
            self.settings = fallback_settings

            # 리셋 플래그 설정
            self.config_was_reset = True
            self.reset_reason = f"Unexpected error: {str(e)}"

    def _needs_migration(self, settings: Dict[str, Any]) -> bool:
        """
        마이그레이션 필요 여부를 확인합니다.

        Args:
            settings: 로드된 설정 딕셔너리

        Returns:
            bool: 마이그레이션이 필요하면 True
        """
        version = settings.get("version", "0.0")
        return version != self.CURRENT_VERSION

    def _migrate_settings(self, old_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        구버전 설정을 신버전 형식으로 변환합니다.

        Args:
            old_settings: 구버전 설정 데이터

        Returns:
            Dict[str, Any]: 마이그레이션된 설정 데이터
        """
        migrated = old_settings.copy()
        current_ver = old_settings.get("version", "0.0")

        logger.info(f"Migrating settings from version {current_ver} to {self.CURRENT_VERSION}")

        # 예시: 0.9 -> 1.0 마이그레이션 로직
        # if current_ver == "0.9":
        #     # 변경된 키 매핑이나 구조 변경 처리
        #     if "old_key" in migrated:
        #         migrated["new_key"] = migrated.pop("old_key")
        #     current_ver = "1.0"

        # 최종 버전 업데이트
        migrated["version"] = self.CURRENT_VERSION
        return migrated

    def _merge_settings(self, user_settings: Dict[str, Any]) -> None:
        """
        사용자 설정을 기본 설정에 재귀적으로 병합
        Args:
            user_settings: 사용자 설정 딕셔너리
        """
        def merge_dict(base: Dict, override: Dict) -> None:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value

            # base에 없는 키도 override에 있다면 추가 (확장성)
            for key, value in override.items():
                if key not in base:
                    base[key] = value

        merge_dict(self.settings, user_settings)

    def _backup_corrupted_settings(self) -> None:
        """
        손상된 설정 파일을 백업
        """
        backup_path = self.config_path.with_suffix('.json.bak')
        try:
            if self.config_path.exists():
                self.config_path.rename(backup_path)
                logger.info(f"Corrupted settings backed up to {backup_path}")
        except OSError:
            pass

    def _save_to_file(self, data: Dict[str, Any]) -> None:
        """
        데이터를 설정 파일에 저장
        Args:
            data: 저장할 설정 딕셔너리
        """
        if not self.config_path.parent.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_settings(self) -> None:
        """
        현재 설정을 파일에 저장
        """
        try:
            self._save_to_file(self.settings)
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
        기본 설정값을 반환합니다.
        실제 데이터는 common/defaults.py에서 관리합니다.
        """
        return create_fallback_settings()