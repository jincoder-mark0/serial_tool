"""
애플리케이션 설정 및 경로 관리
모든 리소스 경로를 중앙에서 관리합니다.
"""
import os
from pathlib import Path
from typing import Dict


class AppConfig:
    """애플리케이션 설정 및 경로를 관리하는 클래스"""

    def __init__(self, base_dir: Path = None):
        """
        AppConfig를 초기화합니다.

        Args:
            base_dir: 프로젝트 루트 디렉토리. None이면 자동 감지.
        """
        # 프로젝트 루트 디렉토리 설정
        if base_dir is None:
            if hasattr(os, '_MEIPASS'):
                # PyInstaller 번들 환경
                self.base_dir = Path(os._MEIPASS)
            else:
                # 개발 모드: config.py가 있는 디렉토리가 루트
                self.base_dir = Path(__file__).parent
        else:
            self.base_dir = Path(base_dir)

        # 리소스 경로 설정
        self.config_dir = self.base_dir / 'config'
        self.resources_dir = self.base_dir / 'resources'

        # 설정 파일 경로
        self.settings_file = self.config_dir / 'settings.json'

        # 언어 파일 경로
        self.languages_dir = self.config_dir / 'languages'
        self.language_files: Dict[str, Path] = {
            'en': self.languages_dir / 'en.json',
            'ko': self.languages_dir / 'ko.json'
        }

        # 테마 파일 경로
        self.themes_dir = self.resources_dir / 'themes'
        self.theme_files: Dict[str, Path] = {
            'common': self.themes_dir / 'common.qss',
            'dark': self.themes_dir / 'dark_theme.qss',
            'light': self.themes_dir / 'light_theme.qss'
        }

        # 아이콘 경로
        self.icons_dir = self.resources_dir / 'icons'

    def get_language_file(self, lang_code: str) -> Path:
        """
        언어 코드에 해당하는 언어 파일 경로를 반환합니다.

        Args:
            lang_code: 언어 코드 (예: 'en', 'ko')

        Returns:
            Path: 언어 파일 경로
        """
        return self.language_files.get(lang_code, self.language_files['en'])

    def get_theme_file(self, theme_name: str) -> Path:
        """
        테마 이름에 해당하는 테마 파일 경로를 반환합니다.

        Args:
            theme_name: 테마 이름 (예: 'dark', 'light', 'common')

        Returns:
            Path: 테마 파일 경로
        """
        return self.theme_files.get(theme_name)

    def get_icon_path(self, icon_name: str, theme: str = None) -> Path:
        """
        아이콘 파일 경로를 반환합니다.

        Args:
            icon_name: 아이콘 이름 (예: 'add', 'delete')
            theme: 테마 접미사 (예: 'dark', 'light'). None이면 접미사 없음.

        Returns:
            Path: 아이콘 파일 경로
        """
        if theme:
            filename = f"{icon_name}_{theme}.svg"
        else:
            filename = f"{icon_name}.svg"

        return self.icons_dir / filename

    def validate_paths(self) -> Dict[str, bool]:
        """
        주요 경로들이 존재하는지 검증합니다.

        Returns:
            Dict[str, bool]: 경로별 존재 여부
        """
        return {
            'config_dir': self.config_dir.exists(),
            'resources_dir': self.resources_dir.exists(),
            'settings_file': self.settings_file.exists(),
            'languages_dir': self.languages_dir.exists(),
            'themes_dir': self.themes_dir.exists(),
            'icons_dir': self.icons_dir.exists()
        }

    def __repr__(self) -> str:
        return f"AppConfig(base_dir={self.base_dir})"
