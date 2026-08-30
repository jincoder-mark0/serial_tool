"""PyFtdi backend tests without the real optional pyftdi package/hardware."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from core.transport.transaction.backends.pyftdi_backend import (
    PyFtdiAdapterProvider,
    _PyFtdiApi,
)
from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.dto import (
    AdapterIdentity,
    I2cConfig,
    I2cTransactionRequest,
    SpiConfig,
    SpiTransactionRequest,
)
from core.transport.transaction.errors import (
    AdapterBusyError,
    AdapterDisconnectedError,
    BackendUnavailableError,
    TransactionCancelledError,
)


@dataclass
class _UsbDescriptor:
    vid: int
    pid: int
    bus: int
    address: int
    sn: str | None
    index: int | None
    description: str


class _FakeUsbTools:
    flush_count = 0
    backend_available = True

    @classmethod
    def find_backend(cls):
        if not cls.backend_available:
            raise RuntimeError("libusb unavailable")
        return object()

    @classmethod
    def flush_cache(cls):
        cls.flush_count += 1


class _FakeFtdi:
    devices_232h = [
        (
            _UsbDescriptor(0x0403, 0x6014, 1, 4, "FT232-SN", None, "FT232H board"),
            1,
        )
    ]
    devices_2232h = [
        (
            _UsbDescriptor(0x0403, 0x6010, 2, 7, "FT2232-SN", None, "Dual RS232-HS"),
            1,
        ),
        (
            _UsbDescriptor(0x0403, 0x6010, 2, 7, "FT2232-SN", None, "Dual RS232-HS"),
            2,
        ),
    ]

    @classmethod
    def list_devices(cls, pattern):
        if ":232h/" in pattern:
            return list(cls.devices_232h)
        if ":2232h/" in pattern:
            return list(cls.devices_2232h)
        return []


class _FakeSpiPort:
    def __init__(self, frequency=3_000_000):
        self.frequency = frequency
        self.calls = []
        self.raise_error = None

    def exchange(self, out, readlen, **kwargs):
        self.calls.append((bytes(out), readlen, kwargs))
        if self.raise_error:
            raise self.raise_error
        if readlen:
            return bytes(range(readlen))
        if kwargs.get("duplex"):
            return bytes(out)
        return b""


class _FakeNativeSpiController:
    instances = []

    def __init__(self, cs_count=1):
        self.cs_count = cs_count
        self.url = None
        self.closed = False
        self.port = _FakeSpiPort()
        self.port_args = None
        type(self).instances.append(self)

    def configure(self, url):
        self.url = url

    def get_port(self, *, cs, freq, mode):
        self.port.frequency = freq
        self.port_args = (cs, freq, mode)
        return self.port

    def close(self):
        self.closed = True


class _FakeI2cPort:
    def __init__(self, frequency=100_000):
        self.frequency = frequency
        self.calls = []
        self.raise_error = None

    def exchange(self, out, readlen, **kwargs):
        self.calls.append(("exchange", bytes(out), readlen, kwargs))
        if self.raise_error:
            raise self.raise_error
        return bytes([0xA5] * readlen)

    def write(self, data, **kwargs):
        self.calls.append(("write", bytes(data), kwargs))
        if self.raise_error:
            raise self.raise_error

    def read(self, length, **kwargs):
        self.calls.append(("read", length, kwargs))
        if self.raise_error:
            raise self.raise_error
        return bytes([0x5A] * length)


class _FakeNativeI2cController:
    instances = []

    def __init__(self):
        self.url = None
        self.configure_kwargs = None
        self.address = None
        self.closed = False
        self.port = _FakeI2cPort()
        type(self).instances.append(self)

    def configure(self, url, **kwargs):
        self.url = url
        self.configure_kwargs = kwargs
        self.port.frequency = kwargs["frequency"]

    def get_port(self, address):
        self.address = address
        return self.port

    def close(self):
        self.closed = True


class _FakeFtdiError(OSError):
    pass


class _FakeI2cError(OSError):
    pass


def _api():
    _FakeUsbTools.backend_available = True
    _FakeNativeSpiController.instances.clear()
    _FakeNativeI2cController.instances.clear()
    return _PyFtdiApi(
        Ftdi=_FakeFtdi,
        FtdiError=_FakeFtdiError,
        SpiController=_FakeNativeSpiController,
        I2cController=_FakeNativeI2cController,
        I2cIOError=_FakeI2cError,
        UsbTools=_FakeUsbTools,
    )


def _provider():
    api = _api()
    return PyFtdiAdapterProvider(api_loader=lambda: api)


def test_enumerates_ft232h_and_ft2232h_channels_with_stable_identity():
    provider = _provider()

    descriptors = list(provider.enumerate())

    assert [(d.device_family, d.identity.channel_id) for d in descriptors] == [
        ("FT232H", None),
        ("FT2232H", "A"),
        ("FT2232H", "B"),
    ]
    assert descriptors[0].identity == AdapterIdentity("pyftdi", "FT232-SN")
    assert descriptors[1].identity == AdapterIdentity("pyftdi", "FT2232-SN", "A")
    assert descriptors[2].identity == AdapterIdentity("pyftdi", "FT2232-SN", "B")
    assert descriptors[1].capabilities.concurrent_channels is True
    assert descriptors[1].capabilities.channel_count == 2
    assert all(item.identity_persistent for item in descriptors)


def test_missing_serial_uses_explicit_non_persistent_usb_locator(monkeypatch):
    no_serial = [
        (_UsbDescriptor(0x0403, 0x6014, 3, 9, None, None, "FT232H"), 1)
    ]
    monkeypatch.setattr(_FakeFtdi, "devices_232h", no_serial)
    monkeypatch.setattr(_FakeFtdi, "devices_2232h", [])
    provider = _provider()

    descriptor = list(provider.enumerate())[0]

    assert descriptor.identity.stable_id == "usb-3-9"
    assert descriptor.identity_persistent is False
    assert "temporary USB path" in descriptor.display_name


def test_ft2232h_channel_b_spi_transaction_is_wrapped_without_vendor_leakage():
    provider = _provider()
    handle = provider.open(AdapterIdentity("pyftdi", "FT2232-SN", "B"))

    controller = handle.open_spi(
        SpiConfig(
            frequency_hz=4_000_000,
            mode=2,
            chip_select=1,
            full_duplex=False,
        )
    )
    result = controller.transact(
        SpiTransactionRequest(tx_data=b"\x9f", rx_length=3)
    )

    native = _FakeNativeSpiController.instances[-1]
    assert native.url == "ftdi://ftdi:2232h:FT2232-SN/2"
    assert native.cs_count == 2
    assert native.port_args == (1, 4_000_000, 2)
    assert result.rx_data == b"\x00\x01\x02"
    assert result.actual_frequency_hz == 4_000_000

    controller.close()
    # Closing the child releases the handle so another protocol may be opened.
    i2c = handle.open_i2c(I2cConfig(frequency_hz=100_000, address=0x50))
    i2c.close()
    handle.close()


def test_handle_prevents_two_protocol_owners_on_same_ftdi_interface():
    provider = _provider()
    handle = provider.open(AdapterIdentity("pyftdi", "FT232-SN"))
    spi = handle.open_spi(SpiConfig(frequency_hz=1_000_000))

    with pytest.raises(AdapterBusyError):
        handle.open_i2c(I2cConfig(frequency_hz=100_000, address=0x20))

    spi.close()
    handle.close()


def test_i2c_repeated_start_and_split_transactions_map_to_pyftdi_port():
    provider = _provider()
    handle = provider.open(AdapterIdentity("pyftdi", "FT2232-SN", "A"))
    controller = handle.open_i2c(
        I2cConfig(
            frequency_hz=400_000,
            address=0x50,
            clock_stretching=True,
        )
    )

    repeated = controller.transact(
        I2cTransactionRequest(write_data=b"\x01", read_length=2, repeated_start=True)
    )
    split = controller.transact(
        I2cTransactionRequest(write_data=b"\x02", read_length=2, repeated_start=False)
    )

    native = _FakeNativeI2cController.instances[-1]
    assert native.url == "ftdi://ftdi:2232h:FT2232-SN/1"
    assert native.address == 0x50
    assert native.configure_kwargs == {
        "frequency": 400_000.0,
        "clockstretching": True,
    }
    assert repeated.read_data == b"\xA5\xA5"
    assert split.read_data == b"\x5A\x5A"
    assert native.port.calls[0][0] == "exchange"
    assert native.port.calls[1][0] == "write"
    assert native.port.calls[2][0] == "read"

    controller.close()
    handle.close()


def test_cancellation_is_checked_before_vendor_io():
    provider = _provider()
    handle = provider.open(AdapterIdentity("pyftdi", "FT232-SN"))
    controller = handle.open_spi(SpiConfig(frequency_hz=1_000_000))
    token = CancellationToken()
    token.cancel()

    with pytest.raises(TransactionCancelledError):
        controller.transact(
            SpiTransactionRequest(tx_data=b"\x01"),
            options=TransactionOptions(timeout_ms=100),
            cancellation=token,
        )

    native = _FakeNativeSpiController.instances[-1]
    assert native.port.calls == []
    controller.close()
    handle.close()


def test_usb_disconnect_error_is_translated_to_common_error():
    provider = _provider()
    handle = provider.open(AdapterIdentity("pyftdi", "FT232-SN"))
    controller = handle.open_spi(SpiConfig(frequency_hz=1_000_000))
    native = _FakeNativeSpiController.instances[-1]
    native.port.raise_error = OSError(19, "No such device")

    with pytest.raises(AdapterDisconnectedError):
        controller.transact(SpiTransactionRequest(tx_data=b"\x01"))

    controller.close()
    handle.close()


def test_provider_is_unavailable_when_optional_backend_prerequisite_is_missing():
    api = _api()
    _FakeUsbTools.backend_available = False
    provider = PyFtdiAdapterProvider(api_loader=lambda: api)

    assert provider.is_available() is False


def test_provider_is_unavailable_when_optional_package_import_fails():
    def _missing():
        raise BackendUnavailableError("missing")

    provider = PyFtdiAdapterProvider(api_loader=_missing)

    assert provider.is_available() is False
