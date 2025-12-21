"""
데이터 처리 핸들러 모듈

Fast Path를 통한 고속 데이터 수신 처리 및 UI 업데이트 스로틀링 로직을 담당합니다.

## WHY
* MainPresenter의 비대화 방지 및 데이터 흐름 로직 캡슐화
* 고속 처리 로직의 독립적 관리 및 성능 최적화
* View 내부 구조에 대한 의존성 제거 (Decoupling)

## WHAT
* Fast Path 수신 처리 (파일 로깅, 통계 집계)
* UI 업데이트 버퍼링 및 플러싱 (Throttling)
* DTO 기반 데이터 전달

## HOW
* QTimer를 사용한 배치 처리 (30ms 간격)
* View Interface (append_rx_data) 호출을 통한 UI 갱신
* DTO(PortDataEvent, LogDataBatch)를 사용하여 타입 안전성 확보
"""
from collections import defaultdict
from PyQt5.QtCore import QObject, QTimer

from core.data_logger import data_logger_manager
from view.main_window import MainWindow
from common.dtos import PortDataEvent, LogDataBatch


class DataTrafficHandler(QObject):
    """
    데이터 트래픽 처리 핸들러 클래스

    고속으로 들어오는 데이터를 버퍼링하고, 일정 주기마다 UI에 반영하여
    메인 스레드의 부하를 줄입니다 (UI Throttling).
    """

    def __init__(self, view: MainWindow):
        """
        DataTrafficHandler 초기화

        Args:
            view (MainWindow): 메인 윈도우 뷰 인스턴스.
        """
        super().__init__()
        self.view = view

        # 포트별 수신 데이터 버퍼 (포트이름 -> bytearray)
        self._rx_buffer = defaultdict(bytearray)

        # 통계 카운터
        self.rx_byte_count = 0
        self.tx_byte_count = 0

        # UI 업데이트 타이머 (Throttling)
        self._ui_refresh_timer = QTimer()
        self._ui_refresh_timer.setInterval(30)  # 30ms (약 33 FPS)
        self._ui_refresh_timer.timeout.connect(self._flush_rx_buffer_to_ui)
        self._ui_refresh_timer.start()

    def on_fast_data_received(self, event: PortDataEvent) -> None:
        """
        고속 데이터 수신 핸들러 (Fast Path)

        Logic:
            1. DTO에서 데이터 추출
            2. 파일 로깅 (지연 없이 즉시 수행)
            3. 통계 집계 (RX 바이트)
            4. UI 버퍼에 데이터 추가 (나중에 타이머에 의해 플러시)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트 DTO.
        """
        port_name = event.port
        data = event.data

        if not data:
            return

        # 1. 파일 로깅 (DataLoggerManager 위임)
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        # 2. 통계 집계
        self.rx_byte_count += len(data)

        # 3. UI 업데이트 버퍼링
        self._rx_buffer[port_name].extend(data)

    def on_data_sent(self, event: PortDataEvent) -> None:
        """
        데이터 송신 핸들러

        Logic:
            1. 송신 데이터 파일 로깅 (전이중 레코딩 지원)
            2. 통계 집계 (TX 바이트)

        Args:
            event (PortDataEvent): 포트 데이터 이벤트 DTO.
        """
        port_name = event.port
        data = event.data

        # 송신 데이터도 로깅 (Full Duplex)
        if data_logger_manager.is_logging(port_name):
            data_logger_manager.write(port_name, data)

        self.tx_byte_count += len(data)

    def _flush_rx_buffer_to_ui(self) -> None:
        """
        버퍼링된 데이터를 UI에 반영합니다. (Timer Slot)

        Logic:
            - 버퍼가 비어있으면 리턴
            - 버퍼에 데이터가 있는 포트 목록 순회
            - DTO(LogDataBatch) 생성하여 View 인터페이스 호출
            - 처리된 버퍼 비우기
        """
        if not self._rx_buffer:
            return

        # 처리할 데이터가 있는 포트 목록 복사 (Dictionary size change 방지)
        pending_ports = list(self._rx_buffer.keys())

        for port_name in pending_ports:
            data = self._rx_buffer[port_name]
            if not data:
                continue

            # bytes로 변환
            data_bytes = bytes(data)

            # View 전달용 DTO 생성
            batch = LogDataBatch(port=port_name, data=data_bytes)

            # View Interface 호출 (Decoupling)
            self.view.append_rx_data(batch)

            # 버퍼 비우기 (해당 포트 키 삭제)
            del self._rx_buffer[port_name]

    def stop(self) -> None:
        """핸들러를 중지하고 타이머를 끕니다."""
        self._ui_refresh_timer.stop()

    def reset_counts(self) -> None:
        """통계 카운터를 초기화합니다 (주기적 속도 계산 후 호출)."""
        self.rx_byte_count = 0
        self.tx_byte_count = 0