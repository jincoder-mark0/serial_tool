"""
포트별 packet parser 세션 관리자.

ConnectionController에서 parser 생성 옵션 변환, parser registry, feed/flush 책임을
분리합니다. 연결 계층은 raw data와 PortConfig만 전달하고 parser 구현 세부사항을
알지 않습니다.
"""
from typing import Any, Dict, List

from common.dtos import PortConfig
from common.enums import ParserType
from model.packet_parser import Packet, PacketParser, ParserFactory


class PacketParserManager:
    """포트 이름을 key로 PacketParser의 생성/입력/종료 flush를 관리합니다."""

    def __init__(self) -> None:
        self._parsers: Dict[str, PacketParser] = {}

    def configure(self, port_name: str, config: PortConfig) -> None:
        """PortConfig에 맞는 parser를 생성해 해당 포트 세션에 등록합니다."""
        parser_type = ParserType.from_preference_index(config.parser_type)
        kwargs = self._build_parser_kwargs(parser_type, config)
        self._parsers[port_name] = ParserFactory.create_parser(parser_type, **kwargs)

    def feed(self, port_name: str, data: bytes) -> List[Packet]:
        """해당 포트 parser에 raw data를 공급하고 완성된 packet들을 반환합니다."""
        parser = self._parsers.get(port_name)
        if parser is None or not data:
            return []
        return list(parser.parse(data))

    def remove(self, port_name: str) -> List[Packet]:
        """parser 세션을 제거하며 내부에 남은 packet을 flush해 반환합니다."""
        parser = self._parsers.pop(port_name, None)
        if parser is None:
            return []
        return list(parser.flush())

    def has_parser(self, port_name: str) -> bool:
        """테스트/진단용으로 parser 세션 존재 여부를 반환합니다."""
        return port_name in self._parsers

    @staticmethod
    def _build_parser_kwargs(parser_type: str, config: PortConfig) -> Dict[str, Any]:
        if parser_type == ParserType.DELIMITER:
            return {
                "delimiter": PacketParserManager._decode_delimiter(
                    config.packet_delimiter
                )
            }
        if parser_type == ParserType.FIXED_LENGTH:
            return {"length": config.packet_length}
        if parser_type == ParserType.LENGTH_FIELD:
            return {
                "length_field_offset": config.length_field_offset,
                "length_field_size": config.length_field_size,
                "length_field_endian": config.length_field_endian,
                "length_includes_header": config.length_includes_header,
            }
        if parser_type == ParserType.GAP:
            return {"gap_ms": config.gap_ms}
        return {}

    @staticmethod
    def _decode_delimiter(raw: str) -> bytes:
        if not raw:
            return b""
        try:
            return raw.encode("utf-8").decode("unicode_escape").encode("latin-1")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return raw.encode("utf-8")
