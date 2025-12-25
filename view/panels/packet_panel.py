"""
패킷 분석 패널 모듈

수신된 패킷 데이터를 테이블 형태로 시각화하고 분석 도구를 제공합니다.

## WHY
* 수신 데이터를 단순 로그가 아닌 구조화된 패킷 단위로 분석 필요
* HEX/ASCII 데이터의 동시 확인 및 패킷 타입 식별 필요
* 대량의 패킷 데이터에 대한 버퍼링 및 실시간 제어(일시정지/재개) 필요

## WHAT
* QTableView 기반의 패킷 목록 표시
* PacketModel을 통한 데이터 관리 및 버퍼 크기 제한
* 캡처 제어(Start/Stop) 및 초기화(Clear) 툴바
* 자동 스크롤 제어

## HOW
* QAbstractTableModel을 상속받아 고성능 데이터 모델 구현
* deque를 사용하여 고정 크기 버퍼(Ring Buffer) 구현
* Presenter로부터 DTO(PacketViewData)를 받아 모델 업데이트
"""
from typing import List, Any
from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QCheckBox, QHeaderView, QLabel, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex, QVariant

from view.managers.language_manager import language_manager
from common.dtos import PacketViewData


class PacketModel(QAbstractTableModel):
    """
    패킷 데이터를 관리하는 테이블 모델 클래스

    QAbstractTableModel을 상속받아 QTableView에 데이터를 제공합니다.
    최대 버퍼 크기를 관리하여 메모리 사용량을 제어합니다.
    """

    # 컬럼 정의
    COLUMNS = ["Time", "Type", "HEX", "ASCII"]

    def __init__(self, buffer_size: int = 100):
        """
        PacketModel 초기화

        Args:
            buffer_size (int): 최대 패킷 저장 개수.
        """
        super().__init__()
        self._buffer_size = buffer_size
        self._data: deque = deque(maxlen=buffer_size)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """행 개수 반환"""
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """열 개수 반환"""
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """
        데이터 반환 (DisplayRole)

        Args:
            index (QModelIndex): 요청 인덱스.
            role (int): 데이터 역할.

        Returns:
            Any: 셀 데이터.
        """
        if not index.isValid() or role != Qt.DisplayRole:
            return QVariant()

        packet = self._data[index.row()]
        col = index.column()

        if col == 0:
            return packet.time_str
        elif col == 1:
            return packet.packet_type
        elif col == 2:
            return packet.data_hex
        elif col == 3:
            return packet.data_ascii
        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        """헤더 데이터 반환"""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return QVariant()

    def append_packet(self, packet: PacketViewData) -> None:
        """
        패킷 데이터를 추가합니다.
        버퍼가 가득 찬 경우 가장 오래된 데이터를 제거합니다.

        Args:
            packet (PacketViewData): 추가할 패킷 데이터 DTO.
        """
        # 버퍼가 가득 찼다면 행 제거 신호를 보냄
        if len(self._data) >= self._buffer_size:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            # deque는 자동으로 오래된 것을 밀어내지만, Qt View 갱신을 위해 명시적으로 알림 필요
            # 그러나 deque의 append는 기존 데이터를 덮어쓰거나 밀어내므로
            # 여기서는 beginInsertRows 전에 remove를 먼저 처리하는 것이 안전함.
            # 하지만 deque 특성상 append 시 자동 popleft가 발생하므로,
            # Qt 모델 동기화를 위해 popleft를 먼저 수행.
            self._data.popleft()
            self.endRemoveRows()

        # 새 행 추가
        row = len(self._data)
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.append(packet)
        self.endInsertRows()

    def clear(self) -> None:
        """모든 데이터 삭제"""
        self.beginResetModel()
        self._data.clear()
        self.endResetModel()

    def set_buffer_size(self, size: int) -> None:
        """
        버퍼 크기를 변경합니다.
        기존 데이터는 유지하되, 새 크기에 맞춰 조정됩니다.

        Args:
            size (int): 새 버퍼 크기.
        """
        if size == self._buffer_size:
            return

        self.beginResetModel()
        self._buffer_size = size
        # deque 리사이징 (새 maxlen 적용)
        self._data = deque(self._data, maxlen=size)
        self.endResetModel()


class PacketPanel(QWidget):
    """
    패킷 분석 뷰 위젯

    QTableView와 제어 도구(Toolbar)를 포함합니다.
    """

    # 사용자 액션 시그널
    clear_requested = pyqtSignal()
    capture_toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget = None) -> None:
        """
        PacketPanel 초기화

        Args:
            parent (QWidget, optional): 부모 위젯.
        """
        super().__init__(parent)

        # UI 컴포넌트
        self.packet_table: QTableView = None
        self.packet_model: PacketModel = None
        self.autoscroll_chk: QCheckBox = None
        self.capture_chk: QCheckBox = None
        self.clear_btn: QPushButton = None

        self._autoscroll_enabled = True

        self.init_ui()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 구성 및 레이아웃 설정"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 1. 툴바 (Toolbar)
        toolbar_layout = QHBoxLayout()

        # 타이틀
        self.title_lbl = QLabel(language_manager.get_text("packet_panel_title", "Packet Inspector"))
        self.title_lbl.setProperty("class", "section-title")

        # 제어 버튼들
        self.capture_chk = QCheckBox(language_manager.get_text("packet_capture_chk", "Capture"))
        self.capture_chk.setChecked(True)
        self.capture_chk.toggled.connect(self.capture_toggled.emit)

        self.autoscroll_chk = QCheckBox(language_manager.get_text("packet_autoscroll_chk", "Auto Scroll"))
        self.autoscroll_chk.setChecked(True)
        self.autoscroll_chk.toggled.connect(self._on_autoscroll_toggled)

        self.clear_btn = QPushButton(language_manager.get_text("packet_panel_btn_clear"))
        self.clear_btn.clicked.connect(self.clear_requested.emit)

        toolbar_layout.addWidget(self.title_lbl)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.capture_chk)
        toolbar_layout.addWidget(self.autoscroll_chk)
        toolbar_layout.addWidget(self.clear_btn)

        # 2. 패킷 테이블 (Table View)
        self.packet_table = QTableView()
        self.packet_model = PacketModel()
        self.packet_table.setModel(self.packet_model)

        # 테이블 스타일 설정
        self.packet_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.packet_table.setAlternatingRowColors(True)
        self.packet_table.verticalHeader().setVisible(False)
        self.packet_table.setProperty("class", "fixed-font")

        # 컬럼 너비 조정
        header = self.packet_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Type
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # HEX (가변)
        header.setSectionResizeMode(3, QHeaderView.Stretch)          # ASCII (가변)

        layout.addLayout(toolbar_layout)
        layout.addWidget(self.packet_table)

    def retranslate_ui(self) -> None:
        """언어 변경 시 텍스트 업데이트"""
        self.title_lbl.setText(language_manager.get_text("packet_panel_title"))
        self.clear_btn.setText(language_manager.get_text("packet_panel_btn_clear"))
        self.capture_chk.setText(language_manager.get_text("packet_panel_chk_capture"))
        self.autoscroll_chk.setText(language_manager.get_text("packet_panel_chk_autoscroll"))
        # 타이틀 라벨 업데이트 로직 필요 시 추가 (객체 참조 저장 필요)

    # -------------------------------------------------------------------------
    # Public Methods (Presenter에서 호출)
    # -------------------------------------------------------------------------
    def set_buffer_size(self, size: int) -> None:
        """
        패킷 버퍼 크기를 설정합니다.

        Args:
            size (int): 버퍼 크기.
        """
        self.packet_model.set_buffer_size(size)

    def set_autoscroll(self, enabled: bool) -> None:
        """
        자동 스크롤 설정을 변경합니다 (설정 로드 시).

        Args:
            enabled (bool): 활성화 여부.
        """
        self._autoscroll_enabled = enabled
        self.autoscroll_chk.setChecked(enabled)

    def set_capture_state(self, enabled: bool) -> None:
        """
        캡처 상태를 UI에 반영합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self.capture_chk.setChecked(enabled)

    def append_packet(self, data: PacketViewData) -> None:
        """
        새 패킷 데이터를 뷰에 추가합니다.

        Args:
            data (PacketViewData): 패킷 데이터 DTO.
        """
        self.packet_model.append_packet(data)

        if self._autoscroll_enabled:
            self.packet_table.scrollToBottom()

    def clear_view(self) -> None:
        """테이블 뷰를 초기화합니다."""
        self.packet_model.clear()

    # -------------------------------------------------------------------------
    # Internal Slots
    # -------------------------------------------------------------------------
    def _on_autoscroll_toggled(self, checked: bool) -> None:
        """
        자동 스크롤 체크박스 토글 핸들러

        Args:
            checked (bool): 체크 상태.
        """
        self._autoscroll_enabled = checked
        if checked:
            self.packet_table.scrollToBottom()