"""
애플리케이션 설정 변경 orchestration 모듈.

Preferences/Theme/Language/Font 저장과 관련 View/Presenter 갱신을 MainPresenter에서
분리합니다. SettingsManager는 이 coordinator에 명시적으로 주입되며, View의 설정 관련
request signal은 한 곳에서 처리됩니다.
"""
from PyQt5.QtCore import QObject, pyqtSignal

from common.constants import ConfigKeys
from common.dtos import FontConfig, PreferencesState
from core.logger import logger
from core.settings_manager import SettingsManager
from presenter.manual_control_presenter import ManualControlPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.port_presenter import PortPresenter
from presenter.preferences_coordinator import PreferencesCoordinator
from view.main_window import MainWindow
from view.managers.language_manager import language_manager


class SettingsCoordinator(QObject):
    """설정 persistence와 runtime 반영 정책을 소유합니다."""

    info_requested = pyqtSignal(str)

    def __init__(
        self,
        view: MainWindow,
        settings_manager: SettingsManager,
        port_presenter: PortPresenter,
        manual_control_presenter: ManualControlPresenter,
        packet_presenter: PacketPresenter,
    ) -> None:
        super().__init__()
        self._view = view
        self._settings = settings_manager
        self._port_presenter = port_presenter
        self._manual_control_presenter = manual_control_presenter
        self._packet_presenter = packet_presenter
        self._connected = False

    def connect_signals(self) -> None:
        """MainWindow의 설정 관련 request signal을 한 번만 연결합니다."""
        if self._connected:
            return
        self._view.settings_save_requested.connect(self.apply_preferences)
        self._view.font_settings_changed.connect(self.apply_font)
        self._view.theme_change_requested.connect(self.apply_theme)
        self._view.language_change_requested.connect(self.apply_language)
        self._view.preferences_requested.connect(self.open_preferences)
        self._connected = True

    def open_preferences(self) -> None:
        """현재 canonical settings로 Preferences dialog를 엽니다."""
        self._view.open_preferences_dialog(
            PreferencesCoordinator.build_state(self._settings)
        )

    def apply_preferences(self, state: PreferencesState) -> None:
        """PreferencesState를 저장하고 모든 runtime 소비자에 동일하게 반영합니다."""
        PreferencesCoordinator.apply_state(self._settings, state)
        self._settings.save_settings()

        self._view.switch_theme(state.theme.lower())
        self._view.apply_proportional_font_size(state.font_size)
        language_manager.set_language(state.language)
        self._port_presenter.apply_max_log_lines(state.max_log_lines)
        self._manual_control_presenter.update_local_echo_setting(
            state.local_echo_enabled
        )
        self._packet_presenter.on_settings_changed(state)

        message = language_manager.get_text("main_status_msg_settings_updated")
        self._view.show_status_message(message, 2000)
        self.info_requested.emit(message)

    def apply_theme(self, theme_name: str) -> None:
        """Theme 요청을 canonical 값으로 저장한 뒤 View에 반영합니다."""
        normalized = theme_name.lower()
        self._settings.set(ConfigKeys.THEME, normalized)
        self._settings.save_settings()
        self._view.switch_theme(normalized)

    def apply_language(self, language_code: str) -> None:
        """Language 요청을 저장한 뒤 LanguageManager에 반영합니다."""
        self._settings.set(ConfigKeys.LANGUAGE, language_code)
        self._settings.save_settings()
        language_manager.set_language(language_code)

    def apply_font(self, font_config: FontConfig) -> None:
        """FontConfig를 SettingsManager에 저장합니다."""
        self._settings.set(ConfigKeys.PROP_FONT_FAMILY, font_config.prop_family)
        self._settings.set(ConfigKeys.PROP_FONT_SIZE, font_config.prop_size)
        self._settings.set(ConfigKeys.FIXED_FONT_FAMILY, font_config.fixed_family)
        self._settings.set(ConfigKeys.FIXED_FONT_SIZE, font_config.fixed_size)
        self._settings.save_settings()
        logger.info("Font settings saved successfully.")
