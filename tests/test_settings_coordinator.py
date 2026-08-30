"""SettingsCoordinator의 persistence/runtime 적용 정책 테스트."""
from unittest.mock import MagicMock, patch

from common.constants import ConfigKeys
from common.dtos import FontConfig, PreferencesState
from presenter.settings_coordinator import SettingsCoordinator


def _make_coordinator():
    view = MagicMock()
    settings = MagicMock()
    port_presenter = MagicMock()
    manual_presenter = MagicMock()
    packet_presenter = MagicMock()
    coordinator = SettingsCoordinator(
        view,
        settings,
        port_presenter,
        manual_presenter,
        packet_presenter,
    )
    return coordinator, view, settings, port_presenter, manual_presenter, packet_presenter


def test_connect_signals_is_idempotent():
    coordinator, view, *_ = _make_coordinator()

    coordinator.connect_signals()
    coordinator.connect_signals()

    view.settings_save_requested.connect.assert_called_once()
    view.font_settings_changed.connect.assert_called_once()
    view.theme_change_requested.connect.assert_called_once()
    view.language_change_requested.connect.assert_called_once()
    view.preferences_requested.connect.assert_called_once()


def test_apply_preferences_updates_all_runtime_consumers():
    coordinator, view, settings, port, manual, packet = _make_coordinator()
    state = PreferencesState(
        theme="dark",
        language="ko",
        font_size=13,
        max_log_lines=1234,
        local_echo_enabled=True,
    )
    info = []
    coordinator.info_requested.connect(info.append)

    with patch(
        "presenter.settings_coordinator.PreferencesCoordinator.apply_state"
    ) as apply_state, patch(
        "presenter.settings_coordinator.language_manager.set_language"
    ) as set_language, patch(
        "presenter.settings_coordinator.language_manager.get_text",
        return_value="updated",
    ):
        coordinator.apply_preferences(state)

    apply_state.assert_called_once_with(settings, state)
    settings.save_settings.assert_called_once()
    view.switch_theme.assert_called_once_with("dark")
    view.apply_proportional_font_size.assert_called_once_with(13)
    set_language.assert_called_once_with("ko")
    port.apply_max_log_lines.assert_called_once_with(1234)
    manual.update_local_echo_setting.assert_called_once_with(True)
    packet.on_settings_changed.assert_called_once_with(state)
    view.show_status_message.assert_called_once_with("updated", 2000)
    assert info == ["updated"]


def test_apply_theme_owns_theme_persistence_and_view_update():
    coordinator, view, settings, *_ = _make_coordinator()

    coordinator.apply_theme("DARK")

    settings.set.assert_called_once_with(ConfigKeys.THEME, "dark")
    settings.save_settings.assert_called_once()
    view.switch_theme.assert_called_once_with("dark")


def test_apply_language_owns_language_persistence():
    coordinator, _, settings, *_ = _make_coordinator()

    with patch(
        "presenter.settings_coordinator.language_manager.set_language"
    ) as set_language:
        coordinator.apply_language("ko")

    settings.set.assert_called_once_with(ConfigKeys.LANGUAGE, "ko")
    settings.save_settings.assert_called_once()
    set_language.assert_called_once_with("ko")


def test_apply_font_persists_all_font_fields_once():
    coordinator, _, settings, *_ = _make_coordinator()
    font = FontConfig(
        prop_family="Arial",
        prop_size=11,
        fixed_family="Consolas",
        fixed_size=10,
    )

    coordinator.apply_font(font)

    expected = [
        (ConfigKeys.PROP_FONT_FAMILY, "Arial"),
        (ConfigKeys.PROP_FONT_SIZE, 11),
        (ConfigKeys.FIXED_FONT_FAMILY, "Consolas"),
        (ConfigKeys.FIXED_FONT_SIZE, 10),
    ]
    assert [call.args for call in settings.set.call_args_list] == expected
    settings.save_settings.assert_called_once()
