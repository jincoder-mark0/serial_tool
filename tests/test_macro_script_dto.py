"""MacroScriptManager -> MacroPresenter DTO 경계와 JSON 왕복 호환성을 검증합니다."""
import commentjson
from unittest.mock import MagicMock

import pytest

from common.dtos import MacroScriptData
from model.macro_script_manager import MacroScriptManager
from presenter.macro_presenter import MacroPresenter


@pytest.fixture
def mock_panel():
    return MagicMock()


@pytest.fixture
def mock_runner():
    return MagicMock()


@pytest.fixture
def script_manager():
    manager = MacroScriptManager()
    yield manager
    manager.stop()


@pytest.fixture
def presenter(mock_panel, mock_runner, script_manager):
    return MacroPresenter(
        panel=mock_panel,
        runner=mock_runner,
        script_manager=script_manager,
    )


def test_manager_emits_macro_script_data_on_async_load(tmp_path, script_manager, qtbot):
    file_path = tmp_path / "macro_dto_worker.json"
    saved_data = {
        "commands": [{"enabled": True, "command": "AT", "delay_ms": 10}],
        "control_state": {"max_runs": 3, "interval_ms": 100},
    }
    with open(file_path, "w", encoding="utf-8") as file:
        commentjson.dump(saved_data, file, indent=4)

    with qtbot.waitSignal(script_manager.script_loaded, timeout=2000) as blocker:
        assert script_manager.request_load(str(file_path)) is True

    payload = blocker.args[0]
    assert isinstance(payload, MacroScriptData)
    assert payload.file_path == str(file_path)
    assert payload.data == saved_data


def test_save_then_load_round_trip_preserves_json_format(
    presenter,
    script_manager,
    mock_panel,
    tmp_path,
    qtbot,
):
    file_path = tmp_path / "macro_dto_roundtrip.json"
    original_data = {
        "commands": [
            {
                "enabled": True,
                "command": "AT+TEST",
                "hex_mode": False,
                "prefix_enabled": False,
                "suffix_enabled": True,
                "delay_ms": 50,
                "expect": "OK",
                "timeout_ms": 3000,
            }
        ],
        "control_state": {
            "max_runs": 0,
            "interval_ms": 200,
            "broadcast_enabled": False,
        },
    }

    script_data = MacroScriptData(file_path=str(file_path), data=original_data)
    presenter.on_script_save(script_data)

    with open(file_path, "r", encoding="utf-8") as file:
        assert commentjson.load(file) == original_data

    with qtbot.waitSignal(script_manager.script_loaded, timeout=2000):
        presenter.on_script_load(str(file_path))

    mock_panel.apply_state.assert_called_once_with(original_data)


def test_presenter_requires_explicit_script_manager(mock_panel, mock_runner):
    with pytest.raises(TypeError):
        MacroPresenter(panel=mock_panel, runner=mock_runner)
