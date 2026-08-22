"""
성능 벤치마크 도구 (RingBuffer / Queue / Parser / DataLogger)

수신 데이터 경로의 모델/코어 구간 처리량을 CLI에서 반복 측정해 표+JSON으로
출력합니다. UI 렌더링은 환경 의존이 커서 측정 범위에서 제외합니다.

## WHY
* README §1.4가 "처리량 수치는 자동 벤치마크가 도입되기 전까지 보장하지
  않습니다"라고 선언한 상태 -- 성능 최적화(S-007) 이전에 측정이 선행되어야 함
* 측정 없는 최적화 금지 (Task.MD 우선순위 메모) -- 회귀 감시용 반복 측정 기반 필요

## WHAT
* ringbuffer: RingBuffer 4KB 청크 write+read 반복 처리량 (MB/s)
* queue: ThreadSafeQueue enqueue+dequeue 처리량 (ops/s)
* parser: DelimiterParser AT 응답 혼합 샘플 파싱 처리량 (lines/s)
* logger: DataLogger(BIN) 실 디스크 기록 처리량 (MB/s)

## HOW
* 각 항목 3회 반복 후 중앙값(median) 채택 -- 1회성 잡음(GC, 스케줄링) 완화
* `--json <path>`로 기계 판독용 결과 저장 지원
* 코어/모델 코드는 읽기 전용으로만 사용 (수정 없음, S-011 DoD)

Usage:
    .venv\\Scripts\\python tools\\benchmark.py
    .venv\\Scripts\\python tools\\benchmark.py --json doc/benchmark_result.json --repeat 5
"""
import argparse
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict

# 프로젝트 루트를 sys.path에 추가 (tools/ 하위에서 직접 실행되는 스크립트이므로
# common/core/model 절대 임포트를 위해 필요 -- tools/ux_capture.py와 동일 관례)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.constants import DEFAULT_READ_CHUNK_SIZE, RING_BUFFER_SIZE  # noqa: E402 - sys.path 조작 후 임포트 필요
from common.enums import LogFormat, ParserType  # noqa: E402 - sys.path 조작 후 임포트 필요
from core.data_logger import DataLogger  # noqa: E402 - sys.path 조작 후 임포트 필요
from core.structures import RingBuffer, ThreadSafeQueue  # noqa: E402 - sys.path 조작 후 임포트 필요
from model.packet_parser import ParserFactory  # noqa: E402 - sys.path 조작 후 임포트 필요

DEFAULT_TOTAL_BYTES = 256 * 1024 * 1024  # 256MB
DEFAULT_QUEUE_COUNT = 100_000
DEFAULT_PARSER_LINES = 10_000
DEFAULT_REPEAT = 3


def bench_ringbuffer(
    total_bytes: int = DEFAULT_TOTAL_BYTES,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
) -> float:
    """RingBuffer write+read 처리량(MB/s)을 1회 측정한다.

    청크마다 write 직후 동일 크기를 read하여, 512KB 기본 크기 버퍼로
    총 `total_bytes`만큼의 write+read 트래픽을 흘려보내는 실사용 패턴
    (수신 → 즉시 소비)을 모사한다.

    Args:
        total_bytes: 왕복(write+read 각각)시킬 총 목표 바이트 수.
        chunk_size: 1회 write/read 크기.

    Returns:
        float: MB/s (write+read 합산 처리량).
    """
    buf = RingBuffer(size=RING_BUFFER_SIZE)
    chunk = bytes(chunk_size)
    n_chunks = max(1, total_bytes // chunk_size)

    start = time.perf_counter()
    for _ in range(n_chunks):
        buf.write(chunk)
        buf.read(chunk_size)
    elapsed = time.perf_counter() - start

    processed_bytes = n_chunks * chunk_size * 2  # write + read
    return (processed_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else float("inf")


def bench_queue(count: int = DEFAULT_QUEUE_COUNT) -> float:
    """ThreadSafeQueue enqueue+dequeue 처리량(ops/s)을 1회 측정한다.

    Args:
        count: enqueue 후 dequeue할 항목 수.

    Returns:
        float: ops/s (enqueue+dequeue 합산 연산 수 기준).
    """
    queue = ThreadSafeQueue()
    item = b"x"

    start = time.perf_counter()
    for _ in range(count):
        queue.enqueue(item)
    for _ in range(count):
        queue.dequeue()
    elapsed = time.perf_counter() - start

    return (count * 2) / elapsed if elapsed > 0 else float("inf")


def _build_at_sample(lines: int) -> bytes:
    """AT 응답 혼합 샘플(OK/+CSQ/ERROR/+CREG 순환) 버퍼를 생성한다.

    Args:
        lines: 생성할 라인 수.

    Returns:
        bytes: `\\n`으로 끝나는 라인들을 이어붙인 버퍼.
    """
    templates = (b"OK\r\n", b"+CSQ: 18,99\r\n", b"ERROR\r\n", b"+CREG: 0,1\r\n")
    return b"".join(templates[i % len(templates)] for i in range(lines))


def bench_parser(lines: int = DEFAULT_PARSER_LINES) -> float:
    """DelimiterParser의 AT 응답 혼합 샘플 파싱 처리량(lines/s)을 1회 측정한다.

    Args:
        lines: 파싱할 샘플 라인 수.

    Returns:
        float: lines/s.
    """
    buffer = _build_at_sample(lines)
    parser = ParserFactory.create_parser(ParserType.DELIMITER, delimiter=b"\n")

    start = time.perf_counter()
    parser.parse(buffer)
    elapsed = time.perf_counter() - start

    return lines / elapsed if elapsed > 0 else float("inf")


def bench_logger(
    total_bytes: int = DEFAULT_TOTAL_BYTES,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
) -> float:
    """DataLogger(BIN)의 실 디스크 기록 처리량(MB/s)을 1회 측정한다.

    `DataLogger.stop_logging()`의 `join(timeout=1.0)`은 대용량 드레인 완료를
    보장하지 않으므로(코어 코드는 수정하지 않음), 측정 구간은 내부 Queue(표준
    라이브러리 `queue.Queue`, 공개 API인 `qsize()`만 사용)가 완전히 빌 때까지
    직접 폴링해 실제 디스크 기록 완료 시점을 잡는다.

    Args:
        total_bytes: 기록할 총 목표 바이트 수.
        chunk_size: 1회 write() 호출 크기.

    Returns:
        float: MB/s.
    """
    tmp_dir = tempfile.mkdtemp(prefix="serial_tool_bench_logger_")
    file_path = os.path.join(tmp_dir, "bench.bin")
    logger_instance = DataLogger()
    chunk = bytes(chunk_size)
    n_chunks = max(1, total_bytes // chunk_size)

    try:
        if not logger_instance.start_logging(file_path, LogFormat.BIN):
            raise RuntimeError("DataLogger.start_logging 실패")

        start = time.perf_counter()
        for _ in range(n_chunks):
            logger_instance.write(chunk)
        # 백그라운드 쓰기 스레드가 큐를 완전히 비울 때까지 대기 (드레인 완료 시점 측정)
        while logger_instance._queue.qsize() > 0:
            time.sleep(0.001)
        elapsed = time.perf_counter() - start

        processed_bytes = n_chunks * chunk_size
        return (processed_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else float("inf")
    finally:
        logger_instance.stop_logging()
        try:
            os.remove(file_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


# 항목명 -> (측정 함수, 단위) 매핑. main()에서 순회하며 표/JSON을 구성한다.
BENCHMARKS: Dict[str, Callable[[], float]] = {
    "ringbuffer": bench_ringbuffer,
    "queue": bench_queue,
    "parser": bench_parser,
    "logger": bench_logger,
}
UNITS: Dict[str, str] = {
    "ringbuffer": "MB/s",
    "queue": "ops/s",
    "parser": "lines/s",
    "logger": "MB/s",
}


def run_all(repeat: int = DEFAULT_REPEAT) -> Dict[str, Dict[str, float]]:
    """4종 벤치마크를 각각 `repeat`회 실행하고 중앙값을 반환한다.

    Args:
        repeat: 항목별 반복 실행 횟수.

    Returns:
        Dict[str, Dict[str, float]]: 항목명 -> {"value": 중앙값, "unit": 단위}.
    """
    results: Dict[str, Dict[str, float]] = {}
    for name, fn in BENCHMARKS.items():
        samples = [fn() for _ in range(repeat)]
        results[name] = {"value": statistics.median(samples), "unit": UNITS[name]}
    return results


def print_table(results: Dict[str, Dict[str, float]]) -> None:
    """결과를 `항목  값  단위` 표 형식으로 콘솔에 출력한다."""
    print(f"{'항목':<12}{'값':>16}  단위")
    print("-" * 40)
    for name, info in results.items():
        print(f"{name:<12}{info['value']:>16,.2f}  {info['unit']}")


def main() -> None:
    """CLI 진입점: 벤치마크 실행 후 표 출력 및 선택적 JSON 저장."""
    arg_parser = argparse.ArgumentParser(
        description="SerialTool 성능 벤치마크 (RingBuffer/Queue/Parser/DataLogger)"
    )
    arg_parser.add_argument(
        "--json", type=str, default=None, help="결과를 저장할 JSON 파일 경로"
    )
    arg_parser.add_argument(
        "--repeat", type=int, default=DEFAULT_REPEAT, help="항목별 반복 횟수 (기본 3, 중앙값 채택)"
    )
    args = arg_parser.parse_args()

    print(f"Python {platform.python_version()} / {platform.processor() or platform.machine()}")
    print(f"repeat={args.repeat}\n")

    results = run_all(repeat=args.repeat)
    print_table(results)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nJSON 저장: {args.json}")


if __name__ == "__main__":
    main()
