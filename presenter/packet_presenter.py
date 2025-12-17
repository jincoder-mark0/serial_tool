"""
패킷 프레젠터 모듈

패킷 인스펙터의 비즈니스 로직을 담당합니다.

## WHY
* 패킷 데이터의 포맷팅 및 가공 로직을 View에서 분리
* Model 이벤트(packet_received)와 View 업데이트 연결
* 사용자 설정(설정값) 반영 및 Clear 동작 처리

## WHAT
* 패킷 수신 이벤트 처리 및 데이터 포맷팅
* View의 Clear 요청 처리
* 설정값(Buffer Size, Autoscroll) 로드 및 적용
* 설정 변경 이벤트에 따른 즉시 업데이트

## HOW
* EventRouter 시그널 구독
* SettingsManager 주입 (Dependency Injection)
* View 인터페이스(PacketPanel) 호출
"""
from PyQt5.QtCore import QObject, QDateTime
from view.panels.packet_panel import PacketPanel
from presenter.event_router import EventRouter
from core.settings_manager import SettingsManager
from common.constants import ConfigKeys
from common.dtos import PacketEvent, PreferencesState

class PacketPresenter(QObject):
    """
    패킷 인스펙터 제어 Presenter

    Model로부터 수신된 패킷 데이터를 가공하여 View에 표시하고,
    View의 사용자 요청(Clear)을 처리합니다.
    """

    def __init__(self, view: PacketPanel, event_router: EventRouter, settings_manager: SettingsManager) -> None:
        """
        PacketPresenter 초기화

        Args:
            view (PacketPanel): 패킷 인스펙터 뷰
            event_router (EventRouter): 이벤트 라우터
            settings_manager (SettingsManager): 설정 관리자 (주입)
        """
        super().__init__()
        self.view = view
        self.event_router = event_router
        self.settings_manager = settings_manager

        # 이벤트 구독
        self.event_router.packet_received.connect(self.on_packet_received)

        # 설정 변경 이벤트 구독 (EventBus -> EventRouter -> Here)
        self.event_router.settings_changed.connect(self.on_settings_changed)

        # View 시그널 연결 (Clear 버튼)
        self.view.clear_requested.connect(self.on_clear_requested)

        # 초기 설정 적용
        self.apply_settings()

    def apply_settings(self) -> None:
        """
        초기 설정을 로드하여 View에 적용합니다.
        (이후 변경사항은 on_settings_changed로 처리)

        Logic:
            - SettingsManager에서 버퍼 크기 및 자동 스크롤 설정 조회
            - View에 설정값 전달
        """
        buffer_size = self.settings_manager.get(ConfigKeys.PACKET_BUFFER_SIZE, 100)
        auto_scroll = self.settings_manager.get(ConfigKeys.PACKET_AUTOSCROLL, True)

        self.view.set_packet_options(buffer_size, auto_scroll)

    def on_settings_changed(self, state: PreferencesState) -> None:
        """
        설정 변경 이벤트 핸들러

        Args:
            state (PreferencesState): 변경된 설정 DTO
        """
        self.view.set_packet_options(state.packet_buffer_size, state.packet_autoscroll)

    def on_packet_received(self, event: PacketEvent) -> None:
        """
        패킷 수신 이벤트 핸들러

        Logic:
            - 실시간 추적 설정 확인
            - 타임스탬프 포맷팅 (HH:mm:ss.zzz)
            - 데이터 포맷팅 (Hex, ASCII)
            - View에 데이터 추가 요청

        Args:
            event (PacketEvent): 수신된 패킷 이벤트 (DTO)
        """
        packet = event.packet

        if not packet:
            return

        # 실시간 추적 옵션 확인
        realtime = self.settings_manager.get(ConfigKeys.PACKET_REALTIME, True)
        if not realtime:
            return

        # 데이터 가공
        timestamp = QDateTime.fromMSecsSinceEpoch(int(packet.timestamp * 1000))
        time_str = timestamp.toString("HH:mm:ss.zzz")

        packet_type = "Raw"
        if packet.metadata and "type" in packet.metadata:
            packet_type = packet.metadata["type"]

        data_bytes = packet.data

        # HEX 포맷팅
        data_hex = " ".join([f"{b:02X}" for b in data_bytes])

        # ASCII 포맷팅
        try:
            data_ascii = "".join([chr(b) if 32 <= b <= 126 else "." for b in data_bytes])
        except Exception:
            data_ascii = str(data_bytes)

        # View 업데이트
        self.view.add_packet_to_view(time_str, packet_type, data_hex, data_ascii)

    def on_clear_requested(self) -> None:
        """
        로그 지우기 요청 처리

        Logic:
            - View의 clear_view 메서드 호출
        """
        self.view.clear_view()
