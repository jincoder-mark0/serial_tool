"""Transaction execution control primitives.

Backend 구현은 이 module의 timeout/cancellation contract를 받아 vendor API 호출 전후와
분할 transaction 경계에서 확인합니다. Qt/QWidget에 의존하지 않아 worker/thread 어디서든
사용할 수 있습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event

from core.transport.transaction.errors import ProtocolConfigurationError


@dataclass(frozen=True)
class TransactionOptions:
    """한 transaction의 공통 실행 정책.

    ``timeout_ms=None``은 backend 기본 timeout을 사용한다는 뜻이며 무한 대기를 의미하지
    않습니다. 실제 backend 기본값은 #12 implementation에서 capability/driver 기준으로
    결정합니다.
    """

    timeout_ms: int | None = None

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms <= 0:
            raise ProtocolConfigurationError("transaction timeout_ms must be positive")


class CancellationToken:
    """Thread-safe cooperative cancellation token.

    Python에서 실행 중인 vendor/native call을 강제 종료하지 않습니다. 대신 backend/worker가
    transaction 시작 전, vendor call 사이, retry/chunk 경계에서 확인해 신규 I/O를 중단하는
    cooperative contract입니다.
    """

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()
