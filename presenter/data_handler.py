"""
데이터 처리 핸들러 모듈

Fast Path를 통한 고속 데이터 수신 처리 및 UI 업데이트 스로틀링 로직을 담당합니다.

## WHY
* MainPresenter의 비대화 방지 및 데이터 흐름 로직 캡슐화
* 고속 처리 로직의 독립적 관리
* View 내부 구조에 대한 의존성 제거 (Decoupling)

## WHAT
* Fast Path 수신 처리 (로깅, 통계 집계)
* UI 업데이트 버퍼링 및 플러싱 (Throttling)

## HOW
* QTimer를 사용한 배치 처리
* View Interface (append_rx_data) 호출을 통한 UI 갱신
* DTO(PortDataEvent) 기반 데이터 처리
"""
from collections import defaultdict
from PyQt5.QtCore import QObject, QTimer
from core.data_logger import data_logger_manager
from view.main_window import MainWindow
from common.dtos import PortDataEvent

class DataTrafficHandler(QObject):
    """
    데이터 트래픽 처리 핸들러
    """
    def __init__(self, view: MainWindow):
        super().__init__()
        self.view = view
        self._rx_buffer = defaultdict(bytearray)
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # UI 업데이트 타이머 (Throttling)
        self._ui_refresh_timer = QTimer()
        self._ui_refresh_timer.setInterval(30)
        self._ui_refresh_timer.timeout.connect(self._flush_rx_buffer_to_ui)
        self._ui_refresh_timer.start()

    def on_fast_data_received(self, event: PortDataEvent) -> None:
        """
        고속 데이터 수신 핸들러 (DTO 적용)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트 DTO
        """
        # [Refactor] Unpack DTO
        port_name = event.port
        data = event.data

        if not data:
            return

        # 1. 파일 로깅
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 2. 통계 집계
        self.rx_byte_count += len(data)

        # 3. UI 업데이트 버퍼링
        self._rx_buffer[port_name].extend(data)

    def on_data_sent(self, event: PortDataEvent) -> None:
        """
        데이터 송신 핸들러 (DTO 적용)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트 DTO
        """
        # [Refactor] Unpack DTO
        port_name = event.port
        data = event.data

        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)
        self.tx_byte_count += len(data)

    def _flush_rx_buffer_to_ui(self) -> None:
        """
        버퍼링된 데이터를 UI에 반영

        Logic:
            - 버퍼에 데이터가 있는 포트만 순회
            - View의 공개 인터페이스(append_rx_data)를 호출하여 데이터 전달
            - Handler는 View의 탭 구조나 위젯 타입을 알 필요 없음 (Decoupling)
        """
        if not self._rx_buffer:
            return

        # 처리할 데이터가 있는 포트 목록 복사
        pending_ports = list(self._rx_buffer.keys())

        for port_name in pending_ports:
            data = self._rx_buffer[port_name]
            if not data:
                continue

            data_bytes = bytes(data)

            # View Interface 호출
            self.view.append_rx_data(port_name, data_bytes)

            del self._rx_buffer[port_name]

    def stop(self) -> None:
        """핸들러 중지"""
        self._ui_refresh_timer.stop()

    def reset_counts(self) -> None:
        """카운터 초기화"""
        self.rx_byte_count = 0
        self.tx_byte_count = 0
