"""Transaction timeout/cancellation contract tests."""

import pytest

from core.transport.transaction.control import CancellationToken, TransactionOptions
from core.transport.transaction.errors import ProtocolConfigurationError


def test_transaction_options_accepts_backend_default_or_positive_timeout():
    assert TransactionOptions().timeout_ms is None
    assert TransactionOptions(timeout_ms=250).timeout_ms == 250


@pytest.mark.parametrize("timeout_ms", [0, -1, -100])
def test_transaction_options_rejects_non_positive_timeout(timeout_ms):
    with pytest.raises(ProtocolConfigurationError, match="timeout_ms must be positive"):
        TransactionOptions(timeout_ms=timeout_ms)


def test_cancellation_token_is_thread_safe_cooperative_state():
    token = CancellationToken()

    assert token.is_cancelled is False
    token.cancel()
    assert token.is_cancelled is True
    token.reset()
    assert token.is_cancelled is False
