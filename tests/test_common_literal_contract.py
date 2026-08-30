"""
공통 상태/선택값 정본 사용 회귀 테스트

상태 문자열과 UI 옵션이 다시 View/Model/Presenter에 리터럴로 복제되지 않도록
이번 리팩터링에서 정본화한 구체적인 계약을 고정합니다.
"""
import inspect

from common.defaults import (
    DEFAULT_PACKET_BUFFER_SIZE,
    DEFAULT_PACKET_LENGTH,
    DEFAULT_PORT_BYTESIZE,
    DEFAULT_PORT_PROTOCOL,
    DEFAULT_SPI_MODE,
    DEFAULT_SPI_SPEED,
)
from common.enums import (
    ByteOrder,
    ConnectionEventState,
    ConnectionProtocol,
    LengthFieldSize,
    LogLevel,
    MacroStepType,
    ParserPreferenceIndex,
    ParserType,
)
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.port_presenter import PortPresenter
from view.dialogs.preferences_dialog import PreferencesDialog
from view.widgets.port_settings import PortSettingsWidget


def test_connection_controller_uses_connection_event_state_enum():
    source = inspect.getsource(ConnectionController)
    assert "ConnectionEventState.OPENED.value" in source
    assert "ConnectionEventState.CLOSED.value" in source
    assert 'state="opened"' not in source
    assert 'state="closed"' not in source


def test_macro_runner_uses_macro_step_type_enum():
    source = inspect.getsource(MacroRunner)
    assert "MacroStepType.STARTED.value" in source
    assert "MacroStepType.COMPLETED.value" in source
    assert 'type="started"' not in source
    assert 'type="completed"' not in source


def test_parser_factory_mapping_uses_public_preference_index_enum():
    for option in ParserPreferenceIndex:
        assert ParserType.from_preference_index(int(option))
    assert ParserType.from_preference_index(9999) == ParserType.RAW


def test_port_settings_uses_common_protocol_and_defaults():
    source = inspect.getsource(PortSettingsWidget)
    assert "ConnectionProtocol.SERIAL" in source
    assert "ConnectionProtocol.SPI" in source
    assert "DEFAULT_PORT_PROTOCOL" in source
    assert "DEFAULT_PORT_BYTESIZE" in source
    assert "DEFAULT_SPI_SPEED" in source
    assert "DEFAULT_SPI_MODE" in source

    assert DEFAULT_PORT_PROTOCOL == ConnectionProtocol.SERIAL
    assert DEFAULT_PORT_BYTESIZE == 8
    assert DEFAULT_SPI_SPEED == 1_000_000
    assert DEFAULT_SPI_MODE == 0


def test_preferences_uses_public_parser_and_length_field_options():
    source = inspect.getsource(PreferencesDialog)
    for option in ParserPreferenceIndex:
        assert f"ParserPreferenceIndex.{option.name}" in source

    assert "for size in LengthFieldSize" in source
    assert "ByteOrder.BIG.value" in source
    assert "ByteOrder.LITTLE.value" in source
    assert "DEFAULT_PACKET_LENGTH" in source
    assert "DEFAULT_PACKET_BUFFER_SIZE" in source

    assert {item.value for item in LengthFieldSize} == {1, 2, 4}
    assert {item.value for item in ByteOrder} == {"big", "little"}
    assert DEFAULT_PACKET_LENGTH == 64
    assert DEFAULT_PACKET_BUFFER_SIZE == 100


def test_port_presenter_uses_log_level_enum():
    source = inspect.getsource(PortPresenter)
    assert "LogLevel.SUCCESS" in source
    assert "LogLevel.INFO" in source
    assert "LogLevel.ERROR" in source
    assert '"SUCCESS")' not in source
    assert '"INFO")' not in source
    assert '"ERROR")' not in source


def test_lifecycle_system_log_uses_log_level_enum():
    source = inspect.getsource(AppLifecycleManager)
    assert "LogLevel.INFO.value" in source
    assert 'level="INFO"' not in source


def test_log_level_values_are_stable():
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.SUCCESS.value == "SUCCESS"
    assert LogLevel.CRITICAL.value == "CRITICAL"
