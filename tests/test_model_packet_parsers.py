"""Tests for the packet parser implementations currently supported by SerialTool."""

from unittest.mock import MagicMock

import pytest

from common.constants import BATCH_SIZE_THRESHOLD, PARSER_MAX_BUFFER_SIZE
from common.enums import ParserType
from model.packet_parser import (
    ATParser,
    DelimiterParser,
    FixedLengthParser,
    ParserFactory,
    RawParser,
)


def test_raw_parser_passes_data_through():
    packets = RawParser().parse(b"\x01\x02\x03")

    assert len(packets) == 1
    assert packets[0].data == b"\x01\x02\x03"


def test_raw_parser_ignores_empty_data():
    assert RawParser().parse(b"") == []


def test_at_parser_reassembles_fragmented_lines():
    parser = ATParser()

    assert parser.parse(b"O") == []
    packets = parser.parse(b"K\r\nERROR\r\n")

    assert [packet.data for packet in packets] == [b"OK\r\n", b"ERROR\r\n"]
    assert all(packet.metadata == {"type": "AT"} for packet in packets)


def test_delimiter_parser_reassembles_fragmented_packets():
    parser = DelimiterParser(b"\x00\xff")

    assert parser.parse(b"first\x00") == []
    packets = parser.parse(b"\xffsecond\x00\xff")

    assert [packet.data for packet in packets] == [
        b"first\x00\xff",
        b"second\x00\xff",
    ]


def test_fixed_length_parser_buffers_remainder():
    parser = FixedLengthParser(3)

    first_packets = parser.parse(b"abcde")
    second_packets = parser.parse(b"f")

    assert [packet.data for packet in first_packets] == [b"abc"]
    assert [packet.data for packet in second_packets] == [b"def"]


@pytest.mark.parametrize(
    ("factory_type", "expected_type", "kwargs"),
    [
        (ParserType.RAW, RawParser, {}),
        (ParserType.AT, ATParser, {}),
        (ParserType.DELIMITER, DelimiterParser, {"delimiter": b"|"}),
        (ParserType.FIXED_LENGTH, FixedLengthParser, {"length": 4}),
    ],
)
def test_parser_factory_creates_supported_parsers(factory_type, expected_type, kwargs):
    assert isinstance(ParserFactory.create_parser(factory_type, **kwargs), expected_type)


def test_parser_factory_falls_back_to_raw_parser():
    assert isinstance(ParserFactory.create_parser("unknown"), RawParser)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DelimiterParser(b""),
        lambda: DelimiterParser(b"\n", max_buffer_size=0),
        lambda: FixedLengthParser(0),
        lambda: FixedLengthParser(-1),
        lambda: FixedLengthParser(1, max_buffer_size=0),
    ],
)
def test_framed_parsers_reject_invalid_configuration(factory):
    with pytest.raises(ValueError):
        factory()


# =============================================================================
# S-064 — 버퍼 잘라내기 순서로 인한 완결 패킷 유실 회귀 테스트
#
# 원인: parse()가 "① 버퍼 크기 제한 적용 → ② 구분자/길이로 분리" 순서였다.
# 워커의 배치 임계값(BATCH_SIZE_THRESHOLD=8192)이 파서의 max_buffer_size 기본값보다
# 커서, 한 번에 큰 배치가 들어오면 구분자가 정상적으로 와 있어도 분리되기 전에
# 잘려나가 완결 패킷이 사라졌다. 수정 후에는 "① 분리 → ② 남은 미완결 조각에만
# 크기 제한 적용" 순서가 되어, max_buffer_size를 아주 작게 줘도(=강제로 잘라내기
# 분기를 타게 해도) 이미 완결된 패킷은 하나도 사라지지 않아야 한다.
# =============================================================================

class TestBufferTruncationDoesNotDropCompletedPackets:
    """완결 패킷은 버퍼 상한과 무관하게 전부 살아남아야 한다."""

    def test_delimiter_parser_survives_batch_larger_than_batch_threshold(self):
        """구분자로 끝나는 패킷들로만 채운 배치(>BATCH_SIZE_THRESHOLD)를 한 번에 넣어도
        전부 분리되어야 한다 — max_buffer_size를 극단적으로 작게 줘서 잘라내기 분기가
        반드시 실행되도록 강제한다."""
        parser = DelimiterParser(b"\n", max_buffer_size=64)

        count = 2000
        payload = b"".join(f"line{i:04d}\n".encode() for i in range(count))
        assert len(payload) > BATCH_SIZE_THRESHOLD  # 시나리오 전제 확인

        packets = parser.parse(payload)

        assert len(packets) == count
        assert packets[0].data == b"line0000\n"
        assert packets[-1].data == f"line{count - 1:04d}\n".encode()

    def test_at_parser_survives_batch_larger_than_batch_threshold(self):
        """AT 파서도 동일한 시나리오에서 완결 라인을 하나도 잃지 않아야 한다."""
        parser = ATParser(max_buffer_size=64)

        count = 1500
        payload = b"".join(f"+RESP:{i:04d}\r\n".encode() for i in range(count))
        assert len(payload) > BATCH_SIZE_THRESHOLD

        packets = parser.parse(payload)

        assert len(packets) == count
        assert packets[0].data == b"+RESP:0000\r\n"
        assert packets[-1].data == f"+RESP:{count - 1:04d}\r\n".encode()

    def test_fixed_length_parser_survives_batch_larger_than_batch_threshold(self):
        """고정 길이 파서도 길이 경계에 정확히 맞춘 배치를 넣으면 완결 청크를
        하나도 잃지 않아야 한다."""
        length = 8
        parser = FixedLengthParser(length, max_buffer_size=64)

        count = 1200
        payload = b"".join(f"{i:07d}\n".encode() for i in range(count))
        assert len(payload) == count * length
        assert len(payload) > BATCH_SIZE_THRESHOLD

        packets = parser.parse(payload)

        assert len(packets) == count
        assert packets[0].data == f"{0:07d}\n".encode()
        assert packets[-1].data == f"{count - 1:07d}\n".encode()


class TestBufferTruncationWarnsAndBoundsMemory:
    """상한을 넘는 '진짜 미완결' 조각은 조용히 버리지 않고 경고하며, 메모리 보호는 유지된다."""

    def test_delimiter_parser_warns_when_incomplete_tail_exceeds_cap(self, monkeypatch):
        mock_logger = MagicMock()
        monkeypatch.setattr("model.packet_parser.logger", mock_logger)

        parser = DelimiterParser(b"\n", max_buffer_size=16)
        garbage = b"x" * 100  # 구분자가 전혀 없는 미완결 조각

        packets = parser.parse(garbage)

        assert packets == []
        mock_logger.warning.assert_called_once()
        assert len(parser._buffer) == 16
        assert parser._buffer == garbage[-16:]

    def test_at_parser_warns_when_incomplete_tail_exceeds_cap(self, monkeypatch):
        mock_logger = MagicMock()
        monkeypatch.setattr("model.packet_parser.logger", mock_logger)

        parser = ATParser(max_buffer_size=16)
        garbage = b"x" * 100

        packets = parser.parse(garbage)

        assert packets == []
        mock_logger.warning.assert_called_once()
        assert len(parser._buffer) == 16

    def test_fixed_length_parser_warns_when_incomplete_tail_exceeds_cap(self, monkeypatch):
        mock_logger = MagicMock()
        monkeypatch.setattr("model.packet_parser.logger", mock_logger)

        parser = FixedLengthParser(length=1000, max_buffer_size=16)
        garbage = b"x" * 100  # length(1000)에 못 미쳐 영원히 미완결인 조각

        packets = parser.parse(garbage)

        assert packets == []
        mock_logger.warning.assert_called_once()
        assert len(parser._buffer) == 16

    def test_delimiter_parser_buffer_stays_bounded_across_many_calls(self):
        """구분자 없는 폭주 스트림을 여러 번 나눠 넣어도 내부 버퍼가 max_buffer_size를
        넘지 않는다 (기존 메모리 보호 회귀 고정)."""
        parser = DelimiterParser(b"\n", max_buffer_size=64)

        for _ in range(50):
            packets = parser.parse(b"y" * 1000)
            assert packets == []
            assert len(parser._buffer) <= 64

    def test_parsers_default_max_buffer_size_is_the_shared_constant(self):
        """기본값은 매직 넘버가 아니라 common/constants.py의 공용 상수를 따른다."""
        assert DelimiterParser(b"\n")._max_buffer_size == PARSER_MAX_BUFFER_SIZE
        assert ATParser()._max_buffer_size == PARSER_MAX_BUFFER_SIZE
        assert FixedLengthParser(4)._max_buffer_size == PARSER_MAX_BUFFER_SIZE
