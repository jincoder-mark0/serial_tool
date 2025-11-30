from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, 
    QHeaderView, QLabel
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex
from typing import Optional, List

class CommandListWidget(QWidget):
    """
    Command List를 관리하는 위젯입니다.
    명령 추가/삭제/이동 기능을 제공합니다.
    """
    
    # Signals
    send_row_requested = pyqtSignal(int) # row_index
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header / Controls
        header_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕")
        self.add_btn.setToolTip("Add new command step")
        
        self.del_btn = QPushButton("➖")
        self.del_btn.setToolTip("Delete selected step")
        
        self.up_btn = QPushButton("⬆️")
        self.up_btn.setToolTip("Move step up")
        
        self.down_btn = QPushButton("⬇️")
        self.down_btn.setToolTip("Move step down")
        
        header_layout.addWidget(QLabel("Command List"))
        header_layout.addStretch()
        header_layout.addWidget(self.add_btn)
        header_layout.addWidget(self.del_btn)
        header_layout.addWidget(self.up_btn)
        header_layout.addWidget(self.down_btn)
        
        # Connect signals
        self.add_btn.clicked.connect(self.add_empty_row)
        self.del_btn.clicked.connect(self.delete_selected_rows)
        self.up_btn.clicked.connect(self.move_row_up)
        self.down_btn.clicked.connect(self.move_row_down)
        
        # Table View
        self.table_view = QTableView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["", "Command", "HEX", "CR", "Delay", "Send"])
        self.table_view.setModel(self.model)
        self.table_view.setToolTip("List of commands to execute")
        
        # Hide vertical header (row numbers)
        self.table_view.verticalHeader().setVisible(False)
        
        # Selection Mode
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        
        # Adjust column widths
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Checkbox
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # Command
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # HEX
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # CR
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Delay
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Send Btn
        
        layout.addLayout(header_layout)
        layout.addWidget(self.table_view)
        
        self.setLayout(layout)
        
        # Add dummy data
        self.add_dummy_row("AT", False, True, "100")
        self.add_dummy_row("AT+VER?", False, True, "500")

    def add_dummy_row(self, cmd: str, hex_mode: bool, cr: bool, delay: str) -> None:
        """테스트용 더미 데이터 추가"""
        self._append_row(cmd, hex_mode, cr, delay)

    def add_empty_row(self) -> None:
        """빈 행 추가"""
        self._append_row("", False, True, "100")
        
    def _append_row(self, cmd: str, hex_mode: bool, cr: bool, delay: str) -> None:
        row_idx = self.model.rowCount()
        
        # 0: Select Checkbox
        item_select = QStandardItem()
        item_select.setCheckable(True)
        item_select.setCheckState(Qt.Checked)
        item_select.setEditable(False) # Only checkbox is interactive
        
        # 1: Command
        item_cmd = QStandardItem(cmd)
        
        # 2: HEX
        item_hex = QStandardItem()
        item_hex.setCheckable(True)
        item_hex.setCheckState(Qt.Checked if hex_mode else Qt.Unchecked)
        item_hex.setEditable(False)
        
        # 3: CR
        item_cr = QStandardItem()
        item_cr.setCheckable(True)
        item_cr.setCheckState(Qt.Checked if cr else Qt.Unchecked)
        item_cr.setEditable(False)
        
        # 4: Delay
        item_delay = QStandardItem(delay)
        
        # 5: Send (Placeholder)
        item_send = QStandardItem("")
        item_send.setEditable(False)
        
        self.model.appendRow([item_select, item_cmd, item_hex, item_cr, item_delay, item_send])
        
        # Set Send Button
        self._set_send_button(row_idx)

    def _set_send_button(self, row: int) -> None:
        """해당 행에 Send 버튼 설정 (레이아웃 개선)"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setAlignment(Qt.AlignCenter)
        
        btn = QPushButton("Send")
        btn.setCursor(Qt.PointingHandCursor)
        # 초기 상태는 비활성화 (포트 연결 전)
        btn.setEnabled(False) 
        
        # 버튼 클릭 시 해당 버튼의 위치를 찾아 시그널 발생
        btn.clicked.connect(lambda: self._on_send_btn_clicked(btn))
        
        layout.addWidget(btn)
        
        index = self.model.index(row, 5)
        self.table_view.setIndexWidget(index, widget)

    def _on_send_btn_clicked(self, btn: QPushButton) -> None:
        """Send 버튼 클릭 핸들러"""
        # 버튼의 부모 위젯(컨테이너)을 통해 위치 확인
        # btn -> layout -> widget -> table_view
        # viewport mapFromGlobal을 사용하는 것이 가장 정확함
        pos = self.table_view.viewport().mapFromGlobal(btn.mapToGlobal(btn.rect().center()))
        index = self.table_view.indexAt(pos)
        if index.isValid():
            self.send_row_requested.emit(index.row())

    def set_send_enabled(self, enabled: bool) -> None:
        """모든 Send 버튼의 활성화 상태 변경"""
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 5)
            widget = self.table_view.indexWidget(index)
            if widget:
                # widget은 컨테이너이므로 그 안의 버튼을 찾아야 함
                btn = widget.findChild(QPushButton)
                if btn:
                    btn.setEnabled(enabled)

    def delete_selected_rows(self) -> None:
        """선택된 행 삭제"""
        rows = sorted(set(index.row() for index in self.table_view.selectionModel().selectedRows()), reverse=True)
        for row in rows:
            self.model.removeRow(row)
            
    def move_row_up(self) -> None:
        """선택된 행 위로 이동"""
        rows = sorted(set(index.row() for index in self.table_view.selectionModel().selectedRows()))
        if not rows or rows[0] == 0:
            return
            
        # 위에서부터 순서대로 이동해야 인덱스가 꼬이지 않음
        for row in rows:
            self._move_row(row, row - 1)
            
        # Selection 복구
        for row in rows:
            self.table_view.selectRow(row - 1)

    def move_row_down(self) -> None:
        """선택된 행 아래로 이동"""
        rows = sorted(set(index.row() for index in self.table_view.selectionModel().selectedRows()), reverse=True)
        if not rows or rows[0] == self.model.rowCount() - 1:
            return
            
        # 아래에서부터 이동
        for row in rows:
            self._move_row(row, row + 1)
            
        # Selection 복구
        for row in rows:
            self.table_view.selectRow(row + 1)
            
    def _move_row(self, source_row: int, dest_row: int) -> None:
        """행 이동 및 위젯(버튼) 복구"""
        # 1. 데이터 가져오기
        items = self.model.takeRow(source_row)
        
        # 2. 새 위치에 삽입
        self.model.insertRow(dest_row, items)
        
        # 3. 위젯(버튼) 복구
        # 이동 시 기존 위젯은 삭제되므로 새로 생성해야 함
        # 단, 기존 버튼의 활성화 상태를 유지하려면 상태를 저장해야 하지만,
        # 현재는 일괄 제어하므로 새로 생성해도 무방함 (set_send_enabled 호출 필요할 수 있음)
        self._set_send_button(dest_row)
        
        # 현재 활성화 상태에 맞춰 버튼 상태 업데이트 필요
        # (최적화를 위해 상태 변수를 클래스에 저장하는 것이 좋음)
        # 여기서는 간단히 기본값(False)로 생성되므로, 외부에서 상태 관리가 필요함.
        # 개선: 클래스 멤버로 _is_connected 상태 저장

    def get_selected_indices(self) -> List[int]:
        """체크된 항목의 인덱스 리스트 반환"""
        indices: List[int] = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item.checkState() == Qt.Checked:
                indices.append(row)
        return indices
        
    def set_all_checked(self, checked: bool) -> None:
        """모든 항목 체크/해제"""
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            item.setCheckState(state)
