"""SPI/I2C adapter/backend 공통 오류 surface.

Vendor-specific exception은 backend implementation 내부에서 이 계층의 오류로 변환하고,
원본 예외는 ``raise ... from exc`` 형태로 cause에 보존합니다.
"""


class TransactionAdapterError(RuntimeError):
    """Transaction adapter 계층의 base exception."""


class BackendUnavailableError(TransactionAdapterError):
    """Optional backend package/DLL/driver를 사용할 수 없음."""


class AdapterNotFoundError(TransactionAdapterError):
    """요청한 stable adapter identity를 찾을 수 없음."""


class AdapterBusyError(TransactionAdapterError):
    """Adapter/channel을 다른 owner가 사용 중임."""


class UnsupportedCapabilityError(TransactionAdapterError):
    """요청 protocol/feature를 해당 adapter가 지원하지 않음."""


class ProtocolConfigurationError(TransactionAdapterError, ValueError):
    """Protocol config가 정적 또는 capability validation을 통과하지 못함."""


class TransactionCancelledError(TransactionAdapterError):
    """Cooperative cancellation이 transaction 시작/경계에서 확인됨."""


class TransactionTimeoutError(TransactionAdapterError, TimeoutError):
    """Transaction이 허용된 timeout 안에 완료되지 않음."""


class TransactionIoError(TransactionAdapterError):
    """Vendor/USB I/O transaction 실패."""


class AdapterDisconnectedError(TransactionIoError):
    """Transaction 도중 adapter가 제거되거나 연결이 끊김."""
