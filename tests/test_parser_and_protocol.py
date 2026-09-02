"""
파서 설정 반영 및 미구현 프로토콜(SPI) 거부 검증.

ConnectionController는 parser registry를 직접 소유하지 않으며 PacketParserManager에
PortConfig를 전달합니다. 테스트도 manager의 public 진단 API를 사용합니다.
"""
from unittest.mock import MagicMock

import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig
from common.enums import ConnectionProtocol
from model.connection_controller import ConnectionController
from model.packet_parser import (
    ATParser,
    DelimiterParser,
    FixedLengthParser,
    GapParser,
    LengthFieldParser,
    RawParser,
)
from model.packet_parser_manager import PacketParserManager


def _loopback_config(**overrides) -> PortConfig:
    return PortConfig(port=LOOPBACK_PORT_NAME, **overrides)


class TestParserSettingsWiring:
    @pytest.mark.parametrize(
        "parser_type_index, extra_kwargs, expected_cls",
        [
            (0, {}, RawParser),
            (1, {}, ATParser),
            (2, {"packet_delimiter": "\\r\\n"}, DelimiterParser),
            (3, {"packet_length": 8}, FixedLengthParser),
            (4, {}, RawParser),
            (5, {"length_field_offset": 0, "length_field_size": 1}, LengthFieldParser),
            (6, {"gap_ms": 7}, GapParser),
        ],
    )
    def test_open_connection_configures_parser_manager(
        self,
        parser_type_index,
        extra_kwargs,
        expected_cls,
    ):
        parser_manager = PacketParserManager()
        controller = ConnectionController(parser_manager)
        config = _loopback_config(parser_type=parser_type_index, **extra_kwargs)
        try:
            assert controller.open_connection(config) is True
            assert isinstance(
                parser_manager.get_parser(LOOPBACK_PORT_NAME),
                expected_cls,
            )
        finally:
            controller.close_all_and_wait()

    def test_invalid_delimiter_is_not_silently_swallowed(self):
        parser_manager = PacketParserManager()
        controller = ConnectionController(parser_manager)
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        result = controller.open_connection(
            _loopback_config(parser_type=2, packet_delimiter="")
        )

        assert result is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        assert not parser_manager.has_parser(LOOPBACK_PORT_NAME)
        error_spy.assert_called_once()
        assert "parser" in error_spy.call_args[0][0].message.lower()

    def test_invalid_fixed_length_is_not_silently_swallowed(self):
        parser_manager = PacketParserManager()
        controller = ConnectionController(parser_manager)
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        result = controller.open_connection(
            _loopback_config(parser_type=3, packet_length=0)
        )

        assert result is False
        assert not parser_manager.has_parser(LOOPBACK_PORT_NAME)
        error_spy.assert_called_once()


class TestUnimplementedProtocolRejection:
    def test_spi_protocol_is_rejected_explicitly(self):
        controller = ConnectionController()
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        result = controller.open_connection(
            _loopback_config(protocol=ConnectionProtocol.SPI)
        )

        assert result is False
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        error_spy.assert_called_once()
        event = error_spy.call_args[0][0]
        assert event.port == LOOPBACK_PORT_NAME
        assert "SPI" in event.message


class TestDefaultSerialRegression:
    def test_default_config_opens_with_raw_parser_over_serial_protocol(self):
        parser_manager = PacketParserManager()
        controller = ConnectionController(parser_manager)
        config = _loopback_config()

        try:
            assert config.protocol == ConnectionProtocol.SERIAL
            assert controller.open_connection(config) is True
            assert isinstance(
                parser_manager.get_parser(LOOPBACK_PORT_NAME),
                RawParser,
            )
        finally:
            controller.close_all_and_wait()
