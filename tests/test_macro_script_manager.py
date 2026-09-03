"""MacroScriptManager와 MacroPresenter의 책임 경계를 검증합니다."""
import inspect
import time
from threading import Event
from unittest.mock import patch

import pytest

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

    # 여기서 재는 것은 "언젠가 도착하는가"이지 지연 시간이 아니다. 2초는 부하가
    # 걸린 머신에서 빠듯해 실제로 간헐적으로 터졌다(전체 스위트 실행 시간이
    # 8초~19초로 흔들린다). 여유를 주되, 터졌을 때 어디서 막혔는지 알 수 있게
    # worker 상태를 함께 남긴다 — "waitUntil timed out"만으로는 다음에도 못 고친다.
    try:
        qtbot.waitUntil(lambda: bool(loaded), timeout=5000)
    except Exception as exc:
        worker = manager._load_worker
        if worker is None:
            detail = "worker=이미 정리됨 (신호만 도달하지 않음)"
        else:
            detail = (
                f"worker_running={worker.isRunning()}, "
                f"pending_io={worker.has_pending_io}"
            )
        pytest.fail(
            f"script_loaded가 오지 않았다 ({type(exc).__name__}). "
            f"is_loading={manager.is_loading}, {detail}"
        )

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


def test_stop_interrupts_qthread_when_file_read_is_blocked(qapp, tmp_path):
    manager = MacroScriptManager()
    file_path = tmp_path / "blocked.json"
    file_path.write_text("{}", encoding="utf-8")
    release = Event()

    def blocked_load(_file):
        release.wait(5)
        return {}

    with patch(
        "model.macro_script_manager.commentjson.load",
        side_effect=blocked_load,
    ):
        assert manager.request_load(str(file_path)) is True
        started_at = time.monotonic()
        assert manager.stop() is True
        elapsed = time.monotonic() - started_at
        assert manager.request_load(str(file_path)) is False
        release.set()

        deadline = time.monotonic() + 1
        while manager._pending_io_worker.has_pending_io and time.monotonic() < deadline:
            time.sleep(0.01)

        assert manager.request_load(str(file_path)) is True
        manager.stop()

    assert elapsed < 0.5
    assert manager._load_worker is None
    assert manager.stop() is True
