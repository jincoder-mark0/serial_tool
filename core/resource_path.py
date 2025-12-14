"""
리소스 경로 관리 모듈

애플리케이션의 모든 리소스 경로를 중앙에서 관리합니다.

## WHY
* 개발/배포 환경 경로 차이 자동 처리
* 하드코딩된 경로 제거로 유지보수성 향상
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
            if hasattr(os, '_MEIPASS'):
                # PyInstaller 번들 환경
                self.base_dir = Path(os._MEIPASS)
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
            'light': self.themes_dir / 'light_theme.qss'
        }

        # 아이콘 경로
        self.icons_dir = self.resources_dir / 'icons'

        # 로그 경로
        self.logs_dir = self.base_dir / 'logs'

    def get_language_file(self, language_code: str) -> Path:
        """
        언어 코드에 해당하는 언어 파일 경로 반환

        Args:
            language_code: 언어 코드 (예: 'en', 'ko')

        Returns:
            Path: 언어 파일 경로 (없으면 영어 기본값)
        """
        return self.language_files.get(language_code, self.language_files['en'])

    def get_theme_file(self, theme_name: str) -> Path:
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
            'languages_dir': self.languages_dir.exists(),
            'themes_dir': self.themes_dir.exists(),
            'icons_dir': self.icons_dir.exists(),
            'logs_dir': self.logs_dir.exists()
        }

    def __repr__(self) -> str:
        return f"ResourcePath(base_dir={self.base_dir})"
