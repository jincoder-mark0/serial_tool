import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가하여 모듈 import 가능하게 함
# 이것은 모든 import 전에 실행되어야 합니다
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from version import __version__
from config import AppConfig
from view.main_window import MainWindow
from presenter.main_presenter import MainPresenter

from core.logger import logger

def setup_logging() -> None:
    """
    로깅 설정을 초기화합니다.
    로그 레벨, 포맷, 날짜 형식을 설정합니다.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

def main() -> None:
    """
    애플리케이션의 메인 진입점입니다.
    로깅 설정, QApplication 초기화, 메인 윈도우 생성 및 실행을 담당합니다.
    """
    setup_logging()
    logging.info(f"Starting Serial Tool v{__version__}")

    # 애플리케이션 설정 초기화
    app_config = AppConfig()

    # 핵심 모듈에 설정 주입
    logger.configure(app_config)

    # 경로 검증
    path_status = app_config.validate_paths()
    for path_name, exists in path_status.items():
        if not exists:
            logging.warning(f"Path not found: {path_name}")

    logging.info(f"Base directory: {app_config.base_dir}")

    # 고해상도(High DPI) 스케일링 설정
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # MainWindow 초기화 (app_config 전달)
    window = MainWindow(app_config=app_config)

    # MainPresenter 초기화 (View와 Model 연결)
    presenter = MainPresenter(window)

    window.show()

    logging.info("Application initialized")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
