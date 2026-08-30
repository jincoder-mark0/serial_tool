"""ShutdownStateCollector의 View-state -> Settings-path 변환을 검증합니다."""
from common.constants import ConfigKeys
from common.dtos import MainWindowState, ManualControlState
from presenter.shutdown_state_collector import ShutdownStateCollector


class TestMergeManualControlState:
    def test_merge_produces_expected_nested_dict(self):
        window_state = MainWindowState(left_section_state={}, right_section_state={})
        manual_state = ManualControlState(
            input_text="AT+CSQ",
            hex_mode=True,
            prefix_enabled=True,
            suffix_enabled=False,
            rts_enabled=True,
            dtr_enabled=False,
            local_echo_enabled=True,
            broadcast_enabled=False,
            auto_tx_enabled=True,
            auto_tx_interval_ms=250,
        )

        ShutdownStateCollector.merge_manual_control_state(window_state, manual_state)

        widget_state = window_state.left_section_state["manual_control"][
            "manual_control_widget"
        ]
        assert widget_state == {
            "input_text": "AT+CSQ",
            "hex_mode": True,
            "prefix_enabled": True,
            "suffix_enabled": False,
            "rts_enabled": True,
            "dtr_enabled": False,
            "local_echo_enabled": True,
            "broadcast_enabled": False,
            "auto_tx_enabled": True,
            "auto_tx_interval_ms": 250,
        }

    def test_merge_overwrites_existing_manual_control_key(self):
        window_state = MainWindowState(
            left_section_state={"manual_control": {"stale": "data"}},
            right_section_state={},
        )

        ShutdownStateCollector.merge_manual_control_state(
            window_state,
            ManualControlState(),
        )

        assert "stale" not in window_state.left_section_state["manual_control"]
        assert "manual_control_widget" in window_state.left_section_state["manual_control"]


class TestApplyWindowState:
    def test_apply_writes_window_geometry_keys(self, mock_settings_manager):
        state = MainWindowState(
            width=1600,
            height=1000,
            x=10,
            y=20,
            splitter_state="b64==",
            right_panel_visible=False,
            left_section_state={},
            right_section_state={},
        )

        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.WINDOW_WIDTH) == 1600
        assert mock_settings_manager.get(ConfigKeys.WINDOW_HEIGHT) == 1000
        assert mock_settings_manager.get(ConfigKeys.WINDOW_X) == 10
        assert mock_settings_manager.get(ConfigKeys.WINDOW_Y) == 20
        assert mock_settings_manager.get(ConfigKeys.SPLITTER_STATE) == "b64=="
        assert mock_settings_manager.get(ConfigKeys.RIGHT_PANEL_VISIBLE) is False

    def test_apply_skips_saved_right_width_when_none(self, mock_settings_manager):
        sentinel = object()
        mock_settings_manager.set(ConfigKeys.SAVED_RIGHT_WIDTH, sentinel)
        state = MainWindowState(
            right_section_width=None,
            left_section_state={},
            right_section_state={},
        )

        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.SAVED_RIGHT_WIDTH) is sentinel

    def test_apply_writes_actual_view_nested_states(self, mock_settings_manager):
        """MainLeftSection/MainRightSection이 실제 반환하는 shape를 사용합니다."""
        state = MainWindowState(
            left_section_state={
                "ports": [{"port": "COM1"}],
                "manual_control": {"manual_control_widget": {"input_text": "AT"}},
            },
            right_section_state={
                "current_tab_index": 0,
                "macro_panel": {
                    "commands": [{"command": "AT+CSQ"}],
                    "control_state": {"broadcast": True},
                },
            },
        )

        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.PORTS_TABS_STATE) == [
            {"port": "COM1"}
        ]
        assert mock_settings_manager.get(ConfigKeys.MANUAL_CONTROL_STATE) == {
            "manual_control_widget": {"input_text": "AT"}
        }
        assert mock_settings_manager.get(ConfigKeys.MACRO_COMMANDS) == [
            {"command": "AT+CSQ"}
        ]
        assert mock_settings_manager.get(ConfigKeys.MACRO_CONTROL_STATE) == {
            "broadcast": True
        }
        assert mock_settings_manager.get(ConfigKeys.RIGHT_TAB_INDEX) == 0

    def test_settings_path_strings_are_not_expected_as_view_keys(
        self,
        mock_settings_manager,
    ):
        """dotted ConfigKeys는 Settings path이며 View state의 key가 아닙니다."""
        sentinel = object()
        mock_settings_manager.set(ConfigKeys.PORTS_TABS_STATE, sentinel)
        state = MainWindowState(
            left_section_state={ConfigKeys.PORTS_TABS_STATE: [{"port": "WRONG"}]},
            right_section_state={},
        )

        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.PORTS_TABS_STATE) is sentinel


class TestCollectAndApply:
    def test_collect_and_apply_preserves_ports_macro_and_manual_state(
        self,
        mock_settings_manager,
    ):
        window_state = MainWindowState(
            left_section_state={"ports": [{"port": "COM7"}]},
            right_section_state={
                "macro_panel": {
                    "commands": [{"command": "PING"}],
                    "control_state": {"repeat": 2},
                }
            },
        )
        manual_state = ManualControlState(
            input_text="AT",
            auto_tx_interval_ms=500,
        )

        ShutdownStateCollector.collect_and_apply(
            mock_settings_manager,
            window_state,
            manual_state,
        )

        saved_manual = mock_settings_manager.get(ConfigKeys.MANUAL_CONTROL_STATE)
        assert saved_manual["manual_control_widget"]["input_text"] == "AT"
        assert saved_manual["manual_control_widget"]["auto_tx_interval_ms"] == 500
        assert mock_settings_manager.get(ConfigKeys.PORTS_TABS_STATE) == [
            {"port": "COM7"}
        ]
        assert mock_settings_manager.get(ConfigKeys.MACRO_COMMANDS) == [
            {"command": "PING"}
        ]
        assert mock_settings_manager.get(ConfigKeys.MACRO_CONTROL_STATE) == {
            "repeat": 2
        }
