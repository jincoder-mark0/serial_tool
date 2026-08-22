"""
리소스 경로 관리 모듈

애플리케이션의 모든 리소스 경로를 중앙에서 관리합니다.

## WHY
* 개발/배포 환경 경로 차이 자동 처리
* PyInstaller 번들 환경 지원
* 경로 검증으로 누락된 리소스 조기 발견

## WHAT
* 프로젝트 루트 디렉토리 자동 감지
* 설정 파일 경로 (settings.json)
* 언어 파일 경로 (en.json, ko.json)
* 테마 파일 경로 (QSS)
* 아이콘 경로
* 로그 디렉토리 경로
* 경로 검증 기능

## HOW
* PyInstaller _MEIPASS 속성으로 번들 환경 감지
* pathlib.Path로 플랫폼 독립적 경로 처리
* Dictionary로 언어/테마 파일 매핑
* validate_paths()로 경로 존재 여부 확인
"""
import os
import sys
from pathlib import Path
from typing import Dict


class ResourcePath:
    """애플리케이션 리소스 경로 관리자"""

    def __init__(self, base_dir: Path = None):
        """
        ResourcePath 초기화

        Logic:
            - PyInstaller 번들 환경 감지 (_MEIPASS)
            - 개발 모드: 현재 파일 위치 기준 루트 설정
            - 모든 리소스 경로 초기화

        Args:
            base_dir: 프로젝트 루트 디렉토리. None이면 자동 감지
        """
        # 프로젝트 루트 디렉토리 설정
        if base_dir is None:
            if hasattr(sys, '_MEIPASS'):
                # PyInstaller 번들 환경
                self.base_dir = Path(sys._MEIPASS)
            else:
                # 개발 모드: resource_path.py가 있는 디렉토리가 루트
                self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = Path(base_dir)

        # 리소스 경로 설정
        self.resources_dir = self.base_dir / 'resources'

        # 설정 파일 경로
        self.config_dir = self.resources_dir / 'configs'
        self.settings_file = self.config_dir / 'settings.json'
        self.color_rules_file = self.config_dir / 'color_rules.json'

        # 언어 파일 경로
        self.languages_dir = self.resources_dir / 'languages'
        self.language_files: Dict[str, Path] = {
            'en': self.languages_dir / 'en.json',
            'ko': self.languages_dir / 'ko.json'
        }

        # 테마 파일 경로
        self.themes_dir = self.resources_dir / 'themes'
        self.theme_files: Dict[str, Path] = {
            'common': self.themes_dir / 'common.qss',
            'dark': self.themes_dir / 'dark_theme.qss',
            'light': self.themes_dir / 'light_theme.qss',
            'dracula': self.themes_dir / 'dracula_theme.qss',
            'classic': self.themes_dir / 'classic_theme.qss'
        }

        # 아이콘 경로
        self.icons_dir = self.resources_dir / 'icons'

    @property
    def logs_dir(self) -> Path:
        """
        로그 파일을 저장할 디렉터리 경로를 반환합니다.

        Logic:
            - 번들 실행(PyInstaller frozen) 시: base_dir(sys._MEIPASS, onedir에서는
              `_internal\\`)가 읽기 전용 설치 폴더일 수 있으므로, user_config_dir와
              동일한 사용자 데이터 경로(APPDATA) 하위 'logs'를 사용한다.
            - 개발 모드: 기존 동작 그대로 base_dir 하위 'logs' (회귀 방지 — 불변).

        Returns:
            Path: 로그 디렉터리 경로.
        """
        if getattr(sys, 'frozen', False):
            return self.user_config_dir / 'logs'
        return self.base_dir / 'logs'

    @property
    def user_config_dir(self) -> Path:
        """
        사용자별 설정을 저장할 디렉터리 경로를 반환합니다.

        Logic:
            - 번들 실행(PyInstaller frozen) 시: 설치 폴더가 읽기 전용일 수 있으므로
              Windows 표준 사용자 데이터 경로(APPDATA)를 사용한다.
              APPDATA 환경변수가 없으면 홈 디렉터리 하위 폴더로 폴백한다.
            - 개발 모드: 기존 설정 파일이 위치한 디렉터리를 그대로 반환한다
              (현행 동작·테스트 완전 불변 — settings_file 경로가 재정의되어도 추종).
            - 디렉터리가 없으면 생성하여 보장한다.

        Returns:
            Path: 사용자 설정 파일을 저장할 디렉터리.
        """
        if getattr(sys, 'frozen', False):
            appdata = os.environ.get('APPDATA')
            if appdata:
                directory = Path(appdata) / 'SerialTool'
            else:
                directory = Path.home() / '.serial_tool'
        else:
            directory = self.settings_file.parent

        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @property
    def user_settings_file(self) -> Path:
        """
        사용자 설정 파일(settings.json)의 전체 경로를 반환합니다.

        Logic:
            - 번들 실행: user_config_dir(APPDATA) 하위 settings.json.
            - 개발 모드: settings_file과 같은 디렉터리의 settings.local.json
              (S-043 — 배포 기본값 원본(settings_file)에 앱이 직접 쓰던 것을
              분리해 개발자 로컬 세션이 커밋에 섞여 들어가는 오염을 차단한다.
              settings_file이 재정의되어도 그 디렉터리를 추종하도록
              config_dir가 아닌 settings_file.parent를 기준으로 삼는다).

        Returns:
            Path: 사용자 설정 파일 경로.
        """
        if getattr(sys, 'frozen', False):
            return self.user_config_dir / 'settings.json'
        return self.settings_file.parent / 'settings.local.json'

    def get_language_path(self, language_code: str) -> Path:
        """
        언어 코드에 해당하는 언어 파일 경로 반환

        Args:
            language_code: 언어 코드 (예: 'en', 'ko')

        Returns:
            Path: 언어 파일 경로 (없으면 영어 기본값)
        """
        return self.language_files.get(language_code, self.language_files['en'])

    def get_theme_path(self, theme_name: str) -> Path:
        """
        테마 이름에 해당하는 테마 파일 경로 반환

        Args:
            theme_name: 테마 이름 (예: 'dark', 'light', 'common')

        Returns:
            Path: 테마 파일 경로
        """
        return self.theme_files.get(theme_name)

    def get_icon_path(self, icon_name: str, theme: str = None) -> Path:
        """
        아이콘 파일 경로 반환

        Args:
            icon_name: 아이콘 이름 (예: 'add', 'delete')
            theme: 테마 이름 (예: 'dark', 'light'). None이면 루트에서 찾음

        Returns:
            Path: 아이콘 파일 경로
        """
        if theme:
            return self.icons_dir / theme / f"{icon_name}_{theme}.svg"

        return self.icons_dir / f"{icon_name}.svg"

    def validate_paths(self) -> Dict[str, bool]:
        """
        주요 경로들이 존재하는지 검증

        Returns:
            Dict[str, bool]: 경로별 존재 여부
        """
        return {
            'config_dir': self.config_dir.exists(),
            'resources_dir': self.resources_dir.exists(),
            'settings_file': self.settings_file.exists(),
            'color_rules_file': self.color_rules_file.exists(),
            'languages_dir': self.languages_dir.exists(),
            'themes_dir': self.themes_dir.exists(),
            'icons_dir': self.icons_dir.exists(),
            'logs_dir': self.logs_dir.exists()
        }

    def __repr__(self) -> str:
        return f"ResourcePath(base_dir={self.base_dir})"
