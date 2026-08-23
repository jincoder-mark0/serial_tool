"""
패킷 프레젠터 모듈

패킷 분석 뷰(PacketPanel)와 데이터 소스(EventRouter)를 연결하고 관리합니다.

## WHY
* 실시간 패킷 데이터의 UI 업데이트 로직 분리 (MVP 패턴)
* 패킷 파싱 데이터의 시각화 형식(Hex/ASCII) 변환 담당
* 대량 패킷 수신 시 UI 버퍼링 및 설정 동기화 관리
* 고속 패킷 환경에서 GUI 스레드 블로킹 방지 (S-061 — 실측 근거는
  `tasks/S-061-packet-view-throttle.md` "측정 결과·판정" 절 참조. 기본 설정
  (buffer_size=100, autoscroll=True)에서 즉시 append 시 8,000패킷 버스트에
  500ms 이상, 실제 LOOPBACK 파이프라인의 14,336패킷 버스트에 약 1초가
  걸려 그 시간만큼 UI가 멈추는 것을 확인)

## WHAT
* PacketPanel(View)과 EventRouter(Model Interface) 연결
* 패킷 수신 이벤트(PacketEvent) 처리 및 View 데이터(PacketViewData) 변환
* 설정 변경(버퍼 크기, 색상 등)에 따른 View 업데이트
* 캡처 시작/정지 및 초기화 제어
* 수신 패킷의 View 반영을 30ms 주기로 버퍼링 (Throttling, S-061)

## HOW
* EventRouter의 시그널을 구독하여 패킷 수신
* DTO 변환 후 리스트에 버퍼링 -> QTimer(UI_REFRESH_INTERVAL_MS)가 주기적으로
  순서대로 flush하여 View의 append_packet 메서드 호출 (`data_handler.py`의
  30ms 배치 패턴을 재사용 — 새 방식을 발명하지 않음)
* SettingsManager를 통해 초기 설정 로드 및 변경 사항 반영
"""
from typing import List, Optional

from PyQt5.QtCore import QObject, QDateTime, QTimer

from view.panels.packet_panel import PacketPanel
from presenter.event_router import EventRouter
from core.settings_manager import SettingsManager
from core import checksum
from core.checksum import ChecksumAlgorithm
from core.logger import logger
from common.constants import ConfigKeys, UI_REFRESH_INTERVAL_MS
from common.dtos import (
    PacketEvent,
    PacketViewData,
    PreferencesState
)


class PacketPresenter(QObject):
    """
    패킷 분석 화면의 로직을 담당하는 Presenter 클래스
    """

    def __init__(self, panel: PacketPanel, event_router: EventRouter, settings_manager: SettingsManager) -> None:
        """
        PacketPresenter 초기화

        Args:
            panel (PacketPanel): 패킷 뷰 인스턴스.
            event_router (EventRouter): 이벤트 라우터 (패킷 수신용).
            settings_manager (SettingsManager): 설정 관리자.
        """
        super().__init__()
        self.panel = panel
        self.event_router = event_router
        self.settings_manager = settings_manager

        # 캡처 활성화 상태 (기본값 True)
        self._is_capturing = True

        # 패킷 View 반영 버퍼 (Throttling, S-061) — on_packet_received는 즉시
        # panel.append_packet을 호출하지 않고 여기 쌓아 두었다가 타이머가 flush한다.
        self._pending_packets: List[PacketViewData] = []
        # View(PacketModel)의 표시 버퍼 크기 사본 (_apply_initial_settings/on_settings_changed가
        # 갱신). _flush_pending_packets가 "화면에 남지도 못하고 즉시 밀려날 항목"을
        # 판단하는 데 쓴다 — 기본값은 PacketModel의 기본 buffer_size(100)와 동일.
        self._buffer_size = 100
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(UI_REFRESH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._flush_pending_packets)
        self._flush_timer.start()

        # 1. 초기 설정 적용
        self._apply_initial_settings()

        # 2. View 시그널 연결 (Facade Signal)
        self.panel.clear_requested.connect(self.on_clear_requested)
        self.panel.capture_toggled.connect(self.on_capture_toggled)

        # 3. EventRouter 시그널 연결
        self.event_router.packet_received.connect(self.on_packet_received)
        self.event_router.settings_changed.connect(self.on_settings_changed)
        # 포트가 닫히면 그 포트에서 아직 버퍼에 남아있는 패킷을 즉시 flush한다
        # (다음 30ms 주기까지 기다리지 않고, 조용히 묻히지 않도록 — S-061).
        self.event_router.port_closed.connect(self._flush_pending_packets)

    def _apply_initial_settings(self) -> None:
        """
        SettingsManager에서 초기 설정을 로드하여 View에 적용합니다.

        Logic:
            - 버퍼 크기, 자동 스크롤 여부 로드
            - View의 설정 메서드 호출 (Facade)
        """
        buffer_size = self.settings_manager.get(ConfigKeys.PACKET_BUFFER_SIZE, 100)
        autoscroll = self.settings_manager.get(ConfigKeys.PACKET_AUTOSCROLL, True)
        realtime = self.settings_manager.get(ConfigKeys.PACKET_REALTIME, True)

        self._buffer_size = buffer_size
        self.panel.set_buffer_size(buffer_size)
        self.panel.set_autoscroll(autoscroll)
        self._is_capturing = realtime
        self.panel.set_capture_state(realtime)

    def on_packet_received(self, event: PacketEvent) -> None:
        """
        패킷 수신 이벤트 처리 핸들러

        Logic:
            1. 캡처 중지 상태면 무시
            2. DTO(`PacketEvent`)에서 패킷 객체 추출
            3. 패킷 데이터를 View용 DTO(`PacketViewData`)로 변환
            4. View에 추가 요청

        Args:
            event (PacketEvent): 수신된 패킷 이벤트 DTO.
        """
        if not self._is_capturing:
            return

        packet = event.packet
        if not packet:
            return

        # 타임스탬프 포맷팅
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")

        # 데이터 변환 (Hex / ASCII)
        # Packet 객체(model.packet_parser.Packet)는 raw_data 속성을 가진다고 가정
        raw_data = getattr(packet, 'data', b'') # Packet DTO 속성명 'data'

        # Hex 문자열 변환 (예: "01 02 0A")
        data_hex = " ".join(f"{b:02X}" for b in raw_data)

        # ASCII 문자열 변환 (제어 문자는 점으로 표시)
        data_ascii = "".join(chr(b) if 32 <= b < 127 else "." for b in raw_data)

        # 패킷 타입 (메타데이터 활용)
        packet_type = "Raw"
        if packet.metadata and "type" in packet.metadata:
            packet_type = packet.metadata["type"]

        # View용 DTO 생성
        view_data = PacketViewData(
            time_str=timestamp,
            packet_type=packet_type,
            data_hex=data_hex,
            data_ascii=data_ascii,
            checksum_ok=self._verify_checksum(raw_data),
        )

        # View 업데이트 버퍼링 (Throttling, S-061) — 즉시 panel.append_packet을
        # 호출하지 않고 큐에 쌓는다. 실제 반영은 _flush_pending_packets가 담당.
        self._pending_packets.append(view_data)

    def _verify_checksum(self, raw_data: bytes) -> Optional[bool]:
        """
        수신 패킷의 체크섬을 검증합니다 (S-071).

        Logic:
            - 알고리즘이 `none`이면 검증하지 않고 None을 돌려준다.
            - 설정된 오프셋에서 체크섬 필드를 읽고, 계산 대상 범위(앞/뒤 제외
              바이트를 뺀 구간)로 값을 계산해 비교한다.
            - 패킷이 체크섬 필드를 담기에 짧으면 "불일치"가 아니라 **검증 불가**
              (None)로 본다 — 파서 설정이 프로토콜과 안 맞을 때 모든 행이 빨갛게
              물드는 것보다, 검증하지 않았음을 그대로 보여주는 쪽이 정직하다.

        Args:
            raw_data (bytes): 패킷 원본 바이트열.

        Returns:
            Optional[bool]: True=통과, False=불일치, None=검증하지 않음.
        """
        algorithm = self.settings_manager.get(
            ConfigKeys.PACKET_CHECKSUM_ALGORITHM, ChecksumAlgorithm.NONE.value
        )
        try:
            algo = ChecksumAlgorithm(algorithm)
        except ValueError:
            logger.warning(f"Unknown checksum algorithm in settings: {algorithm}")
            return None

        if algo is ChecksumAlgorithm.NONE:
            return None

        size = checksum.byte_length(algo)
        offset = int(self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_OFFSET, -1))
        lead = int(self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_EXCLUDE_LEADING, 0))
        trail = int(self.settings_manager.get(ConfigKeys.PACKET_CHECKSUM_EXCLUDE_TRAILING, 0))

        # 음수 오프셋은 "끝에서부터" — 체크섬은 대개 말미에 있다.
        start = (len(raw_data) + offset + 1 - size) if offset < 0 else offset
        if start < 0 or start + size > len(raw_data):
            return None

        expected = int.from_bytes(raw_data[start:start + size], byteorder="big")

        target = raw_data[lead:len(raw_data) - trail] if trail else raw_data[lead:]
        if not target:
            return None

        return checksum.verify(algo, target, expected)

    def _flush_pending_packets(self) -> None:
        """
        버퍼링된 패킷을 순서대로 View에 반영합니다 (Timer Slot, S-061).

        Logic:
            - 버퍼가 비어있으면 즉시 리턴
            - 현재 버퍼를 스냅샷하고 즉시 비움 (flush 도중 들어오는 새 패킷과
              분리 — 이번 flush 대상에는 영향 없음, 다음 flush에서 처리됨)
            - 대기 중인 개수가 View의 표시 버퍼 크기(buffer_size)를 넘으면,
              그중 앞부분(가장 오래된 것들)은 하나씩 넣더라도 View의 고정
              크기 버퍼(deque, 링버퍼)에서 즉시 밀려나 화면에 한 번도 보이지
              못한다 — 최종 표시 결과가 달라지지 않으므로 건너뛴다. 실측(S-061)
              결과, 대량 backlog를 통째로 다 넣으면 단일 flush가 1초 이상
              걸릴 수 있어(개선 전보다 오히려 나쁨) 이 컷이 필요했다.
            - 나머지(최근 buffer_size개)를 수신 순서 그대로 View에 반영
              (순서 보장, "화면에 남을 수 있는" 패킷의 유실은 없음)
        """
        if not self._pending_packets:
            return

        pending = self._pending_packets
        self._pending_packets = []

        if self._buffer_size > 0 and len(pending) > self._buffer_size:
            pending = pending[-self._buffer_size:]

        for view_data in pending:
            self.panel.append_packet(view_data)

    def stop(self) -> None:
        """
        Presenter를 정지합니다 (앱 종료 시 호출, S-061).

        Logic:
            - 타이머를 멈춰 이후 flush가 더는 예약되지 않게 한다.
            - 버퍼에 남아있는 패킷을 즉시 flush한다 — 조용히 버리지 않는다
              (S-039/S-045/S-059와 동일한 원칙).
        """
        self._flush_timer.stop()
        self._flush_pending_packets()

    def on_settings_changed(self, state: PreferencesState) -> None:
        """
        전역 설정 변경 시 호출되는 핸들러

        Logic:
            - 패킷 관련 설정(버퍼, 오토스크롤)이 변경되었는지 확인하고 View 업데이트
            - 캡처 상태(Realtime) 동기화

        Args:
            state (PreferencesState): 변경된 설정 상태 DTO.
        """
        # View Facade 메서드 사용
        self._buffer_size = state.packet_buffer_size
        self.panel.set_buffer_size(state.packet_buffer_size)
        self.panel.set_autoscroll(state.packet_autoscroll)

        # 캡처 상태가 외부 설정에 의해 변경된 경우 반영
        if self._is_capturing != state.packet_realtime:
            self._is_capturing = state.packet_realtime
            self.panel.set_capture_state(state.packet_realtime)

    def on_clear_requested(self) -> None:
        """
        View의 Clear 버튼 클릭 요청 처리

        Logic:
            - 아직 flush되지 않은 버퍼도 함께 비운다 — 그렇지 않으면 Clear 직후
              지연되어 있던 이전 패킷들이 다음 flush 주기에 다시 나타난다 (S-061).
        """
        self._pending_packets.clear()
        self.panel.clear_view()
        logger.debug("Packet view cleared by user.")

    def on_capture_toggled(self, enabled: bool) -> None:
        """
        View의 캡처 토글 버튼 클릭 요청 처리

        Args:
            enabled (bool): 캡처 활성화 여부.
        """
        self._is_capturing = enabled
        logger.debug(f"Packet capture state changed: {enabled}")