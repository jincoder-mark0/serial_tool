"""MacroScriptManager와 MacroPresenter의 책임 경계를 검증합니다."""
import inspect
import time
from unittest.mock import MagicMock, patch

from common.dtos import MacroScriptData
from model.macro_script_manager import MacroScriptManager
from presenter.macro_presenter import MacroPresenter


def test_macro_presenter_does_not_own_file_io_or_qthread():
    source = inspect.getsource(MacroPresenter)

    assert "QThread" not in source
    assert "commentjson" not in source
    assert "with open(" not in source
    assert "script_manager.save_script" in source
    assert "script_manager.request_load" in source


def test_save_round_trip(tmp_path):
    manager = MacroScriptManager()
    file_path = tmp_path / "macro.json"
    payload = {"commands": [{"command": "AT"}], "control_state": {}}
    saved = []
    manager.save_succeeded.connect(saved.append)

    assert manager.save_script(
        MacroScriptData(file_path=str(file_path), data=payload)
    ) is True

    assert saved == [str(file_path)]
    text = file_path.read_text(encoding="utf-8")
    assert '"AT"' in text


def test_save_failure_is_reported(tmp_path):
    manager = MacroScriptManager()
    failed = []
    manager.save_failed.connect(failed.append)
    invalid_path = tmp_path / "missing" / "macro.json"

    assert manager.save_script(
        MacroScriptData(file_path=str(invalid_path), data={})
    ) is False
    assert len(failed) == 1


def test_async_load_emits_macro_script_data(qapp, tmp_path, qtbot):
    manager = MacroScriptManager()
    file_path = tmp_path / "macro.json"
    file_path.write_text(
        '{"commands": [{"command": "AT"}], "control_state": {}}',
        encoding="utf-8",
    )
    loaded = []
    manager.script_loaded.connect(loaded.append)

    assert manager.request_load(str(file_path)) is True
    qtbot.waitUntil(lambda: bool(loaded), timeout=2000)
    manager.stop()

    assert loaded[0].file_path == str(file_path)
    assert loaded[0].data["commands"][0]["command"] == "AT"


def test_overlapping_load_is_rejected(qapp, tmp_path):
    manager = MacroScriptManager()
    file_path = tmp_path / "macro.json"
    file_path.write_text('{"commands": [], "control_state": {}}', encoding="utf-8")

    original_run = manager.request_load
    with patch(
        "model.macro_script_manager.commentjson.load",
        side_effect=lambda _file: (time.sleep(0.2) or {"commands": [], "control_state": {}}),
    ):
        assert original_run(str(file_path)) is True
        assert manager.request_load(str(file_path)) is False
        manager.stop()


def test_stop_without_load_is_idempotent():
    manager = MacroScriptManager()
    assert manager.stop() is True
    assert manager.stop() is True
