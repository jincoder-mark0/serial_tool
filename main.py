"""
SerialTool 애플리케이션 진입점

애플리케이션 구성 요소를 조립하는 composition root 역할을 수행합니다.
SettingsManager/리소스 매니저를 한 번 생성하고 MainPresenter에 명시적으로 주입합니다.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from common.app_info import __version__
from common.constants import ConfigKeys
from common.defaults import DEFAULT_LANGUAGE, DEFAULT_THEME
from core.error_handler import install_global_error_handler, set_error_message_provider
from core.logger import logger
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager
from presenter.main_presenter import MainPresenter
from view.main_window import MainWindow
from view.managers.color_manager import ColorManager
from view.managers.language_manager import LanguageManager
from view.managers.theme_manager import ThemeManager


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    setup_logging()
    install_global_error_handler()
    logging.info(f"Starting Serial Tool v{__version__}")

    resource_path = ResourcePath()
    logger.configure(resource_path)
    logging.info(f"Base directory: {resource_path.base_dir}")

    # Composition root: runtime SettingsManager는 여기서 한 번 생성해 주입한다.
    settings_mgr = SettingsManager(resource_path)
    language_manager = LanguageManager(resource_path)
    theme_manager = ThemeManager(resource_path)
    ColorManager(resource_path)

    def _get_crash_dialog_texts() -> tuple:
        return (
            language_manager.get_text("error_title_critical"),
            language_manager.get_text("error_msg_unexpected"),
        )

    set_error_message_provider(_get_crash_dialog_texts)

    saved_lang = settings_mgr.get(ConfigKeys.LANGUAGE, DEFAULT_LANGUAGE)
    language_manager.set_language(saved_lang)

    for path_name, exists in resource_path.validate_paths().items():
        if not exists:
            logging.warning(f"Path not found: {path_name}")

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)

    saved_theme = settings_mgr.get(ConfigKeys.THEME, DEFAULT_THEME)
    theme_manager.apply_theme(saved_theme)

    window = MainWindow()
    presenter = MainPresenter(  # noqa: F841 - QObject signal wiring GC 방지
        window,
        settings_manager=settings_mgr,
    )
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
