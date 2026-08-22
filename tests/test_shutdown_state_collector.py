"""
S-058 신규 테스트: ShutdownStateCollector (presenter/shutdown_state_collector.py)

## WHY
* 종료 시 상태 병합/반영 로직이 종전에는 MainPresenter.on_close_requested()
  안에 DTO->dict 수동 변환으로 인라인되어 있어, Qt 없이 검증할 수 없었다.
  분리 후에는 Qt/View 의존이 없는 순수 로직이므로 이를 직접 고정한다.

## WHAT
* merge_manual_control_state()가 ManualControlState DTO를
  left_section_state["manual_control"]["manual_control_widget"]로 정확히
  변환하는지 검증.
* apply_window_state()가 SettingsManager의 기대 키에 값을 반영하는지 검증
  (right_section_width가 None이면 SAVED_RIGHT_WIDTH를 쓰지 않는 조건 분기 포함).
* collect_and_apply()가 두 단계를 순서대로 수행하는지 검증.

## HOW
* Qt import 없이 `tests/conftest.py`의 `mock_settings_manager`(임시 경로
  SettingsManager)만 사용한다.
"""
from common.constants import ConfigKeys
from common.dtos import MainWindowState, ManualControlState
from presenter.shutdown_state_collector import ShutdownStateCollector


class TestMergeManualControlState:
    """merge_manual_control_state()의 DTO->dict 변환을 고정한다."""

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

        widget_state = window_state.left_section_state["manual_control"]["manual_control_widget"]
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
        """제자리 수정이며 기존 'manual_control' 키가 있어도 덮어써야 한다."""
        window_state = MainWindowState(
            left_section_state={"manual_control": {"stale": "data"}}, right_section_state={}
        )
        manual_state = ManualControlState()

        ShutdownStateCollector.merge_manual_control_state(window_state, manual_state)

        assert "stale" not in window_state.left_section_state["manual_control"]
        assert "manual_control_widget" in window_state.left_section_state["manual_control"]


class TestApplyWindowState:
    """apply_window_state()가 SettingsManager에 기대한 키로 값을 반영하는지 검증한다."""

    def test_apply_writes_window_geometry_keys(self, mock_settings_manager):
        state = MainWindowState(
            width=1600, height=1000, x=10, y=20, splitter_state="b64==",
            right_panel_visible=False, left_section_state={}, right_section_state={}
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
            right_section_width=None, left_section_state={}, right_section_state={}
        )
        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        # right_section_width가 None이면 SAVED_RIGHT_WIDTH를 건드리지 않아야 한다.
        assert mock_settings_manager.get(ConfigKeys.SAVED_RIGHT_WIDTH) is sentinel

    def test_apply_writes_saved_right_width_when_present(self, mock_settings_manager):
        state = MainWindowState(
            right_section_width=345, left_section_state={}, right_section_state={}
        )
        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.SAVED_RIGHT_WIDTH) == 345

    def test_apply_writes_sub_widget_states_when_keys_present(self, mock_settings_manager):
        state = MainWindowState(
            left_section_state={
                ConfigKeys.MANUAL_CONTROL_STATE: {"foo": "bar"},
                ConfigKeys.PORTS_TABS_STATE: [{"port": "COM1"}],
            },
            right_section_state={
                ConfigKeys.MACRO_COMMANDS: [{"cmd": "AT"}],
                ConfigKeys.MACRO_CONTROL_STATE: {"broadcast": True},
            },
        )
        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.MANUAL_CONTROL_STATE) == {"foo": "bar"}
        assert mock_settings_manager.get(ConfigKeys.PORTS_TABS_STATE) == [{"port": "COM1"}]
        assert mock_settings_manager.get(ConfigKeys.MACRO_COMMANDS) == [{"cmd": "AT"}]
        assert mock_settings_manager.get(ConfigKeys.MACRO_CONTROL_STATE) == {"broadcast": True}

    def test_apply_skips_sub_widget_states_when_keys_absent(self, mock_settings_manager):
        sentinel = object()
        mock_settings_manager.set(ConfigKeys.MANUAL_CONTROL_STATE, sentinel)

        state = MainWindowState(left_section_state={}, right_section_state={})
        ShutdownStateCollector.apply_window_state(mock_settings_manager, state)

        assert mock_settings_manager.get(ConfigKeys.MANUAL_CONTROL_STATE) is sentinel


class TestCollectAndApply:
    """collect_and_apply()가 병합 후 반영까지 순서대로 수행하는지 검증한다."""

    def test_collect_and_apply_merges_then_applies(self, mock_settings_manager):
        window_state = MainWindowState(left_section_state={}, right_section_state={})
        manual_state = ManualControlState(input_text="PING", auto_tx_interval_ms=500)

        ShutdownStateCollector.collect_and_apply(mock_settings_manager, window_state, manual_state)

        # 병합 결과가 left_section_state에도 반영되어 있어야 한다 (제자리 수정).
        assert (
            window_state.left_section_state["manual_control"]["manual_control_widget"]["input_text"]
            == "PING"
        )
        # ConfigKeys.MANUAL_CONTROL_STATE == "manual_control"이므로 병합된 값이
        # apply_window_state()의 하위 위젯 상태 저장 조건에 걸려 그대로 저장된다.
        saved = mock_settings_manager.get(ConfigKeys.MANUAL_CONTROL_STATE)
        assert saved["manual_control_widget"]["input_text"] == "PING"
        assert saved["manual_control_widget"]["auto_tx_interval_ms"] == 500
