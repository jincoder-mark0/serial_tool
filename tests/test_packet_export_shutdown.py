"""패킷 export의 중단·실패가 조용히 사라지지 않는지 검증한다.

## WHY
`PacketExportManager.stop()`은 `requestInterruption()`을 부르지만, worker의
`run()`은 그 요청을 **한 번도 확인하지 않았다** — 단일 blocking write였기 때문이다.
그래서 중단 요청은 아무 일도 하지 않았고, `stop()`은 1초를 기다린 뒤 `None`을
돌려주며 조용히 넘어갔다.

종료 경로(`ShutdownCoordinator` -> `PacketPresenter.stop()` -> 여기)에서 export가
끝나지 않으면 사용자는 **요청한 파일이 없는 이유를 알 수 없다.** S-080·S-084·S-085에서
계속 없애온 침묵과 같은 종류다.

형제 매니저(`PortScanManager`/`MacroScriptManager`)는 `bool`을 돌려주고 상한을
넘기면 경고를 남긴다. 이 매니저만 관례에서 벗어나 있었다.

## WHAT
* 중단 요청이 record 단위로 실제 적용되는가
* 중단 시 **대상 파일이 교체되지 않고** temporary file도 남지 않는가
  (부분 결과가 완성본으로 남으면 안 된다)
* 중단이 `export_failed`로 표면화되는가
* `stop()`이 bool을 돌려주는가
* 빈 경로가 의도한 메시지로 거절되는가
"""
from __future__ import annotations

import time

import pytest

from common.packet_records import PacketRecord
from model.packet_export_manager import (
    PacketExportAborted,
    PacketExportManager,
)


def _record(index: int) -> PacketRecord:
    payload = bytes([index % 256]) * 4
    return PacketRecord(
        packet_id=f"pkt-{index}",
        time_str=f"00:00:{index:02d}",
        port="COM1",
        packet_type="RX",
        raw_data=payload,
        data_hex=payload.hex().upper(),
        data_ascii="....",
        checksum_ok=None,
        annotation="",
    )


# ---------------------------------------------------------------------------
# 중단 계약 (thread 없이 결정론적으로)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("export_format", ["csv", "json", "hex", "raw"])
def test_abort_request_is_honoured_by_every_format(export_format, tmp_path):
    """
    네 포맷 모두 record 단위로 중단을 확인해야 한다.

    한 포맷만 확인하고 나머지는 같으려니 하면, 실제로는 중단되지 않는 경로가
    남는다 (`doc/mistakes.md` #9 — 부분 확인은 확인이 아니다).
    """
    target = tmp_path / f"out.{export_format}"
    records = tuple(_record(i) for i in range(10))

    with pytest.raises(PacketExportAborted) as excinfo:
        PacketExportManager.write_records(
            records,
            target,
            export_format,
            should_abort=lambda: True,
        )

    assert "0 of 10" in str(excinfo.value), (
        f"중단 시점을 알 수 없다: {excinfo.value}"
    )


def test_abort_leaves_neither_target_nor_temporary_file(tmp_path):
    """
    중단하면 부분 결과가 남으면 안 된다.

    대상 파일이 교체되면 사용자는 잘린 파일을 완성본으로 오인한다.
    temporary file이 남으면 쓰레기가 쌓인다.
    """
    target = tmp_path / "out.csv"
    records = tuple(_record(i) for i in range(10))

    calls = {"n": 0}

    def abort_after_three() -> bool:
        calls["n"] += 1
        return calls["n"] > 3

    with pytest.raises(PacketExportAborted):
        PacketExportManager.write_records(
            records, target, "csv", should_abort=abort_after_three
        )

    assert not target.exists(), "중단했는데 대상 파일이 만들어졌다"
    leftovers = list(tmp_path.glob("*.tmp"))
    assert not leftovers, f"temporary file이 남았다: {leftovers}"


def test_completed_export_reports_the_written_count(tmp_path):
    """정상 완료는 실제 기록한 개수를 돌려준다."""
    target = tmp_path / "out.csv"
    records = tuple(_record(i) for i in range(5))

    written = PacketExportManager.write_records(records, target, "csv")

    assert written == 5
    assert target.exists()
    assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------------------
# Manager 계약
# ---------------------------------------------------------------------------

def test_stop_returns_bool_like_sibling_managers(qapp):
    """
    `stop()`은 결과를 돌려줘야 한다.

    과거에는 `None`이라 상한을 넘겨도 호출자가 알 방법이 없었다.
    """
    manager = PacketExportManager()

    result = manager.stop(timeout_ms=100)

    assert result is True, "정리할 worker가 없으면 True여야 한다"


def test_running_export_is_aborted_and_surfaced_on_stop(qapp, tmp_path):
    """
    종료 중 export가 중단되면 **조용히 사라지지 않고** 실패로 표면화돼야 한다.

    사용자는 export를 요청했는데 파일이 없는 이유를 알아야 한다.
    """
    manager = PacketExportManager()
    failures: list[str] = []
    manager.export_failed.connect(failures.append)

    target = tmp_path / "big.csv"
    # 중단 확인이 여러 번 일어날 만큼 충분한 양.
    records = tuple(_record(i) for i in range(20_000))

    assert manager.export_async(records, str(target), "csv") is True

    # worker가 실제로 쓰기 시작할 때까지 잠깐 기다린 뒤 종료를 요청한다.
    deadline = time.monotonic() + 2.0
    while manager.has_pending_exports is False and time.monotonic() < deadline:
        time.sleep(0.005)

    manager.stop(timeout_ms=3000)

    for _ in range(50):
        qapp.processEvents()
        if failures:
            break
        time.sleep(0.01)

    if not target.exists():
        # 중단됐다면 반드시 이유가 표면화돼 있어야 한다.
        assert failures, (
            "export가 완료되지 않았는데 아무것도 알리지 않았다 — 조용한 유실이다"
        )
        assert "aborted" in failures[-1].lower()
        assert not list(tmp_path.glob("*.tmp")), "temporary file이 남았다"


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["", "   "])
def test_empty_path_is_rejected_with_the_intended_message(qapp, path):
    """
    빈 경로는 의도한 메시지로 거절돼야 한다.

    과거 가드 `if not str(Path(path))`는 `Path("")`가 `.`이 되어 **한 번도
    걸리지 않았다.** 빈 경로는 worker 안에서
    `ValueError: WindowsPath('.') has an empty name`으로 터졌다 — 사용자가
    원인을 알 수 없는 메시지다.
    """
    manager = PacketExportManager()
    failures: list[str] = []
    manager.export_failed.connect(failures.append)

    assert manager.export_async((_record(0),), path, "csv") is False

    assert failures == ["Export path must not be empty"], (
        f"의도한 메시지가 아니다: {failures}"
    )
    assert not manager.has_pending_exports, "거절했는데 worker가 떴다"
