"""
S-045 회귀/커버리지 테스트: DataLogger (core/data_logger.py)

## WHY
* `core/data_logger.py`는 기존 테스트가 0건이었다. PCAP/HEX 같은 바이너리 포맷은
  구조가 틀려도 파이썬 레벨에서는 예외 없이 "성공"하고, Wireshark 등 외부 도구를
  열어봐야만 깨진 것이 드러난다 — 그래서 여기서는 `struct.pack`으로 만들어진
  바이트를 다시 `struct.unpack`으로 직접 파싱해 포맷을 결정론적으로 검증한다.
* `stop_logging()`은 `join(timeout=1.0)` 후 타임아웃 여부와 무관하게 파일을 닫아,
  느린 디스크/대량 백로그 상황에서 배경 스레드가 쓰는 중인 파일을 메인이 닫아버려
  `ValueError: I/O operation on closed file` + 잔여 큐가 조용히 사라질 수 있었다
  (S-039의 TX 드레인 유실과 동일한 문제 패턴). 수정 후에는 (1) 정상 백로그는 상한
  내에 전부 드레인되고, (2) 상한을 초과하는 극단적 상황에서는 남은 개수를 경고
  로그로 표면화한 뒤에만 파일을 닫는다.

## WHAT
* BIN/HEX/PCAP 3개 포맷의 파일 산출물을 바이트/정규식 수준으로 검증.
* PCAP 글로벌 헤더(24B)와 패킷 헤더(16B)를 `struct.unpack`으로 직접 파싱.
* `stop_logging()`의 정상 드레인(유실 없음)과, 드레인 상한 초과 시 경고 표면화를
  결정론적으로 재현 (상수를 monkeypatch하여 테스트를 빠르게 유지).

## HOW
* 실제 스레드를 사용하는 `DataLogger`를 `tmp_path`에 직접 파일로 기록시키고,
  `stop_logging()`(블로킹 join)으로 종료를 기다린 뒤 파일을 다시 열어 검증한다.
* 상한 초과 경로는 `core.data_logger.DATA_LOGGER_STOP_DRAIN_TIMEOUT_S` /
  `..._FORCE_TIMEOUT_S`를 아주 작은 값으로 monkeypatch하고, `_file.write`를 느리게
  만들어 배경 스레드가 제 시간 안에 드레인을 끝내지 못하도록 강제한다.
"""
import re
import struct
import time

from core import data_logger as data_logger_module
from core.data_logger import DataLogger, DataLoggerManager
from common.enums import LogFormat


PCAP_GLOBAL_HEADER_FORMAT = "IHHIIII"  # magic, major, minor, thiszone, sigfigs, snaplen, network
PCAP_GLOBAL_HEADER_SIZE = struct.calcsize(PCAP_GLOBAL_HEADER_FORMAT)
PCAP_PACKET_HEADER_FORMAT = "IIII"  # ts_sec, ts_usec, incl_len, orig_len
PCAP_PACKET_HEADER_SIZE = struct.calcsize(PCAP_PACKET_HEADER_FORMAT)


# -----------------------------------------------------------------------------
# BIN 포맷
# -----------------------------------------------------------------------------

def test_bin_format_writes_raw_bytes_unmodified(tmp_path):
    """BIN 포맷은 가공 없이 원본 바이트를 그대로 파일에 기록한다."""
    file_path = str(tmp_path / "out.bin")
    dl = DataLogger()

    assert dl.start_logging(file_path, LogFormat.BIN) is True
    dl.write(b"\x00\x01\xff")
    dl.write(b"HELLO")
    dl.stop_logging()

    with open(file_path, "rb") as f:
        content = f.read()

    assert content == b"\x00\x01\xff" + b"HELLO"


# -----------------------------------------------------------------------------
# HEX 포맷
# -----------------------------------------------------------------------------

def test_hex_dump_line_format_matches_regex(tmp_path):
    """
    HEX 덤프 한 줄의 포맷이 `[HH:MM:SS.mmm] XX XX ...`인지 정규식으로 고정하고,
    실제 바이트 값이 대문자 2자리 HEX로 정확히 변환되는지 확인한다.
    """
    file_path = str(tmp_path / "out.hex.txt")
    dl = DataLogger()

    assert dl.start_logging(file_path, LogFormat.HEX) is True
    dl.write(bytes([0x00, 0x0A, 0xFF, 0x41]))  # -> "00 0A FF 41"
    dl.stop_logging()

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    assert len(lines) == 1
    line = lines[0]

    pattern = r"^\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})\] ([0-9A-F]{2}( [0-9A-F]{2})*)$"
    m = re.match(pattern, line)
    assert m is not None, f"HEX 라인 포맷 불일치: {line!r}"

    hh, mm, ss, ms, hex_body = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    assert 0 <= int(hh) <= 23
    assert 0 <= int(mm) <= 59
    assert 0 <= int(ss) <= 59
    assert 0 <= int(ms) <= 999
    assert hex_body == "00 0A FF 41"


def test_hex_dump_multiple_writes_produce_multiple_lines(tmp_path):
    """write() 호출마다 별도의 HEX 라인이 하나씩 생성된다 (병합되지 않음)."""
    file_path = str(tmp_path / "multi.hex.txt")
    dl = DataLogger()

    assert dl.start_logging(file_path, LogFormat.HEX) is True
    dl.write(b"\x01")
    dl.write(b"\x02")
    dl.write(b"\x03")
    dl.stop_logging()

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln]

    assert len(lines) == 3
    assert lines[0].endswith("01")
    assert lines[1].endswith("02")
    assert lines[2].endswith("03")


# -----------------------------------------------------------------------------
# PCAP 포맷 — struct.pack 바이트 직접 파싱 검증
# -----------------------------------------------------------------------------

def test_pcap_global_header_bytes_match_standard_format(tmp_path):
    """
    PCAP 글로벌 헤더(24바이트)를 `struct.unpack`으로 직접 파싱하여
    매직넘버/버전/스냅렌/네트워크 타입이 표준 PCAP 포맷과 일치하는지 확인한다.
    """
    file_path = str(tmp_path / "out.pcap")
    dl = DataLogger()

    assert dl.start_logging(file_path, LogFormat.PCAP) is True
    dl.stop_logging()  # 데이터 없이 헤더만 검증

    with open(file_path, "rb") as f:
        header_bytes = f.read(PCAP_GLOBAL_HEADER_SIZE)

    assert len(header_bytes) == PCAP_GLOBAL_HEADER_SIZE == 24

    magic, major, minor, thiszone, sigfigs, snaplen, network = struct.unpack(
        PCAP_GLOBAL_HEADER_FORMAT, header_bytes
    )
    assert magic == 0xA1B2C3D4  # microsecond-resolution magic
    assert major == 2
    assert minor == 4
    assert thiszone == 0
    assert sigfigs == 0
    assert snaplen == 65535
    assert network == 147  # DLT_USER0


def test_pcap_packet_header_and_payload_bytes_are_correct(tmp_path):
    """
    PCAP 패킷 레코드(헤더 16바이트 + 페이로드)를 직접 파싱하여
    ts_sec/ts_usec/incl_len/orig_len과 페이로드 바이트가 정확한지 확인한다.
    """
    file_path = str(tmp_path / "packet.pcap")
    dl = DataLogger()

    payload = b"PAYLOAD-DATA"

    before = time.time()
    assert dl.start_logging(file_path, LogFormat.PCAP) is True
    dl.write(payload)
    dl.stop_logging()
    after = time.time()

    with open(file_path, "rb") as f:
        data = f.read()

    # 글로벌 헤더 이후부터 패킷 레코드 시작
    packet_section = data[PCAP_GLOBAL_HEADER_SIZE:]
    assert len(packet_section) == PCAP_PACKET_HEADER_SIZE + len(payload)

    header_bytes = packet_section[:PCAP_PACKET_HEADER_SIZE]
    payload_bytes = packet_section[PCAP_PACKET_HEADER_SIZE:]

    ts_sec, ts_usec, incl_len, orig_len = struct.unpack(PCAP_PACKET_HEADER_FORMAT, header_bytes)

    assert incl_len == len(payload)
    assert orig_len == len(payload)
    assert 0 <= ts_usec < 1_000_000
    # 기록된 타임스탬프가 write() 호출 전후 구간 안에 있는지 확인 (초 단위 여유)
    assert int(before) - 1 <= ts_sec <= int(after) + 1
    assert payload_bytes == payload


def test_pcap_multiple_packets_are_written_in_order(tmp_path):
    """여러 패킷을 기록하면 순서대로 개별 레코드로 저장된다 (병합/누락 없음)."""
    file_path = str(tmp_path / "multi.pcap")
    dl = DataLogger()

    chunks = [b"AAA", b"BB", b"C"]

    assert dl.start_logging(file_path, LogFormat.PCAP) is True
    for c in chunks:
        dl.write(c)
    dl.stop_logging()

    with open(file_path, "rb") as f:
        data = f.read()

    offset = PCAP_GLOBAL_HEADER_SIZE
    parsed_payloads = []
    for _ in chunks:
        header_bytes = data[offset:offset + PCAP_PACKET_HEADER_SIZE]
        _, _, incl_len, orig_len = struct.unpack(PCAP_PACKET_HEADER_FORMAT, header_bytes)
        assert incl_len == orig_len
        offset += PCAP_PACKET_HEADER_SIZE
        parsed_payloads.append(data[offset:offset + incl_len])
        offset += incl_len

    assert parsed_payloads == chunks
    assert offset == len(data)  # 파일 끝까지 정확히 소비됨 (여분 바이트 없음)


# -----------------------------------------------------------------------------
# stop_logging() 잔여 큐 유실 방지 (결함 수정 검증)
# -----------------------------------------------------------------------------

def test_stop_logging_drains_full_backlog_without_loss(tmp_path):
    """
    정상적인(디스크가 느리지 않은) 상황에서 대량의 백로그를 쌓고 즉시
    stop_logging()을 호출해도, 기본 드레인 상한(1.0s) 안에 전부 기록되어야 한다
    (조용한 유실 없음 - 주요 케이스).
    """
    file_path = str(tmp_path / "backlog.bin")
    dl = DataLogger()

    assert dl.start_logging(file_path, LogFormat.BIN) is True

    chunk = b"X" * 32
    count = 500
    for _ in range(count):
        dl.write(chunk)

    dl.stop_logging()

    with open(file_path, "rb") as f:
        content = f.read()

    assert content == chunk * count
    assert dl._queue.qsize() == 0


def test_stop_logging_is_idempotent_and_safe_when_never_started():
    """로깅을 시작하지 않은 상태에서 stop_logging()을 호출해도 예외가 없다."""
    dl = DataLogger()
    dl.stop_logging()  # no-op, 예외 없이 통과해야 함
    assert dl.is_logging is False


def test_stop_logging_surfaces_warning_when_drain_exceeds_timeout(tmp_path, monkeypatch):
    """
    드레인이 상한을 초과하는 극단적 상황(디스크 매우 느림 등)을 재현한다.
    이때 stop_logging()은 (1) 무한 대기하지 않고, (2) 남은 큐 항목 수를
    조용히 버리지 않고 경고 로그로 표면화해야 한다 (S-039와 동일 원칙).
    """
    # 테스트를 빠르게 유지하기 위해 상한값을 아주 작게 monkeypatch
    monkeypatch.setattr(data_logger_module, "DATA_LOGGER_STOP_DRAIN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(data_logger_module, "DATA_LOGGER_STOP_FORCE_TIMEOUT_S", 0.05)

    warnings = []
    monkeypatch.setattr(data_logger_module.logger, "warning", lambda msg: warnings.append(msg))

    file_path = str(tmp_path / "slow.bin")
    dl = DataLogger()
    assert dl.start_logging(file_path, LogFormat.BIN) is True

    # 파일 쓰기를 인위적으로 느리게 만들어(각 write마다 0.2초) 드레인이
    # DATA_LOGGER_STOP_DRAIN_TIMEOUT_S(0.05s) 안에 끝나지 못하도록 강제한다.
    real_write = dl._file.write

    def _slow_write(data):
        time.sleep(0.2)
        return real_write(data)

    dl._file.write = _slow_write

    for _ in range(50):
        dl.write(b"Y")

    start = time.monotonic()
    dl.stop_logging()
    elapsed = time.monotonic() - start

    # 무한 대기 금지: 두 상한(0.05 + 0.05)을 크게 초과하지 않아야 함
    assert elapsed < 5.0

    # 조용한 유실 금지: 경고가 정확히 표면화되어야 함
    assert len(warnings) == 1
    assert "discarded" in warnings[0]
    # 남은 개수가 메시지에 포함되어야 함(정확한 수치까지는 타이밍 의존적이므로
    # "숫자 + queued item(s) discarded" 패턴만 확인)
    assert re.search(r"\d+ queued item\(s\) discarded", warnings[0])

    # 강제 종료 후에도 파일이 정상적으로 닫혀 있어야 함 (핸들 유실 없음)
    assert dl._file is None


def test_stop_logging_force_path_does_not_hang_thread(tmp_path, monkeypatch):
    """
    강제 종료 경로를 타더라도 배경 스레드가 결국 종료되어야 한다
    (thread leak 방지 - 다음 로거가 파일을 다시 열 수 있어야 함).
    """
    monkeypatch.setattr(data_logger_module, "DATA_LOGGER_STOP_DRAIN_TIMEOUT_S", 0.05)
    monkeypatch.setattr(data_logger_module, "DATA_LOGGER_STOP_FORCE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(data_logger_module.logger, "warning", lambda msg: None)

    file_path = str(tmp_path / "slow2.bin")
    dl = DataLogger()
    assert dl.start_logging(file_path, LogFormat.BIN) is True

    real_write = dl._file.write

    def _slow_write(data):
        time.sleep(0.05)
        return real_write(data)

    dl._file.write = _slow_write

    for _ in range(20):
        dl.write(b"Z")

    dl.stop_logging()

    # 강제 플래그가 설정된 뒤에는 루프가 곧 빠져나와 스레드가 살아있지 않아야 함
    thread = dl._thread
    if thread is not None:
        thread.join(timeout=2.0)
        assert not thread.is_alive()


# -----------------------------------------------------------------------------
# DataLoggerManager (다중 포트 위임)
# -----------------------------------------------------------------------------

def test_manager_start_stop_and_is_logging_roundtrip(tmp_path):
    """DataLoggerManager가 포트별 DataLogger 생성/조회/종료를 올바르게 위임한다."""
    manager = DataLoggerManager()
    file_path = str(tmp_path / "port.bin")

    assert manager.is_logging("COM1") is False
    assert manager.start_logging("COM1", file_path, LogFormat.BIN) is True
    assert manager.is_logging("COM1") is True
    assert manager.get_filepath("COM1") == file_path

    manager.write("COM1", b"abc")
    manager.stop_logging("COM1")

    assert manager.is_logging("COM1") is False
    assert manager.get_filepath("COM1") == ""

    with open(file_path, "rb") as f:
        assert f.read() == b"abc"


def test_manager_stop_all_stops_every_active_logger(tmp_path):
    """stop_all()은 등록된 모든 포트의 로거를 중단시킨다."""
    manager = DataLoggerManager()

    manager.start_logging("P1", str(tmp_path / "p1.bin"), LogFormat.BIN)
    manager.start_logging("P2", str(tmp_path / "p2.bin"), LogFormat.BIN)

    assert manager.is_logging("P1") is True
    assert manager.is_logging("P2") is True

    manager.stop_all()

    assert manager.is_logging("P1") is False
    assert manager.is_logging("P2") is False


def test_manager_write_to_unknown_port_is_noop():
    """등록되지 않은 포트에 write()를 호출해도 예외가 발생하지 않는다."""
    manager = DataLoggerManager()
    manager.write("UNKNOWN", b"data")  # no-op, 예외 없어야 함
