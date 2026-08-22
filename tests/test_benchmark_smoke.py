"""
성능 벤치마크 스모크 테스트

## WHY
* S-011에서 추가한 tools/benchmark.py의 4개 측정 함수가 예외 없이 정상적인
  숫자를 반환하는지만 빠르게 확인한다 -- 실측값 자체는 doc/benchmark_*.md가
  별도로 기록하며, 이 테스트는 전체 pytest 스위트에 편입되므로 매번 도는
  회귀 방지용이다.
* 실측용 크기(256MB, 10만 항목, 1만 라인)로 돌리면 수 초가 걸려 CI를
  느리게 만들므로, 훨씬 작은 크기(1MB, 1천 항목/라인)로 축소해 호출한다.

## WHAT
* bench_ringbuffer / bench_queue / bench_parser / bench_logger 각각을
  1회씩 작은 크기로 호출해 예외 없이 양수 float를 반환하는지 검증한다.
* 4개를 모두 합쳐 실행해도 1초 미만으로 끝나는지 확인한다 (DoD: 실행 시간
  1초 미만 유지).

## HOW
* tools/benchmark.py를 일반 모듈처럼 `from tools import benchmark`로 임포트한다
  (tests/conftest.py가 프로젝트 루트를 sys.path에 등록해 두므로 가능).

pytest tests/test_benchmark_smoke.py -v
"""
import time

from tools import benchmark


def test_bench_ringbuffer_smoke():
    """작은 크기(1MB)로 호출해도 예외 없이 양수 MB/s를 반환한다."""
    value = benchmark.bench_ringbuffer(total_bytes=1024 * 1024)
    assert value > 0


def test_bench_queue_smoke():
    """작은 크기(1천 항목)로 호출해도 예외 없이 양수 ops/s를 반환한다."""
    value = benchmark.bench_queue(count=1_000)
    assert value > 0


def test_bench_parser_smoke():
    """작은 크기(1천 라인)로 호출해도 예외 없이 양수 lines/s를 반환한다."""
    value = benchmark.bench_parser(lines=1_000)
    assert value > 0


def test_bench_logger_smoke():
    """작은 크기(1MB)로 호출해도 예외 없이 양수 MB/s를 반환하고 임시 파일을 정리한다."""
    value = benchmark.bench_logger(total_bytes=1024 * 1024)
    assert value > 0


def test_all_smoke_benches_run_under_one_second():
    """4개 벤치를 작은 크기로 모두 실행해도 총 소요 시간이 1초 미만이다."""
    start = time.perf_counter()
    benchmark.bench_ringbuffer(total_bytes=1024 * 1024)
    benchmark.bench_queue(count=1_000)
    benchmark.bench_parser(lines=1_000)
    benchmark.bench_logger(total_bytes=1024 * 1024)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0
