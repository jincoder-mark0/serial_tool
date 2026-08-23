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
    # commentjson은 파싱 실패를 **자체 예외**(JSONLibraryException)로 감싼다.
    # 이것은 ValueError의 하위 클래스가 아니다 — 그래서 "저장 중 잘린 파일"이
    # ValueError 갈래가 아니라 맨 끝 `except Exception`으로 떨어져, 백업도
    # 복구 저장도 없이 조용히 기본값으로 초기화됐다 (S-081, 실측 확인).
    _PARSE_ERRORS = (ValueError, json.JSONLibraryException)
except ImportError:
    import json
    _PARSE_ERRORS = (ValueError,)
import os
from jsonschema import validate, ValidationError
from pathlib import Path
from typing import Dict, Any, Optional

from core.settings_schema import CORE_SETTINGS_SCHEMA
from core.logger import logger
from common.defaults import create_fallback_settings
from core.resource_path import ResourcePath

class SettingsManager:
    """
    애플리케이션 설정 관리 (Singleton)
    설정 로드/저장, 경로 관리, 마이그레이션
    """

    _instance = None
    _initialized = False
    _resource_path = None

    # 현재 애플리케이션 설정 버전
    CURRENT_VERSION = "1.3"

    def __new__(cls, *args, **kwargs):
        """
        Singleton 인스턴스 보장 및 초기화 플래그 설정
        """
        if not cls._instance:
            # QObject 상속 시 super().__new__에는 인자를 전달하지 않는 것이 안전함
            cls._instance = super(SettingsManager, cls).__new__(cls)
            # 인스턴스 생성 직후 플래그 초기화
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path: Optional[ResourcePath] = None):
        """
        SettingsManager를 초기화하고 설정을 로드합니다.

        Args:
            resource_path: ResourcePath 인스턴스. None이면 내부에서 생성.
        """
        # ResourcePath 설정 (주입받거나 없으면 생성)
        if resource_path is None:
            resource_path = ResourcePath()

        # 싱글톤 중복 초기화 방지
        if hasattr(self, '_initialized') and self._initialized:
            # 이미 초기화되었더라도, 새로운 resource_path가 들어오면 업데이트
            if resource_path is not None:
                self._resource_path = resource_path
            return

        # QObject 초기화 (가장 먼저 호출해야 함)
        super().__init__()

        self._resource_path = resource_path


        self.settings: Dict[str, Any] = {}
        # 프로퍼티를 통해 경로 접근
        self.config_path = self._get_config_path()
        # S-043: 개발 모드도 settings.local.json으로 분리(배포 기본값 원본 보호)
        self.user_settings_path = self._get_user_settings_path()

        # 설정 초기화(Reset) 발생 여부 플래그
        self.config_was_reset = False
        self.reset_reason = ""

        # 설정 로드
        self.load_settings()

        # 초기화 완료 플래그 설정
        self._initialized = True

    def _get_config_path(self) -> Path:
        """
        기본 설정 파일의 경로를 반환합니다.

        Returns:
            Path: resources/configs/settings.json 파일의 ResourcePath 객체.
        """
        return self._resource_path.settings_file

    def _get_user_settings_path(self) -> Path:
        """
        사용자 설정 파일의 경로를 반환합니다.
        번들 실행 시에는 APPDATA 하위(쓰기 가능) 경로, 개발 모드에서는
        기본 설정 파일과 같은 디렉터리의 settings.local.json입니다
        (S-043 — 배포 기본값 원본과 분리. ResourcePath.user_settings_file 참고).

        Returns:
            Path: 사용자 설정 파일 경로.
        """
        return self._resource_path.user_settings_file

    def load_settings(self) -> None:
        """
        설정을 로드하고 유효성을 검사합니다.
        사용자 설정 파일(user_settings_path)이 있으면 그것을 우선 로드하고,
        없으면 기본 배포본(config_path, resources/configs/settings.json)을
        읽습니다. 개발 모드에서도 사용자 파일은 settings.local.json으로
        분리되어 있으므로(S-043), 첫 실행 시 기본 배포본에서 자연 이관됩니다.
        파일이 없거나 손상되었거나 스키마가 일치하지 않는 경우
        기본값(Fallback)을 사용하고 파일을 복구합니다.
        """
        fallback_settings = self._get_fallback_settings()
        self.config_was_reset = False

        # 사용자 설정 파일 우선, 없으면 기본 배포본에서 읽는다.
        loaded_from_default_distribution = not self.user_settings_path.exists()
        read_path = self.user_settings_path if not loaded_from_default_distribution else self.config_path

        try:
            if not read_path.exists():
                raise FileNotFoundError("Settings file not found")

            with open(read_path, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)

            # 마이그레이션 체크
            if self._needs_migration(loaded_settings):
                logger.info("Settings migration required.")
                loaded_settings = self._migrate_settings(loaded_settings)
                # 마이그레이션 후 저장 (항상 사용자 경로에)
                self._save_to_file(loaded_settings)

            # JSON Schema 검증 (Optional: 스키마가 있다면)
            validate(instance=loaded_settings, schema=CORE_SETTINGS_SCHEMA)

            # 검증 성공 시 설정 적용 (기본값 위에 덮어쓰기하여 누락된 키 보완)
            self.settings = fallback_settings.copy()
            self._merge_settings(loaded_settings)

            # 기본 배포본에서 처음 읽은 경우(사용자 파일 부재), 사용자 경로로 이관 저장
            if loaded_from_default_distribution:
                self._save_to_file(self.settings)

            logger.info("Settings loaded and validated successfully.")

        except (FileNotFoundError, *_PARSE_ERRORS) as e:
            # 파싱 실패는 라이브러리마다 예외 타입이 다르다 — 표준 json은
            # JSONDecodeError(ValueError 하위), commentjson은 자체
            # JSONLibraryException(ValueError와 무관)을 던진다. 둘 다 여기서
            # 받아야 손상된 파일이 백업되고 복구 저장까지 이어진다 (S-081).
            logger.warning(f"Settings load failed ({type(e).__name__}): {e}. Using fallback.")
            self.settings = fallback_settings
            # 읽지 못한 파일도 백업해 둔다 (S-081).
            # 예전에는 스키마 검증 실패 갈래에만 백업이 있었다. 정작 흔한 손상은
            # "저장 중 중단되어 잘린 파일"인데, 그건 파싱에서 걸려 이 갈래로 오므로
            # 사용자 설정이 흔적 없이 사라졌다. 손으로라도 건질 여지를 남긴다.
            self._backup_corrupted_settings(read_path)
            self.save_settings() # 복구된 설정 저장 (사용자 경로)

            # 리셋 플래그 설정
            self.config_was_reset = True
            self.reset_reason = f"Load failed: {str(e)}"

        except ValidationError as e:
            logger.error(f"Settings validation failed: {e.message}. Reverting to fallback.")
            # 스키마 불일치 시 Fallback 우선 사용
            self.settings = fallback_settings
            self._backup_corrupted_settings(read_path)
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

        # 1. Serial Migration
        if "serial" in migrated:
            serial = migrated["serial"]
            if "scan_interval" in serial:
                val = serial.pop("scan_interval")
                if "scan_interval_ms" not in serial:
                    serial["scan_interval_ms"] = val
                    logger.info(f"Migrated setting: scan_interval -> scan_interval_ms ({val})")

        # 2. UI Migration
        if "ui" in migrated:
            ui = migrated["ui"]
            if "rx_max_lines" in ui:
                val = ui.pop("rx_max_lines")
                if "max_log_lines" not in ui:
                    ui["max_log_lines"] = val
                    logger.info(f"Migrated setting: rx_max_lines -> max_log_lines ({val})")

        # 3. Logging Migration
        if "logging" in migrated:
            log = migrated["logging"]
            if "log_path" in log:
                val = log.pop("log_path")
                if "log_dir" not in log:
                    log["log_dir"] = val
                    logger.info(f"Migrated setting: log_path -> log_dir ({val})")

        # 4. Global -> Settings 네임스페이스 이관 (S-027, 1.0 -> 1.1)
        # 정본은 settings.*(코드 실태 기준) — global은 죽은 블록이므로 제거하되,
        # settings.*에 이미 실사용 값이 있으면 그 값을 우선한다.
        if "global" in migrated:
            global_block = migrated.pop("global")
            if isinstance(global_block, dict):
                settings_block = migrated.setdefault("settings", {})
                for key in ("theme", "language"):
                    if key in global_block and key not in settings_block:
                        settings_block[key] = global_block[key]
                        logger.info(f"Migrated setting: global.{key} -> settings.{key} ({global_block[key]})")

        # 5. UI 블록의 죽은 폰트 키 제거 (실사용은 settings.* 쪽 — S-027)
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

        # 6. 우측 폭 저장 키 이중화 해소 (S-028, 1.1 -> 1.2)
        # 정본은 ui.saved_right_section_width(코드 실태 기준) — 과거 1.0->1.1 리네임 매핑이
        # 실사용 키를 지우고 런타임(main_presenter/lifecycle_manager)이 그 키를 다시 만들어
        # 두 키가 공존했다. 잔존 right_section_width는 saved_right_section_width가
        # 비어 있을 때만 값을 이어받은 뒤 제거한다(과거 이관으로 값이 옮겨간 사용자 폭 보전).
        if "ui" in migrated:
            ui = migrated["ui"]
            if "right_section_width" in ui:
                val = ui.pop("right_section_width")
                if ui.get("saved_right_section_width") is None:
                    ui["saved_right_section_width"] = val
                    logger.info(
                        f"Migrated setting: right_section_width -> saved_right_section_width ({val})"
                    )
                else:
                    logger.info(
                        f"Removed stale ui setting: right_section_width "
                        f"(value {val} discarded; saved_right_section_width already set)"
                    )

        # 7. 루트 serial 블록 제거 (S-030, 1.2 -> 1.3)
        # 최상위 settings.json["serial"](baudrate/parity/.../flowctrl 등)는 어떤 코드도
        # 읽지 않는 고아 블록이다(실사용은 settings.port_* / PortConfig 쪽 — S-030 조사).
        # ports.tabs[*].serial(탭별 실사용 상태, port_settings.py get_state/apply_state)은
        # 완전히 다른 데이터 경로이므로 절대 건드리지 않는다 — 여기서 pop하는 것은
        # 최상위 "serial" 키 하나뿐이다.
        if "serial" in migrated:
            removed = migrated.pop("serial")
            logger.info(f"Removed orphan top-level 'serial' block: {removed}")

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

    def _backup_corrupted_settings(self, source_path: Optional[Path] = None) -> None:
        """
        손상된 설정 파일을 백업

        Args:
            source_path: 손상이 감지된 원본 파일 경로. None이면 사용자 설정 경로.
        """
        target_path = source_path if source_path is not None else self.user_settings_path
        backup_path = target_path.with_suffix('.json.bak')
        try:
            if target_path.exists():
                target_path.rename(backup_path)
                logger.info(f"Corrupted settings backed up to {backup_path}")
        except OSError:
            pass

    def _save_to_file(self, data: Dict[str, Any]) -> None:
        """
        데이터를 사용자 설정 파일에 저장합니다.
        항상 user_settings_path에 씁니다 — 기본 배포본
        (resources/configs/settings.json)은 원본 그대로 보존됩니다
        (개발 모드에서도 settings.local.json으로 분리되어 있어 S-043 이후
        동일하게 성립합니다).

        Args:
            data: 저장할 설정 딕셔너리
        """
        if not self.user_settings_path.parent.exists():
            self.user_settings_path.parent.mkdir(parents=True, exist_ok=True)

        # 임시 파일에 다 쓴 뒤 한 번에 갈아 끼운다 (S-081).
        # 대상 파일에 직접 쓰면, 쓰는 도중 전원이 나가거나 디스크가 차는 순간
        # 설정이 반쪽짜리로 남는다. 실측했더니 그 파일로 재기동하면 파싱에
        # 실패해 기본값으로 되돌아갔다 — 매크로도 포트 탭 구성도 사라졌다.
        # os.replace는 같은 볼륨에서 원자적이므로, 실패해도 이전 파일이 온전히 남는다.
        temp_path = self.user_settings_path.with_suffix('.json.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                # 디스크까지 내려간 것을 확인하고 나서 갈아 끼운다.
                # flush만으로는 OS 버퍼에 남아 있어, 여기서 전원이 나가면
                # 내용이 빈 새 파일이 원본을 대체할 수 있다.
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.user_settings_path)
        except Exception:
            # 갈아 끼우기 전에 실패했다면 원본은 그대로다. 찌꺼기만 지운다.
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

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
