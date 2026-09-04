"""
SerialTool 애플리케이션 진입점.

리소스와 Qt 애플리케이션을 준비한 뒤 ApplicationBootstrapper에 runtime graph 조립을
위임합니다. 구체 Presenter/Model 조립 규칙은 이 파일이 알지 않습니다.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from application_bootstrap import ApplicationBootstrapper
from common.app_info import __version__
from common.constants import ConfigKeys
from common.defaults import DEFAULT_LANGUAGE, DEFAULT_THEME
from core.error_handler import install_global_error_handler, set_error_message_provider
from core.logger import logger
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager
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

    settings_mgr = SettingsManager(resource_path)
    language_manager = LanguageManager(resource_path)
    theme_manager = ThemeManager(resource_path)
    color_manager = ColorManager(resource_path)

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
    # 팔레트 전파는 두 매니저를 모두 아는 composition root가 한다.
    # ThemeManager가 전역 ColorManager를 직접 부르던 구조를 대체한 것이다.
    color_manager.apply_theme(saved_theme)

    window = MainWindow(theme_manager, color_manager)
    runtime = ApplicationBootstrapper(window, settings_mgr).build()  # noqa: F841
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
