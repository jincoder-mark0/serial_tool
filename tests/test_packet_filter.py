"""Structured Packet Filter pure engine regression tests."""
import pytest

from model.packet_filter import (
    PacketFilterContext,
    PacketFilterEngine,
    PacketFilterSyntaxError,
)


def _context(
    *,
    port: str = "COM3",
    packet_type: str = "AT",
    data: bytes = b"AT+OK\r\n",
    checksum_ok=None,
) -> PacketFilterContext:
    return PacketFilterContext(
        port=port,
        packet_type=packet_type,
        data=data,
        checksum_ok=checksum_ok,
    )


def test_empty_expression_is_pass_through():
    compiled = PacketFilterEngine.compile("")
    assert compiled.matches(_context()) is True
    assert compiled.rules == ()


def test_multiple_clauses_use_and_semantics():
    compiled = PacketFilterEngine.compile("port=com3; type=at; len=7; ascii*=OK")

    assert compiled.matches(_context(data=b"AT+OK\r\n")) is True
    assert compiled.matches(_context(port="COM4", data=b"AT+OK\r\n")) is False
    assert compiled.matches(_context(data=b"AT+NG\r\n")) is False


def test_hex_contains_and_prefix_ignore_spacing():
    contains = PacketFilterEngine.compile("hex*=DE AD")
    prefix = PacketFilterEngine.compile("hex^=AA_55")

    assert contains.matches(_context(data=b"\x00\xde\xad\xff")) is True
    assert prefix.matches(_context(data=b"\xaa\x55\x01")) is True
    assert prefix.matches(_context(data=b"\x00\xaa\x55")) is False


def test_numeric_range_and_byte_range():
    length_rule = PacketFilterEngine.compile("len=3..5")
    byte_rule = PacketFilterEngine.compile("byte[1]=16..31")

    assert length_rule.matches(_context(data=b"1234")) is True
    assert length_rule.matches(_context(data=b"12")) is False
    assert byte_rule.matches(_context(data=bytes([0x00, 0x10]))) is True
    assert byte_rule.matches(_context(data=bytes([0x00, 0x20]))) is False
    assert byte_rule.matches(_context(data=b"\x00")) is False


def test_masked_byte_condition():
    compiled = PacketFilterEngine.compile("byte[0]&0xF0=0xA0")

    assert compiled.matches(_context(data=b"\xab")) is True
    assert compiled.matches(_context(data=b"\x9f")) is False


@pytest.mark.parametrize(
    ("expression", "value"),
    [("checksum=ok", True), ("checksum=fail", False), ("checksum=none", None)],
)
def test_checksum_filter(expression, value):
    compiled = PacketFilterEngine.compile(expression)
    assert compiled.matches(_context(checksum_ok=value)) is True


def test_type_and_port_equality_are_case_insensitive():
    compiled = PacketFilterEngine.compile("type=at; port=com3")
    assert compiled.matches(_context(packet_type="AT", port="COM3")) is True


@pytest.mark.parametrize(
    "expression",
    [
        ";",
        "len=9..3",
        "len=-1",
        "hex*=A",
        "hex*=GG",
        "ascii*=",
        "byte[0]=256",
        "byte[0]&0xF0=0xAF",
        "checksum=maybe",
        "unknown=value",
    ],
)
def test_malformed_rules_fail_during_compile(expression):
    with pytest.raises(PacketFilterSyntaxError):
        PacketFilterEngine.compile(expression)
