"""
패킷 분석 패널 모듈

수신된 패킷 데이터를 테이블 형태로 시각화하고 분석 도구를 제공합니다.

## WHY
* 수신 데이터를 단순 로그가 아닌 구조화된 패킷 단위로 분석 필요
* HEX/ASCII 데이터의 동시 확인 및 패킷 타입 식별 필요
* 대량의 패킷 데이터에 대한 버퍼링 및 실시간 제어(일시정지/재개) 필요
* 선택된 packet에 note를 붙이고 여러 형식으로 export하는 분석 workflow 필요

## WHAT
* QTableView 기반의 패킷 목록 표시
* PacketModel을 통한 데이터 관리 및 버퍼 크기 제한
* 캡처 제어(Start/Stop) 및 초기화(Clear) 툴바
* declarative packet filter 입력/활성화/오류 표시
* selected-row annotation / export request UI

## HOW
* QAbstractTableModel을 상속받아 고성능 데이터 모델 구현
* deque를 사용하여 고정 크기 버퍼(Ring Buffer) 구현
* 표시용 PacketViewData와 export/annotation용 immutable PacketRecord를 parallel 보관
* View는 selection/dialog만 담당하고 annotation 저장/file I/O는 Presenter/Model에 위임
"""
from collections import deque
from typing import Any

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from common.constants import LAYOUT_MARGIN_NONE, LAYOUT_SPACING_TIGHT
from common.dtos import PacketViewData
from common.packet_records import PacketRecord
from view.managers.language_manager import language_manager

_FILTER_SYNTAX_EXAMPLE = "type=AT; len=8..32; ascii*=OK"


class PacketModel(QAbstractTableModel):
    """패킷 표시 DTO와 immutable record snapshot을 함께 관리하는 bounded model."""

    COLUMN_KEYS = [
        "packet_col_time",
        "packet_col_type",
        "packet_col_hex",
        "packet_col_ascii",
        "packet_col_checksum",
        None,  # Annotation: 기술 용어이므로 현재는 "Note" 고정 표기
    ]

    CHECKSUM_PASS_TEXT = "OK"
    CHECKSUM_FAIL_TEXT = "FAIL"
    ANNOTATION_HEADER = "Note"

    def __init__(self, buffer_size: int = 100):
        super().__init__()
        self._buffer_size = buffer_size
        self._data: deque[PacketViewData] = deque(maxlen=buffer_size)
        self._records: deque[PacketRecord | None] = deque(maxlen=buffer_size)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.COLUMN_KEYS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return QVariant()

        packet = self._data[index.row()]
        record = self._records[index.row()]
        col = index.column()

        if role == Qt.ToolTipRole and record is not None and record.annotation:
            return record.annotation
        if role != Qt.DisplayRole:
            return QVariant()

        if col == 0:
            return packet.time_str
        if col == 1:
            return packet.packet_type
        if col == 2:
            return packet.data_hex
        if col == 3:
            return packet.data_ascii
        if col == 4:
            if packet.checksum_ok is None:
                return ""
            return self.CHECKSUM_PASS_TEXT if packet.checksum_ok else self.CHECKSUM_FAIL_TEXT
        if col == 5:
            return record.annotation if record is not None else ""
        return QVariant()

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            key = self.COLUMN_KEYS[section]
            return language_manager.get_text(key) if key else self.ANNOTATION_HEADER
        return QVariant()

    def retranslate_headers(self) -> None:
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.COLUMN_KEYS) - 1)

    def append_packet(
        self,
        packet: PacketViewData,
        record: PacketRecord | None = None,
    ) -> None:
        if len(self._data) >= self._buffer_size:
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._data.popleft()
            self._records.popleft()
            self.endRemoveRows()

        row = len(self._data)
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.append(packet)
        self._records.append(record)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._data.clear()
        self._records.clear()
        self.endResetModel()

    def set_buffer_size(self, size: int) -> None:
        if size == self._buffer_size:
            return

        self.beginResetModel()
        self._buffer_size = size
        self._data = deque(self._data, maxlen=size)
        self._records = deque(self._records, maxlen=size)
        self.endResetModel()

    def records_for_rows(self, rows: list[int]) -> tuple[PacketRecord, ...]:
        records: list[PacketRecord] = []
        for row in sorted(set(rows)):
            if 0 <= row < len(self._records):
                record = self._records[row]
                if record is not None:
                    records.append(record)
        return tuple(records)

    def set_annotation(self, packet_ids: tuple[str, ...], note: str) -> None:
        targets = set(packet_ids)
        if not targets:
            return

        changed_rows: list[int] = []
        for row, record in enumerate(self._records):
            if record is not None and record.packet_id in targets:
                self._records[row] = record.with_annotation(note)
                changed_rows.append(row)

        for row in changed_rows:
            index = self.index(row, 5)
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.ToolTipRole])


class PacketPanel(QWidget):
    """Packet Presenter에 passive facade를 제공하는 분석 패널."""

    clear_requested = pyqtSignal()
    capture_toggled = pyqtSignal(bool)
    filter_toggled = pyqtSignal(bool)
    filter_expression_changed = pyqtSignal(str)
    annotation_requested = pyqtSignal(object, str)
    export_requested = pyqtSignal(object, str, str)

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

        self._packet_table: QTableView = None
        self._packet_model: PacketModel = None
        self._autoscroll_chk: QCheckBox = None
        self._capture_chk: QCheckBox = None
        self._filter_chk: QCheckBox = None
        self._filter_edit: QLineEdit = None
        self._filter_error_lbl: QLabel = None
        self._annotate_btn: QPushButton = None
        self._export_btn: QPushButton = None
        self._clear_btn: QPushButton = None
        self._title_lbl: QLabel = None

        self._autoscroll_enabled = True

        self.init_ui()
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
        )
        layout.setSpacing(LAYOUT_SPACING_TIGHT)

        toolbar_layout = QHBoxLayout()

        self._title_lbl = QLabel(language_manager.get_text("packet_grp_title"))
        self._title_lbl.setProperty("class", "section-title")
        self._title_lbl.setToolTip(language_manager.get_text("packet_grp_title_tooltip"))

        self._capture_chk = QCheckBox(language_manager.get_text("packet_chk_capture"))
        self._capture_chk.setChecked(True)
        self._capture_chk.setToolTip(language_manager.get_text("packet_chk_capture_tooltip"))
        self._capture_chk.toggled.connect(self.capture_toggled.emit)

        self._autoscroll_chk = QCheckBox(language_manager.get_text("packet_chk_autoscroll"))
        self._autoscroll_chk.setChecked(True)
        self._autoscroll_chk.setToolTip(language_manager.get_text("packet_chk_autoscroll_tooltip"))
        self._autoscroll_chk.toggled.connect(self._on_autoscroll_toggled)

        self._filter_chk = QCheckBox(language_manager.get_text("data_log_chk_filter"))
        self._filter_chk.setChecked(False)
        self._filter_chk.setToolTip(
            language_manager.get_text("data_log_chk_filter_tooltip")
        )
        self._filter_chk.toggled.connect(self.filter_toggled.emit)

        self._filter_edit = QLineEdit()
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setPlaceholderText(_FILTER_SYNTAX_EXAMPLE)
        self._filter_edit.setToolTip(_FILTER_SYNTAX_EXAMPLE)
        self._filter_edit.editingFinished.connect(self._emit_filter_expression)

        self._annotate_btn = QPushButton("Note")
        self._annotate_btn.setToolTip("Add or clear note for selected packet rows")
        self._annotate_btn.clicked.connect(self._request_annotation)

        self._export_btn = QPushButton("Export")
        self._export_btn.setToolTip("Export selected packet rows")
        self._export_btn.clicked.connect(self._request_export)

        self._clear_btn = QPushButton(language_manager.get_text("packet_btn_clear"))
        self._clear_btn.setToolTip(language_manager.get_text("packet_btn_clear_tooltip"))
        self._clear_btn.clicked.connect(self.clear_requested.emit)

        toolbar_layout.addWidget(self._title_lbl)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self._filter_chk)
        toolbar_layout.addWidget(self._filter_edit, 1)
        toolbar_layout.addWidget(self._annotate_btn)
        toolbar_layout.addWidget(self._export_btn)
        toolbar_layout.addWidget(self._capture_chk)
        toolbar_layout.addWidget(self._autoscroll_chk)
        toolbar_layout.addWidget(self._clear_btn)

        self._filter_error_lbl = QLabel("")
        self._filter_error_lbl.setProperty("class", "error-text")
        self._filter_error_lbl.setVisible(False)
        self._filter_error_lbl.setWordWrap(True)

        self._packet_table = QTableView()
        self._packet_model = PacketModel()
        self._columns_sized = False
        self._packet_table.setModel(self._packet_model)

        self._packet_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._packet_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._packet_table.setAlternatingRowColors(True)
        self._packet_table.verticalHeader().setVisible(False)
        self._packet_table.setProperty("class", "fixed-font")

        header = self._packet_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        layout.addLayout(toolbar_layout)
        layout.addWidget(self._filter_error_lbl)
        layout.addWidget(self._packet_table)

    def retranslate_ui(self) -> None:
        self._title_lbl.setText(language_manager.get_text("packet_grp_title"))
        self._title_lbl.setToolTip(language_manager.get_text("packet_grp_title_tooltip"))
        self._clear_btn.setText(language_manager.get_text("packet_btn_clear"))
        self._clear_btn.setToolTip(language_manager.get_text("packet_btn_clear_tooltip"))
        self._capture_chk.setText(language_manager.get_text("packet_chk_capture"))
        self._capture_chk.setToolTip(language_manager.get_text("packet_chk_capture_tooltip"))
        self._autoscroll_chk.setText(language_manager.get_text("packet_chk_autoscroll"))
        self._autoscroll_chk.setToolTip(language_manager.get_text("packet_chk_autoscroll_tooltip"))
        self._filter_chk.setText(language_manager.get_text("data_log_chk_filter"))
        self._filter_chk.setToolTip(
            language_manager.get_text("data_log_chk_filter_tooltip")
        )
        self._filter_edit.setPlaceholderText(_FILTER_SYNTAX_EXAMPLE)
        self._filter_edit.setToolTip(_FILTER_SYNTAX_EXAMPLE)
        self._packet_model.retranslate_headers()

    def set_buffer_size(self, size: int) -> None:
        self._packet_model.set_buffer_size(size)

    def set_autoscroll(self, enabled: bool) -> None:
        self._autoscroll_enabled = enabled
        self._autoscroll_chk.setChecked(enabled)

    def set_capture_state(self, enabled: bool) -> None:
        self._capture_chk.setChecked(enabled)

    def set_filter_state(self, enabled: bool) -> None:
        self._filter_chk.setChecked(enabled)

    def set_filter_error(self, message: str) -> None:
        self._filter_error_lbl.setText(message)
        self._filter_error_lbl.setToolTip(message)
        self._filter_error_lbl.setVisible(True)
        self._filter_edit.setProperty("validationError", True)
        self._refresh_filter_style()

    def clear_filter_error(self) -> None:
        self._filter_error_lbl.clear()
        self._filter_error_lbl.setToolTip("")
        self._filter_error_lbl.setVisible(False)
        self._filter_edit.setProperty("validationError", False)
        self._refresh_filter_style()

    def append_packet(
        self,
        data: PacketViewData,
        record: PacketRecord | None = None,
    ) -> None:
        self._packet_model.append_packet(data, record)

        if not self._columns_sized:
            self._columns_sized = True
            self._packet_table.resizeColumnToContents(0)

        if self._autoscroll_enabled:
            self._packet_table.scrollToBottom()

    def set_packet_annotation(self, packet_ids: tuple[str, ...], note: str) -> None:
        self._packet_model.set_annotation(packet_ids, note)

    def clear_view(self) -> None:
        self._packet_model.clear()
        self._columns_sized = False

    def selected_packet_records(self) -> tuple[PacketRecord, ...]:
        rows = sorted({index.row() for index in self._packet_table.selectedIndexes()})
        return self._packet_model.records_for_rows(rows)

    def _emit_filter_expression(self) -> None:
        self.filter_expression_changed.emit(self._filter_edit.text())

    def _request_annotation(self) -> None:
        records = self.selected_packet_records()
        if not records:
            return

        existing = records[0].annotation if len(records) == 1 else ""
        note, accepted = QInputDialog.getText(
            self,
            "Packet Annotation",
            "Note",
            text=existing,
        )
        if accepted:
            self.annotation_requested.emit(
                tuple(record.packet_id for record in records),
                note,
            )

    def _request_export(self) -> None:
        records = self.selected_packet_records()
        if not records:
            return

        filters = (
            "CSV (*.csv);;JSON (*.json);;Hex Text (*.txt);;Raw Binary (*.bin)"
        )
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Packets",
            "",
            filters,
        )
        if not path:
            return

        export_format = self._resolve_export_format(path, selected_filter)
        self.export_requested.emit(records, path, export_format)

    @staticmethod
    def _resolve_export_format(path: str, selected_filter: str) -> str:
        lower_path = path.lower()
        if lower_path.endswith(".json") or selected_filter.startswith("JSON"):
            return "json"
        if lower_path.endswith(".txt") or selected_filter.startswith("Hex"):
            return "hex"
        if lower_path.endswith(".bin") or selected_filter.startswith("Raw"):
            return "raw"
        return "csv"

    def _refresh_filter_style(self) -> None:
        style = self._filter_edit.style()
        style.unpolish(self._filter_edit)
        style.polish(self._filter_edit)
        self._filter_edit.update()

    def _on_autoscroll_toggled(self, checked: bool) -> None:
        self._autoscroll_enabled = checked
        if checked:
            self._packet_table.scrollToBottom()
