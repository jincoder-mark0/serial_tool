import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
import qdarkstyle

# 프로젝트 루트 경로를 sys.path에 추가하여 모듈 import 가능하게 함
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from version import __version__
from view.main_window import MainWindow

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )

def main():
    setup_logging()
    logging.info(f"Starting SerialManager v{__version__}")

    # High DPI Scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    # 테마 적용
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    # MainWindow 초기화
    window = MainWindow()
    window.show()

    logging.info("Application initialized")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
