"""
체크섬 계산 검증 테스트 (S-071)

## WHY
체크섬 구현은 자체 계산끼리 비교하면 아무것도 증명하지 못한다. 반사(reflected)
여부나 init/xorout을 잘못 잡아도 "계산값 == 계산값"은 언제나 참이다.
그래서 이 파일은 **각 알고리즘의 공개된 표준 검사값**으로 고정한다.

표준 검사값은 CRC 카탈로그 관례대로 ASCII 문자열 `"123456789"`에 대한 값이다.
CRC-32는 파이썬 표준 라이브러리 `zlib.crc32`와도 교차 확인한다.
"""
import zlib

import pytest

from core.checksum import ChecksumAlgorithm, byte_length, compute, verify

CHECK_INPUT = b"123456789"

# 알고리즘 -> "123456789"에 대한 표준 검사값
STANDARD_CHECK_VALUES = {
    ChecksumAlgorithm.XOR: 0x31,
    ChecksumAlgorithm.SUM8: 0xDD,
    ChecksumAlgorithm.SUM16: 0x01DD,
    ChecksumAlgorithm.CRC8: 0xF4,                # CRC-8/SMBUS
    ChecksumAlgorithm.CRC16_MODBUS: 0x4B37,      # CRC-16/MODBUS
    ChecksumAlgorithm.CRC16_CCITT_FALSE: 0x29B1,  # CRC-16/IBM-3740
    ChecksumAlgorithm.CRC32: 0xCBF43926,         # CRC-32/ISO-HDLC
}


@pytest.mark.parametrize("algorithm,expected", list(STANDARD_CHECK_VALUES.items()))
def test_standard_check_value(algorithm, expected):
    """각 알고리즘이 표준 검사값을 재현해야 한다."""
    actual = compute(algorithm, CHECK_INPUT)
    assert actual == expected, (
        f"{algorithm.value}: 0x{actual:X} != 표준 검사값 0x{expected:X}. "
        f"다항식/init/반사/xorout 중 하나가 잘못됐다."
    )


def test_crc32_matches_zlib():
    """CRC-32는 표준 라이브러리와 일치해야 한다 (독립 구현 교차 확인)."""
    assert compute(ChecksumAlgorithm.CRC32, CHECK_INPUT) == zlib.crc32(CHECK_INPUT)


@pytest.mark.parametrize("payload", [b"", b"\x00", b"\xff" * 300, bytes(range(256))])
def test_crc32_matches_zlib_for_various_payloads(payload):
    """길이·내용이 달라도 zlib와 일치해야 한다 (경계·대용량 포함)."""
    assert compute(ChecksumAlgorithm.CRC32, payload) == zlib.crc32(payload)


def test_none_algorithm_computes_zero_and_always_verifies():
    """NONE은 검증하지 않는다는 의미이므로 항상 통과해야 한다."""
    assert compute(ChecksumAlgorithm.NONE, CHECK_INPUT) == 0
    assert verify(ChecksumAlgorithm.NONE, CHECK_INPUT, 0xDEAD) is True


@pytest.mark.parametrize("algorithm,expected", list(STANDARD_CHECK_VALUES.items()))
def test_verify_accepts_correct_and_rejects_wrong(algorithm, expected):
    """verify()가 맞는 값은 받고 틀린 값은 거절해야 한다."""
    assert verify(algorithm, CHECK_INPUT, expected) is True
    assert verify(algorithm, CHECK_INPUT, expected ^ 0x01) is False


@pytest.mark.parametrize(
    "algorithm,size",
    [
        (ChecksumAlgorithm.NONE, 0),
        (ChecksumAlgorithm.XOR, 1),
        (ChecksumAlgorithm.SUM8, 1),
        (ChecksumAlgorithm.SUM16, 2),
        (ChecksumAlgorithm.CRC8, 1),
        (ChecksumAlgorithm.CRC16_MODBUS, 2),
        (ChecksumAlgorithm.CRC16_CCITT_FALSE, 2),
        (ChecksumAlgorithm.CRC32, 4),
    ],
)
def test_byte_length(algorithm, size):
    """알고리즘별 결과 바이트 수가 고정돼야 한다 (오프셋 계산의 근거)."""
    assert byte_length(algorithm) == size


def test_result_fits_declared_byte_length():
    """계산 결과가 선언한 바이트 수 안에 들어와야 한다."""
    for algorithm in ChecksumAlgorithm:
        size = byte_length(algorithm)
        if size == 0:
            continue
        value = compute(algorithm, bytes(range(256)))
        assert 0 <= value < (1 << (size * 8)), f"{algorithm.value} 결과가 {size}바이트를 넘는다"


def test_empty_payload_is_defined_for_every_algorithm():
    """빈 입력에서도 예외 없이 정의된 값을 내야 한다."""
    for algorithm in ChecksumAlgorithm:
        compute(algorithm, b"")


def test_unknown_algorithm_raises():
    """알 수 없는 알고리즘은 조용히 넘어가지 않고 오류를 낸다."""
    with pytest.raises(ValueError):
        compute("definitely_not_an_algorithm", CHECK_INPUT)
