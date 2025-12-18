"""
패킷 인스펙터 패널 모듈

PacketWidget을 래핑하고 Presenter와의 인터페이스를 제공합니다.

## WHY
* 패킷 분석 뷰와 제어 버튼(Clear 등)의 레이아웃 관리
* Presenter에 추상화된 데이터 입력 인터페이스 제공

## WHAT
* PacketWidget 배치 및 헤더(Clear 버튼) 구성
* 패킷 데이터 추가 및 옵션 설정 메서드 제공

## HOW
* QVBoxLayout 및 QHBoxLayout 사용
* View 로직 없이 UI 조작 메서드만 노출
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import pyqtSignal
from typing import Optional
from view.managers.language_manager import language_manager
from view.widgets.packet import PacketWidget

class PacketPanel(QWidget):
    """
    PacketWidget을 감싸는 패널 클래스

    Attributes:
        packet_widget (PacketWidget): 패킷 뷰 위젯
        clear_btn (QPushButton): 로그 초기화 버튼
    """

    # 초기화 요청 시그널
    clear_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PacketPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.packet_widget = None
        self.clear_btn: Optional[QPushButton] = None
        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 헤더 영역 (Clear 버튼 배치)
        header_layout = QHBoxLayout()
        header_layout.addStretch()

        self.clear_btn = QPushButton(language_manager.get_text("packet_panel_btn_clear"))
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.clicked.connect(self.clear_requested.emit)

        header_layout.addWidget(self.clear_btn)

        layout.addLayout(header_layout)

        # 패킷 인스펙터 위젯 추가
        self.packet_widget = PacketWidget()
        layout.addWidget(self.packet_widget)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트 업데이트"""
        self.clear_btn.setText(language_manager.get_text("packet_panel_btn_clear"))

    def append_packet(self, time_str: str, packet_type: str, data_hex: str, data_ascii: str) -> None:
        """
        패킷 데이터를 뷰에 추가

        Args:
            time_str (str): 시간 문자열
            packet_type (str): 패킷 타입
            data_hex (str): Hex 데이터
            data_ascii (str): ASCII 데이터
        """
        if self.packet_widget:
            self.packet_widget.add_packet(time_str, packet_type, data_hex, data_ascii)

    def set_packet_options(self, buffer_size: int, auto_scroll: bool) -> None:
        """
        인스펙터 옵션 설정

        Args:
            buffer_size (int): 버퍼 크기
            auto_scroll (bool): 자동 스크롤 여부
        """
        if self.packet_widget:
            self.packet_widget.set_buffer_size(buffer_size)
            self.packet_widget.set_auto_scroll(auto_scroll)

    def clear_view(self) -> None:
        """뷰 내용 초기화"""
        if self.packet_widget:
            self.packet_widget.clear()
