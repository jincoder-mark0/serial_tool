"""Tests for the packet parser implementations currently supported by SerialTool."""

import pytest

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
