"""
패킷 프레젠터 모듈

패킷 인스펙터의 비즈니스 로직을 담당합니다.

## WHY
* 패킷 데이터의 포맷팅 및 가공 로직을 View에서 분리
* Model 이벤트(packet_received)와 View 업데이트 연결
* 사용자 설정(설정값) 반영

## WHAT
* 패킷 수신 이벤트 처리
* 데이터 포맷팅 (Timestamp, Hex, ASCII)
* 설정값(Buffer Size, Autoscroll) 로드 및 적용

## HOW
* EventRouter 시그널 구독
* SettingsManager 설정값 조회
* View 인터페이스(PacketInspectorPanel) 호출
"""
from PyQt5.QtCore import QObject, QDateTime
from view.panels.packet_inspector_panel import PacketInspectorPanel
from presenter.event_router import EventRouter
from core.settings_manager import SettingsManager
from constants import ConfigKeys

class PacketPresenter(QObject):
    """
    패킷 인스펙터 제어 Presenter

    Model로부터 수신된 패킷 데이터를 가공하여 View에 표시하도록 지시합니다.
    """

    def __init__(self, view: PacketInspectorPanel, event_router: EventRouter) -> None:
        """
        PacketPresenter 초기화

        Args:
            view (PacketInspectorPanel): 패킷 인스펙터 뷰
            event_router (EventRouter): 이벤트 라우터
        """
        super().__init__()
        self.view = view
        self.event_router = event_router

        # 설정 관리자
        self.settings_manager = SettingsManager()

        # 이벤트 구독
        self.event_router.packet_received.connect(self.on_packet_received)

        # 초기 설정 적용
        self.apply_settings()

    def apply_settings(self) -> None:
        """
        설정 파일에서 값을 읽어 View에 적용합니다.

        Logic:
            - SettingsManager에서 버퍼 크기 및 자동 스크롤 설정 조회
            - View에 설정값 전달
        """
        buffer_size = self.settings_manager.get(ConfigKeys.INSPECTOR_BUFFER_SIZE, 100)
        auto_scroll = self.settings_manager.get(ConfigKeys.INSPECTOR_AUTOSCROLL, True)

        self.view.set_inspector_options(buffer_size, auto_scroll)

    def on_packet_received(self, port_name: str, packet: object) -> None:
        """
        패킷 수신 이벤트 핸들러

        Logic:
            - 실시간 추적 설정 확인
            - 타임스탬프 포맷팅 (HH:mm:ss.zzz)
            - 데이터 포맷팅 (Hex, ASCII)
            - View에 데이터 추가 요청

        Args:
            port_name (str): 포트 이름
            packet (Packet): 수신된 패킷 객체 (model.packet_parser.Packet)
        """
        # 실시간 추적 옵션 확인
        realtime = self.settings_manager.get(ConfigKeys.INSPECTOR_REALTIME, True)
        if not realtime:
            return

        # 데이터 가공
        timestamp = QDateTime.fromMSecsSinceEpoch(int(packet.timestamp * 1000))
        time_str = timestamp.toString("HH:mm:ss.zzz")

        packet_type = "Raw"
        if packet.metadata and "type" in packet.metadata:
            packet_type = packet.metadata["type"]

        data_bytes = packet.data

        # HEX 포맷팅 (예: 41 42 43)
        data_hex = " ".join([f"{b:02X}" for b in data_bytes])

        # ASCII 포맷팅 (제어 문자는 .으로 대체)
        try:
            data_ascii = "".join([chr(b) if 32 <= b <= 126 else "." for b in data_bytes])
        except Exception:
            data_ascii = str(data_bytes)

        # View 업데이트
        self.view.add_packet_to_view(time_str, packet_type, data_hex, data_ascii)

    def on_clear_requested(self) -> None:
        """로그 지우기 요청 처리"""
        self.view.clear_view()
