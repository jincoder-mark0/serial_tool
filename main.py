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
* 핵심 Manager(Settings, Theme, Language, Color) 사전 초기  화
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
        - 모든 Manager 클래스 사전 초기화 (View 생성 전 필수)
        - High DPI 스케일링 설정
        - QApplication 생성
        - MainWindow 및 MainPresenter 초기화
        - 이벤트 루프 시작
    """
    setup_logging()

    # 전역 에러 핸들러 설치
    install_global_error_handler()
    logging.info(f"Starting Serial Tool v{__version__}")

    # ResourcePath 초기화 (개발/배포 환경 자동 감지)
    resource_path = ResourcePath()

    # 핵심 모듈에 경로 주입 및 초기화
    logger.configure(resource_path)

    # [중요] Manager들 사전 초기화 (순서 중요: Settings -> Theme/Lang -> View)
    # MainWindow 내부에서 직접 생성하지 않도록 외부에서 주입/초기화 보장
    SettingsManager(resource_path)
    ThemeManager(resource_path)
    LanguageManager(resource_path)
    ColorManager(resource_path)

    # 경로 검증 및 경고
    path_status = resource_path.validate_paths()
    for path_name, exists in path_status.items():
        if not exists:
            logging.warning(f"Path not found: {path_name}")

    logging.info(f"Base directory: {resource_path.base_dir}")

    # High DPI 스케일링 설정
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # MainWindow 초기화
    # MainWindow는 이제 resource_path를 직접 받지 않아도 됨
    window = MainWindow()

    # MainPresenter 초기화
    presenter = MainPresenter(window)

    window.show()

    logging.info("Application initialized")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
