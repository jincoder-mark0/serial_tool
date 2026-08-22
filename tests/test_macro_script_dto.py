"""
매크로 스크립트 로드 DTO화 검증 모듈

S-044: 매크로 스크립트 로드 경로(Worker -> Presenter)가 raw dict가 아닌
`MacroScriptData` DTO를 경유하는지, 그리고 기존 JSON 파일 포맷과의
저장/로드 왕복 호환성이 유지되는지를 검증합니다.

## WHY
* CLAUDE.md 절대 규칙: "계층 간 데이터 전달은 dict 금지, DTO만 사용"
* 매크로 스크립트 파일은 기존 사용자가 저장해 둔 JSON을 계속 불러올 수
  있어야 하므로, DTO화가 파일 포맷을 바꾸지 않았는지 회귀 확인이 필요

## WHAT
* ScriptLoadWorker.load_finished 시그널이 `MacroScriptData` 인스턴스를 방출하는지
* MacroPresenter._on_load_success가 DTO를 받아 panel.apply_state(dict)를 호출하는지
* 저장(on_script_save) -> 로드(ScriptLoadWorker) 왕복 시 데이터가 그대로 보존되는지

## HOW
* MacroPanel/MacroRunner는 MagicMock으로 대체하여 Presenter 로직만 격리 검증
* ScriptLoadWorker.run()을 QThread.start() 없이 동기 호출하여 스레드 의존성 제거

pytest tests/test_macro_script_dto.py -v
"""
import commentjson
import pytest
from unittest.mock import MagicMock

from presenter.macro_presenter import MacroPresenter, ScriptLoadWorker
from common.dtos import MacroScriptData


@pytest.fixture
def mock_panel():
    """MacroPanel(View)을 Mocking합니다."""
    return MagicMock()


@pytest.fixture
def mock_runner():
    """MacroRunner(Model)를 Mocking합니다."""
    return MagicMock()


@pytest.fixture
def presenter(mock_panel, mock_runner):
    """테스트 대상 MacroPresenter 인스턴스를 생성합니다."""
    return MacroPresenter(panel=mock_panel, runner=mock_runner)


def test_script_load_worker_emits_macro_script_data(tmp_path):
    """ScriptLoadWorker.load_finished가 dict가 아닌 MacroScriptData DTO를 방출하는지 확인합니다."""
    file_path = tmp_path / "macro_dto_worker.json"
    saved_data = {
        "commands": [{"enabled": True, "command": "AT", "delay_ms": 10}],
        "control_state": {"max_runs": 3, "interval_ms": 100},
    }
    with open(file_path, "w", encoding="utf-8") as f:
        commentjson.dump(saved_data, f, indent=4)

    worker = ScriptLoadWorker(str(file_path))
    received = {}
    worker.load_finished.connect(lambda payload: received.setdefault("payload", payload))
    worker.load_failed.connect(lambda msg: pytest.fail(f"load_failed emitted unexpectedly: {msg}"))

    # QThread.start() 대신 run()을 직접 호출하여 스레드 없이 동기 실행
    worker.run()

    assert "payload" in received
    payload = received["payload"]
    assert isinstance(payload, MacroScriptData), "load_finished는 dict가 아닌 MacroScriptData를 방출해야 한다"
    assert payload.file_path == str(file_path)
    assert payload.data == saved_data


def test_save_then_load_round_trip_preserves_json_format(presenter, mock_panel, tmp_path):
    """
    저장(on_script_save) -> 로드(ScriptLoadWorker + _on_load_success) 왕복 시
    panel.apply_state에 전달되는 데이터가 저장 시점의 데이터와 동일해야 한다
    (JSON 파일 포맷 호환성 유지 확인).
    """
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
        "control_state": {"max_runs": 0, "interval_ms": 200, "broadcast_enabled": False},
    }

    # 1. 저장: 기존 파일 포맷(raw dict, commands/control_state 키) 그대로 기록되는지 확인
    script_data = MacroScriptData(file_path=str(file_path), data=original_data)
    presenter.on_script_save(script_data)

    with open(file_path, "r", encoding="utf-8") as f:
        raw_saved = commentjson.load(f)
    assert raw_saved == original_data

    # 2. 로드: ScriptLoadWorker가 DTO를 생성하고, Presenter가 이를 unwrap하여
    #    panel.apply_state(dict)를 호출하는지 확인 (Worker->Presenter 구간은 DTO 경유)
    worker = ScriptLoadWorker(str(file_path))
    worker.load_finished.connect(presenter._on_load_success)
    worker.run()

    mock_panel.apply_state.assert_called_once_with(original_data)
