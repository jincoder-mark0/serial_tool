"""
길이 필드·갭 기반 파서 테스트 (S-072)

## WHY
* `FixedLengthParser`는 *상수* 길이만 안다. 헤더에 길이가 실려 매 패킷 크기가
  달라지는 프로토콜(`[SOF][LEN][PAYLOAD][CRC]`)을 나눌 수 없었다.
* 구분자도 길이도 없이 **유휴 시간**으로 프레임을 구분하는 프로토콜(Modbus RTU의
  3.5문자 유휴)도 다룰 수 없었다.

## WHAT
* 가변 길이 분리 정확성, 경계 조건(청크 경계 걸침, 기형 길이, includes_header 양쪽 해석)
* 갭 판정과 `flush()`로 마지막 조각 확정
* **S-064 회귀**: 배치 임계값(8192B) 이상을 한 번에 넣어도 완결 패킷이 유실되지 않는다

## HOW
시간에 의존하는 테스트는 느리고 불안정하므로, `GapParser`는 `time_source`를 주입해
가짜 시계로 검증한다 — `sleep`을 쓰지 않는다.
"""
import pytest

from common.constants import BATCH_SIZE_THRESHOLD
from common.enums import ParserType
from model.packet_parser import GapParser, LengthFieldParser, ParserFactory


class FakeClock:
    """테스트용 가짜 단조 시계 (초 단위)."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance_ms(self, ms: float) -> None:
        self.now += ms / 1000.0


# =============================================================================
# LengthFieldParser
# =============================================================================

class TestLengthFieldParser:
    """헤더의 길이 필드로 가변 길이 패킷을 나눈다."""

    @staticmethod
    def _frame(payload: bytes) -> bytes:
        """`[LEN][PAYLOAD]` 프레임 (LEN=1바이트, 페이로드 길이만 셈)."""
        return bytes([len(payload)]) + payload

    def test_splits_variable_length_packets_in_one_chunk(self):
        """길이가 서로 다른 패킷이 한 번에 들어와도 전부 정확히 나뉘어야 한다."""
        payloads = [b"A", b"BB", b"CCCC", b"D" * 20]
        stream = b"".join(self._frame(p) for p in payloads)

        parser = LengthFieldParser(offset=0, size=1, includes_header=False)
        packets = parser.parse(stream)

        assert [p.data for p in packets] == [self._frame(p) for p in payloads]

    def test_length_field_split_across_chunks(self):
        """길이 필드가 청크 경계에 걸쳐도 잃지 않아야 한다."""
        # LEN=2바이트로 두고 그 사이를 자른다
        payload = b"XYZ"
        frame = len(payload).to_bytes(2, "big") + payload

        parser = LengthFieldParser(offset=0, size=2, includes_header=False)
        assert parser.parse(frame[:1]) == []      # 길이 필드 첫 바이트만
        assert parser.parse(frame[1:2]) == []     # 길이 필드 완성, 페이로드 없음
        packets = parser.parse(frame[2:])
        assert [p.data for p in packets] == [frame]

    def test_payload_split_across_many_chunks(self):
        """페이로드가 여러 청크로 쪼개져 와도 완결 시점에 한 패킷으로 나와야 한다."""
        payload = b"HELLO-WORLD"
        frame = self._frame(payload)

        parser = LengthFieldParser(offset=0, size=1, includes_header=False)
        out = []
        for i in range(len(frame)):
            out.extend(parser.parse(frame[i:i + 1]))
        assert [p.data for p in out] == [frame]

    def test_includes_header_true_counts_whole_packet(self):
        """`includes_header=True`면 길이 값이 헤더까지 포함한 전체 길이다."""
        # [LEN=5][4바이트 페이로드] -> 전체 5바이트
        frame = bytes([5]) + b"WXYZ"
        parser = LengthFieldParser(offset=0, size=1, includes_header=True)
        packets = parser.parse(frame)
        assert [p.data for p in packets] == [frame]

    def test_includes_header_false_counts_payload_only(self):
        """`includes_header=False`면 길이 값이 필드 뒤 바이트 수만 센다."""
        frame = bytes([4]) + b"WXYZ"  # 전체는 5바이트
        parser = LengthFieldParser(offset=0, size=1, includes_header=False)
        packets = parser.parse(frame)
        assert [p.data for p in packets] == [frame]

    def test_offset_skips_leading_header_bytes(self):
        """길이 필드 앞에 SOF가 있어도 offset으로 건너뛸 수 있어야 한다."""
        sof = b"\xAA\x55"
        payload = b"PQR"
        frame = sof + bytes([len(payload)]) + payload

        parser = LengthFieldParser(offset=2, size=1, includes_header=False)
        packets = parser.parse(frame)
        assert [p.data for p in packets] == [frame]

    def test_little_endian_length(self):
        """리틀 엔디언 길이 필드를 읽을 수 있어야 한다."""
        payload = b"Z" * 300
        frame = len(payload).to_bytes(2, "little") + payload

        parser = LengthFieldParser(offset=0, size=2, endian="little", includes_header=False)
        packets = parser.parse(frame)
        assert [p.data for p in packets] == [frame]

    def test_absurd_length_resyncs_instead_of_stalling(self):
        """
        기형 길이 값을 만나면 1바이트 버리고 재동기화해야 한다.

        그대로 두면 같은 위치에서 영원히 막혀 뒤따르는 정상 패킷까지 못 본다.
        """
        garbage = b"\xFF\xFF"           # 상한을 넘는 길이 값
        # 파서를 size=2로 두므로 정상 프레임도 2바이트 길이 필드로 만든다.
        # (처음엔 1바이트짜리 헬퍼를 그대로 썼다가, 파서가 아니라 테스트 데이터가
        #  파서 설정과 어긋나 실패했다.)
        payload = b"OK"
        good = len(payload).to_bytes(2, "big") + payload
        parser = LengthFieldParser(offset=0, size=2, includes_header=False, max_packet_size=64)

        packets = parser.parse(garbage + good)
        assert [p.data for p in packets] == [good], "재동기화 후 정상 패킷이 나와야 한다"

    def test_rejects_invalid_construction(self):
        """잘못된 인자는 조용히 넘어가지 않고 오류를 낸다."""
        with pytest.raises(ValueError):
            LengthFieldParser(size=3)
        with pytest.raises(ValueError):
            LengthFieldParser(endian="middle")
        with pytest.raises(ValueError):
            LengthFieldParser(offset=-1)

    def test_no_loss_when_batch_threshold_exceeded_at_once(self):
        """
        S-064 회귀: 워커 배치 임계값 이상을 한 번에 받아도 완결 패킷이 유실되면 안 된다.

        버퍼 상한을 분리보다 먼저 적용하면 앞쪽 완결 패킷이 통째로 잘려나간다.
        """
        payload = b"P" * 15
        frame = self._frame(payload)
        count = (BATCH_SIZE_THRESHOLD * 2) // len(frame) + 10
        stream = frame * count

        parser = LengthFieldParser(offset=0, size=1, includes_header=False)
        packets = parser.parse(stream)

        assert len(packets) == count, (
            f"완결 패킷 {count}개 중 {len(packets)}개만 나왔다 — "
            f"버퍼 상한이 분리보다 먼저 적용되고 있다(S-064)."
        )


# =============================================================================
# GapParser
# =============================================================================

class TestGapParser:
    """유휴 시간으로 프레임을 나눈다."""

    def test_no_gap_accumulates_into_one_frame(self):
        """유휴가 없으면 계속 같은 프레임으로 모은다."""
        clock = FakeClock()
        parser = GapParser(gap_ms=5, time_source=clock)

        assert parser.parse(b"AB") == []
        clock.advance_ms(1)
        assert parser.parse(b"CD") == []
        assert parser.flush()[0].data == b"ABCD"

    def test_gap_closes_previous_frame(self):
        """유휴가 지나면 그때까지 모인 바이트가 한 프레임으로 확정된다."""
        clock = FakeClock()
        parser = GapParser(gap_ms=5, time_source=clock)

        parser.parse(b"FRAME1")
        clock.advance_ms(10)                      # 유휴 발생
        packets = parser.parse(b"FRAME2")

        assert [p.data for p in packets] == [b"FRAME1"]
        assert parser.flush()[0].data == b"FRAME2"

    def test_boundary_exactly_at_gap_is_a_frame_break(self):
        """유휴가 정확히 임계값이면 경계로 본다 (>= 판정)."""
        clock = FakeClock()
        parser = GapParser(gap_ms=5, time_source=clock)

        parser.parse(b"A")
        clock.advance_ms(5)
        assert [p.data for p in parser.parse(b"B")] == [b"A"]

    def test_flush_confirms_last_fragment(self):
        """
        데이터가 끊기면 마지막 조각은 `flush()`로만 확정된다 (설계상 한계).

        파서는 `parse()`가 호출될 때만 시간을 볼 수 있어, 유휴는 다음 데이터가
        도착했을 때 소급 판정된다. 포트 종료 경로에서 flush를 불러줘야 한다.
        """
        clock = FakeClock()
        parser = GapParser(gap_ms=5, time_source=clock)
        parser.parse(b"LAST")

        assert [p.data for p in parser.flush()] == [b"LAST"]
        assert parser.flush() == [], "flush는 멱등이어야 한다 (두 번 부르면 빈 리스트)"

    def test_flush_on_empty_buffer_is_harmless(self):
        """받은 것이 없으면 flush가 빈 패킷을 만들지 않아야 한다."""
        parser = GapParser(gap_ms=5, time_source=FakeClock())
        assert parser.flush() == []

    def test_reset_discards_pending_fragment(self):
        """reset은 진행 중인 조각을 버린다."""
        clock = FakeClock()
        parser = GapParser(gap_ms=5, time_source=clock)
        parser.parse(b"PARTIAL")
        parser.reset()
        assert parser.flush() == []

    def test_rejects_invalid_construction(self):
        """잘못된 인자는 오류를 낸다."""
        with pytest.raises(ValueError):
            GapParser(gap_ms=0)
        with pytest.raises(ValueError):
            GapParser(gap_ms=5, max_buffer_size=0)

    def test_no_loss_when_batch_threshold_exceeded_at_once(self):
        """
        S-064 회귀: 대량 유입 뒤 유휴가 와도 모인 바이트가 통째로 보존돼야 한다.

        상한을 넘긴 조각을 미리 잘라내면 확정 시점에 앞부분이 사라진다.
        """
        clock = FakeClock()
        # 상한을 넉넉히 잡아 "정상 프레임이 상한에 걸려 잘리는" 상황을 배제한다
        big = b"Q" * (BATCH_SIZE_THRESHOLD * 2)
        parser = GapParser(gap_ms=5, max_buffer_size=len(big) * 2, time_source=clock)

        parser.parse(big)
        clock.advance_ms(10)
        packets = parser.parse(b"NEXT")

        assert len(packets) == 1
        assert packets[0].data == big, "유휴 확정 시 모인 바이트가 온전해야 한다"


# =============================================================================
# ParserFactory 등록
# =============================================================================

class TestParserFactoryRegistration:
    """새 파서가 팩토리에서 만들어져야 설정으로 고를 수 있다."""

    def test_creates_length_field_parser(self):
        parser = ParserFactory.create_parser(
            ParserType.LENGTH_FIELD,
            length_field_offset=2,
            length_field_size=2,
            length_field_endian="little",
            length_includes_header=True,
        )
        assert isinstance(parser, LengthFieldParser)

    def test_creates_gap_parser(self):
        parser = ParserFactory.create_parser(ParserType.GAP, gap_ms=7)
        assert isinstance(parser, GapParser)

    def test_created_length_field_parser_uses_given_options(self):
        """팩토리가 넘긴 옵션이 실제로 반영돼야 한다 (인자가 무시되면 조용히 오동작)."""
        sof = b"\xAA\x55"
        payload = b"OPT"
        frame = sof + len(payload).to_bytes(2, "little") + payload

        parser = ParserFactory.create_parser(
            ParserType.LENGTH_FIELD,
            length_field_offset=2,
            length_field_size=2,
            length_field_endian="little",
            length_includes_header=False,
        )
        assert [p.data for p in parser.parse(frame)] == [frame]


class TestGapFlushOnConnectionClose:
    """
    포트를 닫을 때 갭 파서의 마지막 프레임이 유실되지 않아야 한다 (S-072).

    `GapParser`는 유휴로 프레임을 나누는데, 데이터가 끊기면 `parse()` 호출 자체가
    없어 마지막 프레임이 나오지 않는다. Controller가 파서를 버리기 전에 `flush()`를
    불러줘야 한다 — 안 부르면 조용히 사라진다.
    """

    def test_last_frame_is_emitted_when_connection_closes(self, qapp):
        from unittest.mock import MagicMock

        from common.constants import LOOPBACK_PORT_NAME
        from common.dtos import PortConfig
        from model.connection_controller import ConnectionController

        controller = ConnectionController()
        received = MagicMock()
        controller.packet_received.connect(received)

        # 갭 파서(인덱스 6)로 LOOPBACK 연결
        config = PortConfig(port=LOOPBACK_PORT_NAME, parser_type=6, gap_ms=50)
        assert controller.open_connection(config) is True
        try:
            # 유휴 없이 한 조각만 넣는다 -> 아직 확정되지 않은 상태
            controller.packet_parser_manager.feed(LOOPBACK_PORT_NAME, b"TAIL")
            assert received.call_count == 0, "유휴 전에는 프레임이 확정되면 안 된다"
        finally:
            controller.close_connection()

        assert received.call_count == 1, (
            "포트를 닫을 때 마지막 프레임이 나오지 않았다 — "
            "Controller가 파서를 버리기 전에 flush()를 부르지 않는다."
        )
        assert received.call_args[0][0].packet.data == b"TAIL"
