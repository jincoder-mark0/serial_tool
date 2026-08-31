"""PyFtdi backend for FT232H / FT2232H transaction adapters.

## WHY
* PyFtdi는 첫 Tier-1 backend지만 Core transaction contract 자체가 되어서는 안 됨
* FT232H single-channel + FT2232H dual-channel을 같은 provider로 처리
* PyFtdi/libusb가 설치되지 않아도 SerialTool의 Serial 기능은 계속 시작 가능해야 함

## HOW
* vendor import는 `_load_pyftdi_api()`에서 lazy 수행
* `Ftdi.list_devices()` 결과를 vendor-neutral `AdapterDescriptor`로 변환
* serial number 우선 stable identity, serial이 없으면 USB topology locator를 명시적
  non-persistent fallback으로 사용
* PyFtdi SPI/I2C exception을 공통 transaction error surface로 변환
"""
from __future__ import annotations

from dataclasses import dataclass
from errno import ENODEV
from time import monotonic
from typing import Any, Callable, Sequence
from urllib.parse import quote

from core.transport.transaction.contracts import (
    AdapterHandle,
    AdapterProvider,
    I2cController,
    SpiController,
)
from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.dto import (
    AdapterCapabilities,
    AdapterDescriptor,
    AdapterIdentity,
    I2cCapabilities,
    I2cConfig,
    I2cTransactionRequest,
    I2cTransactionResult,
    SpiCapabilities,
    SpiConfig,
    SpiTransactionRequest,
    SpiTransactionResult,
    TransactionProtocol,
)
from core.transport.transaction.errors import (
    AdapterBusyError,
    AdapterDisconnectedError,
    AdapterNotFoundError,
    BackendUnavailableError,
    ProtocolConfigurationError,
    TransactionCancelledError,
    TransactionIoError,
    TransactionTimeoutError,
)
from core.transport.transaction.registry import AdapterBackendRegistry

_PYFTDI_BACKEND_ID = "pyftdi"
_FTDI_VENDOR_ID = 0x0403
_FT232H_PID = 0x6014
_FT2232H_PID = 0x6010


@dataclass(frozen=True)
class _PyFtdiApi:
    """Lazy-imported vendor symbols grouped for deterministic testing."""

    Ftdi: type
    FtdiError: type[BaseException]
    SpiController: type
    I2cController: type
    I2cIOError: type[BaseException]
    UsbTools: type


def _load_pyftdi_api() -> _PyFtdiApi:
    """Import optional PyFtdi dependency only when this backend is used."""
    try:
        from pyftdi.ftdi import Ftdi, FtdiError
        from pyftdi.i2c import I2cController as NativeI2cController, I2cIOError
        from pyftdi.spi import SpiController as NativeSpiController
        from pyftdi.usbtools import UsbTools
    except ImportError as exc:
        raise BackendUnavailableError(
            "PyFtdi backend requires the optional 'pyftdi' package"
        ) from exc

    return _PyFtdiApi(
        Ftdi=Ftdi,
        FtdiError=FtdiError,
        SpiController=NativeSpiController,
        I2cController=NativeI2cController,
        I2cIOError=I2cIOError,
        UsbTools=UsbTools,
    )


@dataclass(frozen=True)
class _ResolvedAdapter:
    descriptor: AdapterDescriptor
    url: str


class PyFtdiAdapterProvider(AdapterProvider):
    """FT232H/FT2232H discovery and factory provider."""

    _TARGETS = (
        ("FT232H", "232h", _FT232H_PID),
        ("FT2232H", "2232h", _FT2232H_PID),
    )

    def __init__(
        self,
        api_loader: Callable[[], _PyFtdiApi] = _load_pyftdi_api,
    ) -> None:
        self._api_loader = api_loader
        self._api: _PyFtdiApi | None = None

    @property
    def backend_id(self) -> str:
        return _PYFTDI_BACKEND_ID

    def _get_api(self) -> _PyFtdiApi:
        if self._api is None:
            self._api = self._api_loader()
        return self._api

    def is_available(self) -> bool:
        """Package와 PyUSB/libusb backend가 모두 로드 가능한지 확인."""
        try:
            api = self._get_api()
            api.UsbTools.find_backend()
            return True
        except Exception:
            return False

    def enumerate(self) -> Sequence[AdapterDescriptor]:
        return [item.descriptor for item in self._enumerate_resolved()]

    def open(self, identity: AdapterIdentity) -> AdapterHandle:
        if identity.backend_id != self.backend_id:
            raise AdapterNotFoundError(
                f"identity backend '{identity.backend_id}' does not belong to PyFtdi"
            )

        for resolved in self._enumerate_resolved():
            if resolved.descriptor.identity == identity:
                return _PyFtdiAdapterHandle(
                    api=self._get_api(),
                    descriptor=resolved.descriptor,
                    url=resolved.url,
                )
        raise AdapterNotFoundError(
            f"FTDI adapter not found: {identity.stable_id}"
            + (f"/{identity.channel_id}" if identity.channel_id else "")
        )

    def _enumerate_resolved(self) -> list[_ResolvedAdapter]:
        api = self._get_api()
        resolved: list[_ResolvedAdapter] = []

        try:
            # PyFtdi may cache USB descriptors. Flush before interactive re-scan so unplug/replug
            # does not keep a stale bus/address handle.
            api.UsbTools.flush_cache()
            for family, product_name, expected_pid in self._TARGETS:
                entries = api.Ftdi.list_devices(f"ftdi://ftdi:{product_name}/?")
                for usb_descriptor, interface in entries:
                    if int(getattr(usb_descriptor, "vid", 0)) != _FTDI_VENDOR_ID:
                        continue
                    if int(getattr(usb_descriptor, "pid", 0)) != expected_pid:
                        continue
                    resolved.append(
                        self._build_resolved(
                            usb_descriptor,
                            int(interface),
                            family=family,
                            product_name=product_name,
                        )
                    )
        except BackendUnavailableError:
            raise
        except Exception as exc:
            raise _translate_io_error(exc, "enumerate FTDI adapters") from exc

        # Same device/interface may appear more than once with alias product filters on some
        # PyFtdi versions/custom identifiers. Identity is the dedupe contract.
        unique: dict[AdapterIdentity, _ResolvedAdapter] = {}
        for item in resolved:
            unique[item.descriptor.identity] = item
        return list(unique.values())

    @staticmethod
    def _build_resolved(
        usb_descriptor: Any,
        interface: int,
        *,
        family: str,
        product_name: str,
    ) -> _ResolvedAdapter:
        serial = str(getattr(usb_descriptor, "sn", "") or "").strip()
        bus = getattr(usb_descriptor, "bus", None)
        address = getattr(usb_descriptor, "address", None)

        if serial:
            stable_id = serial
            persistent = True
            selector = quote(serial, safe="")
        else:
            # Bus/address is intentionally flagged non-persistent: it may change after replug.
            stable_id = f"usb-{bus}-{address}"
            persistent = False
            selector = f"{bus}:{address}"

        channel_id = None
        channel_label = ""
        channel_count = 1
        concurrent_channels = False
        if family == "FT2232H":
            channel_count = 2
            concurrent_channels = True
            channel_id = _interface_to_channel(interface)
            channel_label = f" [{channel_id}]"

        identity = AdapterIdentity(
            backend_id=_PYFTDI_BACKEND_ID,
            stable_id=stable_id,
            channel_id=channel_id,
        )
        description = str(getattr(usb_descriptor, "description", "") or family)
        persistence_suffix = "" if persistent else " [temporary USB path]"
        display_name = (
            f"{family} {serial or f'{bus}:{address}'}{channel_label} - {description}"
            f"{persistence_suffix}"
        )

        capabilities = AdapterCapabilities(
            protocols=frozenset({TransactionProtocol.SPI, TransactionProtocol.I2C}),
            channel_count=channel_count,
            concurrent_channels=concurrent_channels,
            spi=SpiCapabilities(
                modes=frozenset({0, 1, 2, 3}),
                bit_orders=frozenset({"msb"}),
                min_frequency_hz=1_000,
                max_frequency_hz=30_000_000,
                full_duplex=True,
                chip_select_count=5,
                cs_hold=True,
            ),
            i2c=I2cCapabilities(
                min_frequency_hz=10_000,
                max_frequency_hz=1_000_000,
                seven_bit_address=True,
                ten_bit_address=False,
                repeated_start=True,
                clock_stretching=True,
            ),
        )

        url = f"ftdi://ftdi:{product_name}:{selector}/{interface}"
        return _ResolvedAdapter(
            descriptor=AdapterDescriptor(
                identity=identity,
                device_family=family,
                display_name=display_name,
                capabilities=capabilities,
                identity_persistent=persistent,
            ),
            url=url,
        )


class _PyFtdiAdapterHandle(AdapterHandle):
    """One resolved FTDI MPSSE interface lifecycle owner."""

    def __init__(self, api: _PyFtdiApi, descriptor: AdapterDescriptor, url: str) -> None:
        self._api = api
        self._descriptor = descriptor
        self._url = url
        self._active_controller: SpiController | I2cController | None = None
        self._closed = False

    @property
    def descriptor(self) -> AdapterDescriptor:
        return self._descriptor

    def open_spi(self, config: SpiConfig) -> SpiController:
        self._ensure_open_and_idle()
        AdapterBackendRegistry.validate_spi(self._descriptor, config)

        try:
            native = self._api.SpiController(
                cs_count=max(1, config.chip_select + 1)
            )
            native.configure(self._url)
            port = native.get_port(
                cs=config.chip_select,
                freq=config.frequency_hz,
                mode=config.mode,
            )
        except Exception as exc:
            try:
                native.close()
            except Exception:
                pass
            raise _translate_io_error(exc, "open FTDI SPI controller") from exc

        controller = _PyFtdiSpiController(
            native=native,
            port=port,
            config=config,
            release=self._release_controller,
        )
        self._active_controller = controller
        return controller

    def open_i2c(self, config: I2cConfig) -> I2cController:
        self._ensure_open_and_idle()
        AdapterBackendRegistry.validate_i2c(self._descriptor, config)

        native = None
        try:
            native = self._api.I2cController()
            native.configure(
                self._url,
                frequency=float(config.frequency_hz),
                clockstretching=config.clock_stretching,
            )
            port = native.get_port(config.address)
        except Exception as exc:
            if native is not None:
                try:
                    native.close()
                except Exception:
                    pass
            raise _translate_io_error(exc, "open FTDI I2C controller") from exc

        controller = _PyFtdiI2cController(
            native=native,
            port=port,
            config=config,
            release=self._release_controller,
        )
        self._active_controller = controller
        return controller

    def close(self) -> None:
        if self._closed:
            return
        controller = self._active_controller
        if controller is not None:
            controller.close()
        self._active_controller = None
        self._closed = True

    def _ensure_open_and_idle(self) -> None:
        if self._closed:
            raise AdapterDisconnectedError("FTDI adapter handle is already closed")
        if self._active_controller is not None:
            raise AdapterBusyError(
                "FTDI interface already owns an active SPI/I2C controller"
            )

    def _release_controller(self, controller: object) -> None:
        if self._active_controller is controller:
            self._active_controller = None


class _PyFtdiSpiController(SpiController):
    def __init__(self, native: Any, port: Any, config: SpiConfig, release: Callable) -> None:
        self._native = native
        self._port = port
        self._config = config
        self._release = release
        self._closed = False

    def transact(
        self,
        request: SpiTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> SpiTransactionResult:
        self._ensure_open()
        _raise_if_cancelled(cancellation)

        if (
            self._config.full_duplex
            and request.tx_data
            and request.rx_length not in (0, len(request.tx_data))
        ):
            raise ProtocolConfigurationError(
                "PyFtdi full-duplex SPI requires rx_length to be 0 or equal tx_data length"
            )

        started = monotonic()
        try:
            rx_data = self._port.exchange(
                request.tx_data,
                request.rx_length,
                start=True,
                stop=not request.keep_cs_asserted,
                duplex=bool(self._config.full_duplex and request.tx_data),
            )
        except Exception as exc:
            raise _translate_io_error(exc, "FTDI SPI transaction") from exc

        _raise_if_cancelled(cancellation)
        _raise_if_timed_out(started, options)
        return SpiTransactionResult(
            rx_data=bytes(rx_data),
            actual_frequency_hz=int(round(float(self._port.frequency))),
        )

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._native.close()
        finally:
            self._closed = True
            self._release(self)

    def _ensure_open(self) -> None:
        if self._closed:
            raise AdapterDisconnectedError("FTDI SPI controller is closed")


class _PyFtdiI2cController(I2cController):
    def __init__(self, native: Any, port: Any, config: I2cConfig, release: Callable) -> None:
        self._native = native
        self._port = port
        self._config = config
        self._release = release
        self._closed = False

    def transact(
        self,
        request: I2cTransactionRequest,
        *,
        options: TransactionOptions = TransactionOptions(),
        cancellation: CancellationToken | None = None,
    ) -> I2cTransactionResult:
        self._ensure_open()
        _raise_if_cancelled(cancellation)
        started = monotonic()

        try:
            if request.write_data and request.read_length:
                if request.repeated_start:
                    read_data = self._port.exchange(
                        request.write_data,
                        request.read_length,
                        relax=True,
                        start=True,
                    )
                else:
                    self._port.write(request.write_data, relax=True, start=True)
                    read_data = self._port.read(
                        request.read_length,
                        relax=True,
                        start=True,
                    )
            elif request.write_data:
                self._port.write(request.write_data, relax=True, start=True)
                read_data = b""
            else:
                read_data = self._port.read(
                    request.read_length,
                    relax=True,
                    start=True,
                )
        except Exception as exc:
            raise _translate_io_error(exc, "FTDI I2C transaction") from exc

        _raise_if_cancelled(cancellation)
        _raise_if_timed_out(started, options)
        return I2cTransactionResult(
            read_data=bytes(read_data),
            actual_frequency_hz=int(round(float(self._port.frequency))),
        )

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._native.close()
        finally:
            self._closed = True
            self._release(self)

    def _ensure_open(self) -> None:
        if self._closed:
            raise AdapterDisconnectedError("FTDI I2C controller is closed")


def _interface_to_channel(interface: int) -> str:
    if 1 <= interface <= 26:
        return chr(ord("A") + interface - 1)
    return str(interface)


def _raise_if_cancelled(cancellation: CancellationToken | None) -> None:
    if cancellation is not None and cancellation.is_cancelled:
        raise TransactionCancelledError("transaction was cancelled")


def _raise_if_timed_out(started: float, options: TransactionOptions) -> None:
    if options.timeout_ms is None:
        return
    elapsed_ms = (monotonic() - started) * 1000.0
    if elapsed_ms > options.timeout_ms:
        raise TransactionTimeoutError(
            f"transaction exceeded timeout: {elapsed_ms:.1f} ms > {options.timeout_ms} ms"
        )


def _translate_io_error(exc: BaseException, operation: str) -> TransactionIoError:
    """Map vendor/USB errors without exposing vendor exception classes upward."""
    errno_value = getattr(exc, "errno", None)
    message = str(exc)
    lowered = message.casefold()
    if errno_value == ENODEV or "no such device" in lowered or "disconnected" in lowered:
        return AdapterDisconnectedError(f"{operation}: adapter disconnected: {message}")
    return TransactionIoError(f"{operation} failed: {message}")
