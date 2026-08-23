"""
체크섬 계산 모듈 (S-071)

패킷의 무결성 검증에 쓰이는 체크섬/CRC를 계산합니다.

## WHY
* 프로토콜 디버깅에서 가장 자주 나오는 질문은 "이 패킷이 유효한가"다. 그런데
  SerialTool은 패킷 경계를 나눌 수는 있어도 검증 수단이 없어 사람이 HEX를 눈으로
  더해야 했다.
* 계산을 Qt·View에 의존하지 않는 Core에 두면 Model이 그대로 쓸 수 있고, GUI 없이
  표준 시험 벡터로 검증할 수 있다.

## WHAT
* `ChecksumAlgorithm`: 지원 알고리즘 식별자 (설정 저장 값과 1:1)
* `compute(algorithm, data)`: 바이트열의 체크섬 값을 정수로 반환
* `byte_length(algorithm)`: 그 알고리즘이 차지하는 바이트 수
* `verify(algorithm, data, expected)`: 계산값과 기대값 비교

## HOW
* CRC는 매 호출 테이블을 만들지 않도록 **다항식별 룩업 테이블을 캐시**한다.
* 반사(reflected) 계열은 반사된 다항식으로 오른쪽 시프트 방식으로 계산한다.
* 각 알고리즘은 표준 시험 문자열 "123456789"에 대한 알려진 검사값을 가지며,
  `tests/test_checksum.py`가 그 값으로 고정한다 (자체 계산끼리 비교하지 않는다).
"""
from enum import Enum
from typing import Dict, List


class ChecksumAlgorithm(str, Enum):
    """
    지원하는 체크섬 알고리즘.

    값은 설정 파일에 그대로 저장되므로 변경 시 마이그레이션이 필요하다.
    """

    NONE = "none"
    XOR = "xor"
    SUM8 = "sum8"
    SUM16 = "sum16"
    CRC8 = "crc8"
    CRC16_MODBUS = "crc16_modbus"
    CRC16_CCITT_FALSE = "crc16_ccitt_false"
    CRC32 = "crc32"


# 알고리즘별 결과 바이트 수 (NONE은 0)
_BYTE_LENGTHS: Dict[ChecksumAlgorithm, int] = {
    ChecksumAlgorithm.NONE: 0,
    ChecksumAlgorithm.XOR: 1,
    ChecksumAlgorithm.SUM8: 1,
    ChecksumAlgorithm.SUM16: 2,
    ChecksumAlgorithm.CRC8: 1,
    ChecksumAlgorithm.CRC16_MODBUS: 2,
    ChecksumAlgorithm.CRC16_CCITT_FALSE: 2,
    ChecksumAlgorithm.CRC32: 4,
}

# 다항식별 테이블 캐시 (키: (다항식, 반사 여부, 폭))
_TABLE_CACHE: Dict[tuple, List[int]] = {}


def _crc_table(poly: int, width: int, reflected: bool) -> List[int]:
    """
    CRC 룩업 테이블을 만든다 (같은 조합은 캐시에서 재사용).

    Args:
        poly (int): 다항식. reflected=True면 이미 반사된 형태를 넘긴다.
        width (int): CRC 폭(비트). 8/16/32.
        reflected (bool): 반사 계열 여부.

    Returns:
        List[int]: 256개 엔트리 테이블.
    """
    key = (poly, width, reflected)
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached

    mask = (1 << width) - 1
    table: List[int] = []
    for i in range(256):
        if reflected:
            crc = i
            for _ in range(8):
                crc = (crc >> 1) ^ (poly if crc & 1 else 0)
        else:
            crc = i << (width - 8)
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & mask if crc & (1 << (width - 1)) else (crc << 1) & mask
        table.append(crc & mask)

    _TABLE_CACHE[key] = table
    return table


def _crc(data: bytes, poly: int, width: int, init: int, reflected: bool, xor_out: int) -> int:
    """테이블 기반 CRC 공통 계산."""
    mask = (1 << width) - 1
    table = _crc_table(poly, width, reflected)
    crc = init & mask

    if reflected:
        for byte in data:
            crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
    else:
        for byte in data:
            crc = ((crc << 8) & mask) ^ table[((crc >> (width - 8)) ^ byte) & 0xFF]

    return (crc ^ xor_out) & mask


def byte_length(algorithm: ChecksumAlgorithm) -> int:
    """
    알고리즘의 결과가 차지하는 바이트 수를 반환합니다.

    Args:
        algorithm (ChecksumAlgorithm): 대상 알고리즘.

    Returns:
        int: 바이트 수 (NONE이면 0).
    """
    return _BYTE_LENGTHS[ChecksumAlgorithm(algorithm)]


def compute(algorithm: ChecksumAlgorithm, data: bytes) -> int:
    """
    바이트열의 체크섬 값을 계산합니다.

    Args:
        algorithm (ChecksumAlgorithm): 사용할 알고리즘.
        data (bytes): 계산 대상 바이트열.

    Returns:
        int: 체크섬 값. `NONE`이면 0.

    Raises:
        ValueError: 알 수 없는 알고리즘인 경우.
    """
    algo = ChecksumAlgorithm(algorithm)

    if algo is ChecksumAlgorithm.NONE:
        return 0
    if algo is ChecksumAlgorithm.XOR:
        result = 0
        for byte in data:
            result ^= byte
        return result
    if algo is ChecksumAlgorithm.SUM8:
        return sum(data) & 0xFF
    if algo is ChecksumAlgorithm.SUM16:
        return sum(data) & 0xFFFF
    if algo is ChecksumAlgorithm.CRC8:
        # CRC-8/SMBUS: poly 0x07, init 0x00, 비반사, xorout 0x00
        return _crc(data, poly=0x07, width=8, init=0x00, reflected=False, xor_out=0x00)
    if algo is ChecksumAlgorithm.CRC16_MODBUS:
        # CRC-16/MODBUS: poly 0x8005(반사 0xA001), init 0xFFFF, 반사, xorout 0x0000
        return _crc(data, poly=0xA001, width=16, init=0xFFFF, reflected=True, xor_out=0x0000)
    if algo is ChecksumAlgorithm.CRC16_CCITT_FALSE:
        # CRC-16/IBM-3740(통칭 CCITT-FALSE): poly 0x1021, init 0xFFFF, 비반사, xorout 0x0000
        return _crc(data, poly=0x1021, width=16, init=0xFFFF, reflected=False, xor_out=0x0000)
    if algo is ChecksumAlgorithm.CRC32:
        # CRC-32/ISO-HDLC: poly 0x04C11DB7(반사 0xEDB88320), init 0xFFFFFFFF, 반사, xorout 0xFFFFFFFF
        return _crc(data, poly=0xEDB88320, width=32, init=0xFFFFFFFF, reflected=True, xor_out=0xFFFFFFFF)

    raise ValueError(f"Unknown checksum algorithm: {algorithm}")


def verify(algorithm: ChecksumAlgorithm, data: bytes, expected: int) -> bool:
    """
    계산한 체크섬이 기대값과 같은지 확인합니다.

    Args:
        algorithm (ChecksumAlgorithm): 사용할 알고리즘.
        data (bytes): 계산 대상 바이트열.
        expected (int): 패킷에 실려 온 기대값.

    Returns:
        bool: 일치하면 True. `NONE`이면 검증하지 않으므로 항상 True.
    """
    if ChecksumAlgorithm(algorithm) is ChecksumAlgorithm.NONE:
        return True
    return compute(algorithm, data) == expected
