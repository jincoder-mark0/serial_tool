"""
SerialTool 애플리케이션 진입점

시리얼 통신 도구의 메인 실행 파일입니다.

## WHY
* 애플리케이션 초기화 및 실행 관리
* 전역 설정 및 리소스 경로 구성
* 에러 핸들링 및 로깅 설정
* MVP 패턴 초기 연결 및 Manager 초기화 보장

## WHAT
* QApplication 생성 및 설정
* ResourcePath 초기화
* 핵심 Manager(Settings, Theme, Language, Color) 사전 초기화 및 의존성 주입
* MainWindow 및 MainPresenter 생성
* 전역 에러 핸들러 설치

## HOW
* sys.path 조정으로 모듈 import 경로 설정
* ResourcePath로 개발/배포 환경 자동 감지
* 싱글톤 Manager들을 미리 인스턴스화하여 전역 상태 설정
* MVP 패턴으로 View-Presenter 연결
* QApplication.exec_()로 이벤트 루프 시작
"""
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가 (모든 import 전에 실행)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from common.app_info import __version__
from core.resource_path import ResourcePath
from view.main_window import MainWindow
from presenter.main_presenter import MainPresenter

from core.logger import logger
from core.error_handler import install_global_error_handler
from core.settings_manager import SettingsManager
from view.managers.theme_manager import ThemeManager
from view.managers.language_manager import LanguageManager
from view.managers.color_manager import ColorManager
from common.constants import ConfigKeys

def setup_logging() -> None:
    """
    로깅 설정 초기화

    Logic:
        - 로그 레벨을 INFO로 설정
        - 타임스탬프, 레벨, 메시지 포맷 정의
        - 시간 형식을 HH:MM:SS로 설정
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

def main() -> None:
    """
    애플리케이션 메인 진입점

    Logic:
        - 로깅 및 에러 핸들러 설치
        - ResourcePath 초기화 및 경로 검증
        - SettingsManager 우선 초기화 (설정값 로드)
        - 나머지 Manager들(Theme, Lang, Color) 초기화 및 경로 주입
        - 언어 설정 적용 (UI 생성 전 텍스트 준비)
        - QApplication 및 MainWindow 생성
        - 테마 설정 적용 (UI 표시 전 깜빡임 방지)
        - 이벤트 루프 시작
    """
    setup_logging()

    # 1. 전역 에러 핸들러 설치
    install_global_error_handler()
    logging.info(f"Starting Serial Tool v{__version__}")

    # 2. ResourcePath 초기화 (개발/배포 환경 자동 감지)
    resource_path = ResourcePath()
    logger.configure(resource_path)
    logging.info(f"Base directory: {resource_path.base_dir}")

    # 3. SettingsManager 우선 초기화
    # 설정을 먼저 로드해야 저장된 언어와 테마를 알 수 있음
    settings_mgr = SettingsManager(resource_path)

    # 4. Manager들 경로 주입 (Lazy Initialization 트리거)
    # 이때 실제 리소스 파일(언어 JSON, 테마 QSS 등)이 로드됨
    language_manager = LanguageManager(resource_path)
    theme_manager = ThemeManager(resource_path)
    ColorManager(resource_path)

    # 5. 언어 설정 적용
    # MainWindow 생성 전에 언어를 설정해야 UI 텍스트가 올바르게 표시됨
    saved_lang = settings_mgr.get(ConfigKeys.LANGUAGE, "en")
    language_manager.set_language(saved_lang)

    # 경로 검증 및 경고 (로깅용)
    path_status = resource_path.validate_paths()
    for path_name, exists in path_status.items():
        if not exists:
            logging.warning(f"Path not found: {path_name}")

    # 6. High DPI 스케일링 설정
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 7. 테마 설정 적용 (UI 표시 직전)
    # MainWindow 생성 후 show() 호출 전에 테마를 입혀 깜빡임을 방지
    # (ThemeManager 초기화 시에는 기본값만 로드하고 적용은 여기서 수행)
    saved_theme = settings_mgr.get(ConfigKeys.THEME, "dark")
    theme_manager.apply_theme(saved_theme)

    # 8. MainWindow 및 Presenter 초기화
    window = MainWindow()
    presenter = MainPresenter(window)

    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()