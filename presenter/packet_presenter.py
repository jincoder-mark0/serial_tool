"""
패킷 프레젠터 모듈

패킷 분석 뷰(PacketPanel)와 데이터 소스(EventRouter)를 연결하고 관리합니다.

## WHY
* 실시간 패킷 데이터의 UI 업데이트 로직 분리 (MVP 패턴)
* 패킷 파싱 데이터의 시각화 형식(Hex/ASCII) 변환 담당
* 대량 패킷 수신 시 UI 버퍼링 및 설정 동기화 관리

## WHAT
* PacketPanel(View)과 EventRouter(Model Interface) 연결
* 패킷 수신 이벤트(PacketEvent) 처리 및 View 데이터(PacketViewData) 변환
* 설정 변경(버퍼 크기, 색상 등)에 따른 View 업데이트
* 캡처 시작/정지 및 초기화 제어

## HOW
* EventRouter의 시그널을 구독하여 패킷 수신
* DTO 변환 후 View의 append_packet 메서드 호출
* SettingsManager를 통해 초기 설정 로드 및 변경 사항 반영
"""
from typing import Optional
from PyQt5.QtCore import QObject, QDateTime

from view.panels.packet_panel import PacketPanel
from presenter.event_router import EventRouter
from core.settings_manager import SettingsManager
from core.logger import logger
from common.constants import ConfigKeys
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

        # 1. 초기 설정 적용
        self._apply_initial_settings()

        # 2. View 시그널 연결 (Facade Signal)
        self.panel.clear_requested.connect(self.on_clear_requested)
        self.panel.capture_toggled.connect(self.on_capture_toggled)

        # 3. EventRouter 시그널 연결
        self.event_router.packet_received.connect(self.on_packet_received)
        self.event_router.settings_changed.connect(self.on_settings_changed)

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
            data_ascii=data_ascii
        )

        # View 업데이트 (Facade Method)
        self.panel.append_packet(view_data)

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
        self.panel.set_buffer_size(state.packet_buffer_size)
        self.panel.set_autoscroll(state.packet_autoscroll)

        # 캡처 상태가 외부 설정에 의해 변경된 경우 반영
        if self._is_capturing != state.packet_realtime:
            self._is_capturing = state.packet_realtime
            self.panel.set_capture_state(state.packet_realtime)

    def on_clear_requested(self) -> None:
        """
        View의 Clear 버튼 클릭 요청 처리
        """
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