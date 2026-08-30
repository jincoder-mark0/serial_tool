"""
설정 관리자 모듈

애플리케이션 설정을 로드하고 저장하는 중앙 관리 시스템입니다.

## WHY
* 사용자 설정의 영속화 (앱 재시작 후에도 유지)
* 설정 파일 손상 시 자동 복구 (Fallback)
* 점(.) 표기법으로 중첩된 설정 접근 편의성 제공
* 전역 Singleton 대신 Composition Root가 명시적으로 생성/주입하는 instance 사용

## WHAT
* JSON 기반 설정 파일 관리 및 스키마 검증
* 점(.) 표기법 설정 접근 (예: 'ui.theme')
* 기본값(Fallback) 자동 생성 및 파일 복구
* ResourcePath를 통한 동적 경로 관리
* 설정 마이그레이션

## HOW
* main.py가 SettingsManager instance를 생성하고 ApplicationBootstrapper에 주입
* commentjson으로 주석 포함 JSON 파싱
* jsonschema를 사용하여 데이터 구조 무결성 검증
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import commentjson as json

    # commentjson은 파싱 실패를 자체 예외(JSONLibraryException)로 감싼다.
    # ValueError와 별개이므로 두 예외를 모두 복구 경로에서 처리해야 한다.
    _PARSE_ERRORS = (ValueError, json.JSONLibraryException)
except ImportError:
    import json

    _PARSE_ERRORS = (ValueError,)

from jsonschema import ValidationError, validate

from common.defaults import create_fallback_settings
from core.logger import logger
from core.resource_path import ResourcePath
from core.settings_schema import CORE_SETTINGS_SCHEMA


class SettingsManager:
    """설정 로드/저장, 경로 관리, 마이그레이션을 담당하는 일반 instance 객체.

    WHY:
        과거 Singleton 구현은 ``SettingsManager()`` 호출 위치가 곧 hidden global
        dependency가 되게 만들었다. 현재 runtime은 ``main.py``에서 한 번 생성한
        instance를 Composition Root에 전달하므로 Singleton이 필요하지 않다.

    HOW:
        각 생성 호출은 독립 instance를 만든다. 같은 runtime graph에서 공유가
        필요하면 constructor injection으로 동일 instance를 전달한다.
    """

    CURRENT_VERSION = "1.3"

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """SettingsManager를 초기화하고 설정을 로드한다.

        Args:
            resource_path: ResourcePath instance. None이면 기본 ResourcePath 생성.
        """
        self._resource_path = resource_path or ResourcePath()
        self.settings: Dict[str, Any] = {}

        # 배포 기본값 파일과 사용자 쓰기 파일은 분리한다.
        self.config_path = self._get_config_path()
        self.user_settings_path = self._get_user_settings_path()

        self.config_was_reset = False
        self.reset_reason = ""
        self.load_settings()

    def _get_config_path(self) -> Path:
        """배포 기본 설정 파일 경로를 반환한다."""
        return self._resource_path.settings_file

    def _get_user_settings_path(self) -> Path:
        """사용자 쓰기 설정 파일 경로를 반환한다.

        번들 실행 시 APPDATA 하위, 개발 모드에서는 배포 설정과 같은 디렉터리의
        ``settings.local.json``을 사용한다.
        """
        return self._resource_path.user_settings_file

    def load_settings(self) -> None:
        """설정을 로드하고 검증하며 필요 시 복구/마이그레이션한다."""
        fallback_settings = self._get_fallback_settings()
        self.config_was_reset = False
        self.reset_reason = ""

        # 사용자 파일이 없을 때만 배포 기본본을 읽고, 정상 로드 후 사용자 경로로 이관한다.
        loaded_from_default_distribution = not self.user_settings_path.exists()
        read_path = (
            self.config_path
            if loaded_from_default_distribution
            else self.user_settings_path
        )

        try:
            if not read_path.exists():
                raise FileNotFoundError("Settings file not found")

            with open(read_path, "r", encoding="utf-8") as file:
                loaded_settings = json.load(file)

            if self._needs_migration(loaded_settings):
                logger.info("Settings migration required.")
                loaded_settings = self._migrate_settings(loaded_settings)
                self._save_to_file(loaded_settings)

            validate(instance=loaded_settings, schema=CORE_SETTINGS_SCHEMA)

            # Fallback을 먼저 채운 뒤 사용자 값을 재귀 병합하여 누락 key를 보완한다.
            self.settings = fallback_settings.copy()
            self._merge_settings(loaded_settings)

            if loaded_from_default_distribution:
                self._save_to_file(self.settings)

            logger.info("Settings loaded and validated successfully.")

        except (FileNotFoundError, *_PARSE_ERRORS) as exc:
            logger.warning(
                f"Settings load failed ({type(exc).__name__}): {exc}. Using fallback."
            )
            self.settings = fallback_settings
            self._backup_corrupted_settings(read_path)
            self.save_settings()
            self.config_was_reset = True
            self.reset_reason = f"Load failed: {exc}"

        except ValidationError as exc:
            logger.error(
                f"Settings validation failed: {exc.message}. Reverting to fallback."
            )
            self.settings = fallback_settings
            self._backup_corrupted_settings(read_path)
            self.save_settings()
            self.config_was_reset = True
            self.reset_reason = f"Validation failed: {exc.message}"

        except Exception as exc:
            logger.error(f"Unexpected error loading settings: {exc}")
            self.settings = fallback_settings
            self.config_was_reset = True
            self.reset_reason = f"Unexpected error: {exc}"

    def _needs_migration(self, settings: Dict[str, Any]) -> bool:
        """설정 version이 현재 version과 다른지 반환한다."""
        return settings.get("version", "0.0") != self.CURRENT_VERSION

    def _migrate_settings(self, old_settings: Dict[str, Any]) -> Dict[str, Any]:
        """과거 설정 schema를 현재 version으로 변환한다."""
        migrated = old_settings.copy()
        current_ver = old_settings.get("version", "0.0")
        logger.info(
            f"Migrating settings from version {current_ver} to {self.CURRENT_VERSION}"
        )

        # 1. Serial Migration
        if "serial" in migrated:
            serial = migrated["serial"]
            if "scan_interval" in serial:
                value = serial.pop("scan_interval")
                if "scan_interval_ms" not in serial:
                    serial["scan_interval_ms"] = value
                    logger.info(
                        f"Migrated setting: scan_interval -> scan_interval_ms ({value})"
                    )

        # 2. UI Migration
        if "ui" in migrated:
            ui = migrated["ui"]
            if "rx_max_lines" in ui:
                value = ui.pop("rx_max_lines")
                if "max_log_lines" not in ui:
                    ui["max_log_lines"] = value
                    logger.info(
                        f"Migrated setting: rx_max_lines -> max_log_lines ({value})"
                    )

        # 3. Logging Migration
        if "logging" in migrated:
            log = migrated["logging"]
            if "log_path" in log:
                value = log.pop("log_path")
                if "log_dir" not in log:
                    log["log_dir"] = value
                    logger.info(
                        f"Migrated setting: log_path -> log_dir ({value})"
                    )

        # 4. global.* -> settings.* 이관. 이미 settings.*가 있으면 실사용 값을 우선한다.
        if "global" in migrated:
            global_block = migrated.pop("global")
            if isinstance(global_block, dict):
                settings_block = migrated.setdefault("settings", {})
                for key in ("theme", "language"):
                    if key in global_block and key not in settings_block:
                        settings_block[key] = global_block[key]
                        logger.info(
                            f"Migrated setting: global.{key} -> settings.{key} "
                            f"({global_block[key]})"
                        )

        # 5. 과거 ui.* 폰트 key는 현재 settings.*가 정본이므로 제거한다.
        if "ui" in migrated:
            ui = migrated["ui"]
            for dead_key in (
                "proportional_font_family",
                "proportional_font_size",
                "fixed_font_family",
                "fixed_font_size",
            ):
                if dead_key in ui:
                    ui.pop(dead_key)
                    logger.info(f"Removed dead ui setting: {dead_key}")

        # 6. right_section_width -> saved_right_section_width 정본화.
        if "ui" in migrated:
            ui = migrated["ui"]
            if "right_section_width" in ui:
                value = ui.pop("right_section_width")
                if ui.get("saved_right_section_width") is None:
                    ui["saved_right_section_width"] = value
                    logger.info(
                        "Migrated setting: right_section_width -> "
                        f"saved_right_section_width ({value})"
                    )
                else:
                    logger.info(
                        "Removed stale ui setting: right_section_width "
                        f"(value {value} discarded; saved_right_section_width already set)"
                    )

        # 7. 최상위 serial block은 현재 코드가 읽지 않는 orphan 데이터다.
        # ports.tabs[*].serial은 별도 경로이므로 이 pop의 대상이 아니다.
        if "serial" in migrated:
            removed = migrated.pop("serial")
            logger.info(f"Removed orphan top-level 'serial' block: {removed}")

        migrated["version"] = self.CURRENT_VERSION
        return migrated

    def _merge_settings(self, user_settings: Dict[str, Any]) -> None:
        """사용자 설정을 fallback 설정 위에 재귀적으로 병합한다."""

        def merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> None:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value

            # 기존 구현과 동일하게 base에 없던 확장 key도 보존한다.
            for key, value in override.items():
                if key not in base:
                    base[key] = value

        merge_dict(self.settings, user_settings)

    def _backup_corrupted_settings(
        self,
        source_path: Optional[Path] = None,
    ) -> None:
        """손상이 감지된 설정 파일을 ``.json.bak``으로 보존한다."""
        target_path = source_path or self.user_settings_path
        backup_path = target_path.with_suffix(".json.bak")
        try:
            if target_path.exists():
                target_path.rename(backup_path)
                logger.info(f"Corrupted settings backed up to {backup_path}")
        except OSError:
            # Backup 실패가 fallback 적용 자체를 막으면 안 된다.
            pass

    def _save_to_file(self, data: Dict[str, Any]) -> None:
        """설정을 사용자 경로에 atomic replace 방식으로 저장한다."""
        if not self.user_settings_path.parent.exists():
            self.user_settings_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = self.user_settings_path.with_suffix(".json.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, self.user_settings_path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def save_settings(self) -> None:
        """현재 설정을 사용자 설정 파일에 저장한다."""
        try:
            self._save_to_file(self.settings)
        except IOError as exc:
            logger.error(f"설정 저장 실패: {exc}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """점(.) 경로로 설정값을 읽는다."""
        value: Any = self.settings
        for key in key_path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, key_path: str, value: Any) -> None:
        """점(.) 경로로 설정값을 기록하며 없는 중간 dict를 생성한다."""
        keys = key_path.split(".")
        current = self.settings

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def get_all_settings(self) -> Dict[str, Any]:
        """현재 전체 설정 dict를 반환한다."""
        return self.settings

    @staticmethod
    def _get_fallback_settings() -> Dict[str, Any]:
        """common/defaults.py의 canonical fallback을 반환한다."""
        return create_fallback_settings()
