"""완결 Packet DTO 이후에 적용하는 declarative packet filter engine.

## WHY
* Raw RX Fast Path를 건드리지 않고 Packet Parser가 확정한 packet만 filtering
* arbitrary Python expression 없이 predictable / testable rule 제공
* malformed filter가 RX/connection runtime을 깨지 않도록 compile 단계에서 검증

## HOW
* semicolon(`;`)으로 rule을 분리하고 모든 rule을 AND로 평가
* compile 결과는 immutable `CompiledPacketFilter`로 보존
* packet data/type/port/checksum snapshot만 읽고 원본 Packet을 mutation하지 않음

지원 DSL
--------
* `port=COM3`
* `type=AT`
* `len=8` / `len=8..32`
* `hex*=DE AD`       : byte sequence contains
* `hex^=AA55`        : byte sequence prefix
* `ascii*=OK`        : text contains (latin-1 1:1 decode)
* `ascii^=AT+`       : text prefix
* `byte[0]=0xAA`
* `byte[1]=10..20`
* `byte[0]&0xF0=0xA0`
* `checksum=ok|fail|none`
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


class PacketFilterSyntaxError(ValueError):
    """사용자가 입력한 declarative filter rule이 유효하지 않을 때 발생."""


@dataclass(frozen=True)
class PacketFilterContext:
    """Filter Engine이 읽는 완결 packet snapshot.

    Packet parser 구현이나 QWidget을 직접 참조하지 않아 filter가 독립적으로
    unit-test 가능하도록 경계를 고정한다.
    """

    port: str
    packet_type: str
    data: bytes
    checksum_ok: Optional[bool] = None


@dataclass(frozen=True)
class PacketFilterRule:
    """compile된 단일 declarative rule."""

    kind: str
    operator: str = "eq"
    text_value: str = ""
    bytes_value: bytes = b""
    offset: int = -1
    lower: int = 0
    upper: int = 0
    mask: Optional[int] = None
    checksum_value: Optional[bool] = None

    def matches(self, context: PacketFilterContext) -> bool:
        """Rule 종류별로 packet snapshot과 일치하는지 반환한다."""
        if self.kind == "port":
            return context.port.casefold() == self.text_value.casefold()

        if self.kind == "type":
            return context.packet_type.casefold() == self.text_value.casefold()

        if self.kind == "length":
            return self.lower <= len(context.data) <= self.upper

        if self.kind == "hex":
            if self.operator == "contains":
                return self.bytes_value in context.data
            return context.data.startswith(self.bytes_value)

        if self.kind == "ascii":
            text = context.data.decode("latin-1")
            if self.operator == "contains":
                return self.text_value in text
            return text.startswith(self.text_value)

        if self.kind == "byte":
            if self.offset < 0 or self.offset >= len(context.data):
                return False
            value = context.data[self.offset]
            if self.mask is not None:
                return (value & self.mask) == self.lower
            return self.lower <= value <= self.upper

        if self.kind == "checksum":
            return context.checksum_ok is self.checksum_value

        # compile()을 통하지 않은 잘못된 rule object도 fail-closed 처리.
        return False


@dataclass(frozen=True)
class CompiledPacketFilter:
    """검증된 rule collection. Rule은 모두 AND 조건으로 평가한다."""

    source: str
    rules: tuple[PacketFilterRule, ...]

    def matches(self, context: PacketFilterContext) -> bool:
        return all(rule.matches(context) for rule in self.rules)


class PacketFilterEngine:
    """사용자 DSL을 immutable filter로 compile하는 stateless engine."""

    _BYTE_RULE_RE = re.compile(
        r"^byte\[(?P<offset>\d+)\]"
        r"(?:&(?P<mask>[^=]+))?="
        r"(?P<value>.+)$",
        re.IGNORECASE,
    )

    @classmethod
    def compile(cls, expression: str) -> CompiledPacketFilter:
        """Filter DSL을 검증/compile한다.

        Empty expression은 rule 0개의 pass-through filter다. Syntax error는
        `PacketFilterSyntaxError`로 통일해 Presenter가 기존 valid filter를 유지하면서
        사용자에게 오류만 표시할 수 있게 한다.
        """
        source = expression.strip()
        if not source:
            return CompiledPacketFilter(source="", rules=())

        rules: list[PacketFilterRule] = []
        for raw_clause in source.split(";"):
            clause = raw_clause.strip()
            if not clause:
                raise PacketFilterSyntaxError("empty filter clause")
            rules.append(cls._compile_clause(clause))

        return CompiledPacketFilter(source=source, rules=tuple(rules))

    @classmethod
    def _compile_clause(cls, clause: str) -> PacketFilterRule:
        lowered = clause.casefold()

        if lowered.startswith("port="):
            value = clause.split("=", 1)[1].strip()
            return cls._text_equality_rule("port", value)

        if lowered.startswith("type="):
            value = clause.split("=", 1)[1].strip()
            return cls._text_equality_rule("type", value)

        if lowered.startswith("len="):
            value = clause.split("=", 1)[1].strip()
            lower, upper = cls._parse_range(value, minimum=0, maximum=None)
            return PacketFilterRule(kind="length", lower=lower, upper=upper)

        if lowered.startswith("hex*="):
            value = clause.split("=", 1)[1].strip()
            return PacketFilterRule(
                kind="hex",
                operator="contains",
                bytes_value=cls._parse_hex_bytes(value),
            )

        if lowered.startswith("hex^="):
            value = clause.split("=", 1)[1].strip()
            return PacketFilterRule(
                kind="hex",
                operator="prefix",
                bytes_value=cls._parse_hex_bytes(value),
            )

        if lowered.startswith("ascii*="):
            value = clause.split("=", 1)[1]
            return cls._ascii_rule("contains", value)

        if lowered.startswith("ascii^="):
            value = clause.split("=", 1)[1]
            return cls._ascii_rule("prefix", value)

        if lowered.startswith("checksum="):
            value = clause.split("=", 1)[1].strip().casefold()
            mapping = {"ok": True, "fail": False, "none": None}
            if value not in mapping:
                raise PacketFilterSyntaxError(
                    "checksum value must be one of: ok, fail, none"
                )
            return PacketFilterRule(
                kind="checksum",
                checksum_value=mapping[value],
            )

        byte_match = cls._BYTE_RULE_RE.fullmatch(clause)
        if byte_match:
            return cls._compile_byte_rule(byte_match)

        raise PacketFilterSyntaxError(f"unsupported filter clause: {clause}")

    @staticmethod
    def _text_equality_rule(kind: str, value: str) -> PacketFilterRule:
        if not value:
            raise PacketFilterSyntaxError(f"{kind} value must not be empty")
        return PacketFilterRule(kind=kind, text_value=value)

    @staticmethod
    def _ascii_rule(operator: str, value: str) -> PacketFilterRule:
        if value == "":
            raise PacketFilterSyntaxError("ascii filter value must not be empty")
        return PacketFilterRule(
            kind="ascii",
            operator=operator,
            text_value=value,
        )

    @classmethod
    def _compile_byte_rule(cls, match: re.Match[str]) -> PacketFilterRule:
        offset = int(match.group("offset"))
        mask_text = match.group("mask")
        value_text = match.group("value").strip()

        if mask_text is not None:
            if ".." in value_text:
                raise PacketFilterSyntaxError("masked byte rule does not support range")
            mask = cls._parse_byte_number(mask_text.strip())
            expected = cls._parse_byte_number(value_text)
            if expected & ~mask:
                raise PacketFilterSyntaxError(
                    "masked byte expected value contains bit outside mask"
                )
            return PacketFilterRule(
                kind="byte",
                offset=offset,
                lower=expected,
                upper=expected,
                mask=mask,
            )

        lower, upper = cls._parse_range(value_text, minimum=0, maximum=0xFF)
        return PacketFilterRule(
            kind="byte",
            offset=offset,
            lower=lower,
            upper=upper,
        )

    @classmethod
    def _parse_range(
        cls,
        text: str,
        *,
        minimum: int,
        maximum: Optional[int],
    ) -> tuple[int, int]:
        parts = [part.strip() for part in text.split("..")]
        if len(parts) not in (1, 2) or any(part == "" for part in parts):
            raise PacketFilterSyntaxError(f"invalid numeric range: {text}")

        lower = cls._parse_number(parts[0])
        upper = cls._parse_number(parts[-1])

        if lower > upper:
            raise PacketFilterSyntaxError("range lower bound must be <= upper bound")
        if lower < minimum or (maximum is not None and upper > maximum):
            limit = f"{minimum}..{maximum}" if maximum is not None else f">={minimum}"
            raise PacketFilterSyntaxError(f"range must be within {limit}")
        return lower, upper

    @staticmethod
    def _parse_number(text: str) -> int:
        """일반 numeric field는 decimal, `0x` prefix만 hex로 해석한다."""
        try:
            return int(text, 0) if text.lower().startswith("0x") else int(text, 10)
        except ValueError as exc:
            raise PacketFilterSyntaxError(f"invalid number: {text}") from exc

    @classmethod
    def _parse_byte_number(cls, text: str) -> int:
        """Byte/mask 값은 decimal 또는 0x-prefixed hex를 허용한다."""
        value = cls._parse_number(text)
        if not 0 <= value <= 0xFF:
            raise PacketFilterSyntaxError("byte value must be within 0..255")
        return value

    @staticmethod
    def _parse_hex_bytes(text: str) -> bytes:
        """`AA55`, `AA 55`, `AA_55` 형태의 HEX byte sequence를 허용한다."""
        normalized = text.replace(" ", "").replace("_", "")
        if not normalized:
            raise PacketFilterSyntaxError("hex filter value must not be empty")
        if len(normalized) % 2:
            raise PacketFilterSyntaxError("hex filter value must contain complete bytes")
        try:
            return bytes.fromhex(normalized)
        except ValueError as exc:
            raise PacketFilterSyntaxError(f"invalid hex byte sequence: {text}") from exc
