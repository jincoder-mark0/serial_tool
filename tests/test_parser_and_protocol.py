"""
파서 설정 반영 및 미구현 프로토콜(SPI) 거부 검증 모듈 (S-041)

## WHY
* `model/connection_controller.py`가 Preferences의 패킷 파서 설정을 무시하고
  항상 `RawParser`만 생성하던 결함(B-1)의 회귀 방지.
* `PortConfig.protocol`이 "SPI"여도 `SpiTransport`가 없어 조용히
  `SerialTransport`로 연결을 시도하던 결함(B-2)의 회귀 방지.

## WHAT
* `PortConfig.parser_type`/`packet_delimiter`/`packet_length` 조합별로
  `ConnectionController.open_connection()`이 생성하는 `PacketParser` 타입이
  설정과 일치하는지 검증한다.
* 잘못된 파서 파라미터(빈 delimiter, 0 이하 length)가 조용히 실패하지 않고
  `error_occurred` 시그널로 표면화되는지 검증한다.
* `protocol="SPI"`로 열기 시도 시 연결이 시도되지 않고 명시적으로 거부되는지
  검증한다.
* 설정을 건드리지 않은 기본(Serial/Raw) 경로가 회귀하지 않는지 검증한다.

## HOW
* 실제 시리얼 장비 없이 `LOOPBACK_PORT_NAME` 더미 포트로 `ConnectionController`를
  직접 구동한다 (Model 계층 단위 검증 — Presenter의 설정 조회는 범위 밖).
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


def _loopback_config(**overrides) -> PortConfig:
    """LOOPBACK 더미 포트용 PortConfig DTO를 생성한다 (파서 설정 오버라이드 지원)."""
    return PortConfig(port=LOOPBACK_PORT_NAME, **overrides)


# =============================================================================
# ① 파서 설정 반영 검증
# =============================================================================

class TestParserSettingsWiring:
    """Preferences에서 고른 파서 타입이 실제로 open_connection()에 적용되는지 검증."""

    @pytest.mark.parametrize(
        "parser_type_index, extra_kwargs, expected_cls",
        [
            (0, {}, RawParser),                                  # Auto -> Raw (자동 감지 미구현)
            (1, {}, ATParser),
            (2, {"packet_delimiter": "\\r\\n"}, DelimiterParser),
            (3, {"packet_length": 8}, FixedLengthParser),
            (4, {}, RawParser),
            # S-072 — 프레이밍 확장
            (5, {"length_field_offset": 0, "length_field_size": 1}, LengthFieldParser),
            (6, {"gap_ms": 7}, GapParser),
        ],
    )
    def test_open_connection_creates_configured_parser(self, parser_type_index, extra_kwargs, expected_cls):
        """설정된 parser_type 인덱스에 맞는 PacketParser 인스턴스가 생성된다."""
        controller = ConnectionController()
        config = _loopback_config(parser_type=parser_type_index, **extra_kwargs)
        try:
            assert controller.open_connection(config) is True
            assert isinstance(controller.parsers[LOOPBACK_PORT_NAME], expected_cls)
        finally:
            controller.close_connection()

    def test_invalid_delimiter_is_not_silently_swallowed(self):
        """빈 delimiter로 Delimiter 파서를 선택하면 연결이 거부되고 에러가 사용자에게 표면화된다."""
        controller = ConnectionController()
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        config = _loopback_config(parser_type=2, packet_delimiter="")

        result = controller.open_connection(config)

        assert result is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        error_spy.assert_called_once()
        event = error_spy.call_args[0][0]
        assert event.port == LOOPBACK_PORT_NAME
        assert "parser" in event.message.lower()

    def test_invalid_fixed_length_is_not_silently_swallowed(self):
        """0 이하 length로 FixedLength 파서를 선택하면 연결이 거부되고 에러가 사용자에게 표면화된다."""
        controller = ConnectionController()
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        config = _loopback_config(parser_type=3, packet_length=0)

        result = controller.open_connection(config)

        assert result is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        error_spy.assert_called_once()


# =============================================================================
# ② 미구현 프로토콜(SPI) 명시적 거부 검증
# =============================================================================

class TestUnimplementedProtocolRejection:
    """SPI 선택 시 조용히 Serial로 연결되지 않고 명시적으로 거부되는지 검증."""

    def test_spi_protocol_is_rejected_explicitly(self):
        """protocol='SPI'로 열기 시도하면 연결이 시도되지 않고 에러가 발행된다."""
        controller = ConnectionController()
        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        config = _loopback_config(protocol=ConnectionProtocol.SPI)

        result = controller.open_connection(config)

        assert result is False
        assert controller.is_connection_open(LOOPBACK_PORT_NAME) is False
        assert LOOPBACK_PORT_NAME not in controller.workers
        error_spy.assert_called_once()
        event = error_spy.call_args[0][0]
        assert event.port == LOOPBACK_PORT_NAME
        assert "SPI" in event.message


# =============================================================================
# ③ 기본(Serial) 경로 회귀 검증
# =============================================================================

class TestDefaultSerialRegression:
    """설정을 건드리지 않은 기존 기본 경로(Serial + Raw)가 그대로 동작하는지 검증."""

    def test_default_config_opens_with_raw_parser_over_serial_protocol(self):
        """기본 PortConfig(파서/프로토콜 미지정)는 여전히 Serial + Raw로 연결된다."""
        controller = ConnectionController()
        config = _loopback_config()  # protocol/parser_type 모두 기본값

        try:
            assert config.protocol == ConnectionProtocol.SERIAL
            assert controller.open_connection(config) is True
            assert isinstance(controller.parsers[LOOPBACK_PORT_NAME], RawParser)
        finally:
            controller.close_connection()
