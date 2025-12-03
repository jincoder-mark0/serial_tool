from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, 
    QHeaderView, QLabel, QCheckBox
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex
from typing import Optional, List, Dict, Any
from view.language_manager import language_manager

class CommandListWidget(QWidget):
    """
    명령어 목록(Command List)을 관리하는 위젯 클래스입니다.
    명령어의 추가, 삭제, 순서 변경 및 선택 기능을 제공합니다.
    """
    
    # 시그널 정의
    send_row_requested = pyqtSignal(int) # row_index
    command_list_changed = pyqtSignal()  # 데이터 변경 시그널
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        CommandListWidget을 초기화합니다.
        
        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()
        
        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 헤더 / 제어 버튼 (Header / Controls)
        header_layout = QHBoxLayout()
        
        # 전체 선택 체크박스 (Tristate 지원)
        self.select_all_check = QCheckBox(language_manager.get_text("chk_select_all"))
        self.select_all_check.setToolTip(language_manager.get_text("chk_select_all_tooltip"))
        self.select_all_check.setTristate(True)
        self.select_all_check.stateChanged.connect(self.on_select_all_changed)
        
        self.add_btn = QPushButton()
        self.add_btn.setObjectName("btn_add")
        self.add_btn.setToolTip(language_manager.get_text("btn_add_tooltip"))
        self.add_btn.setFixedSize(30, 30)
        
        self.del_btn = QPushButton()
        self.del_btn.setObjectName("btn_del")
        self.del_btn.setToolTip(language_manager.get_text("btn_del_tooltip"))
        self.del_btn.setFixedSize(30, 30)
        
        self.up_btn = QPushButton()
        self.up_btn.setObjectName("btn_up")
        self.up_btn.setToolTip(language_manager.get_text("btn_up_tooltip"))
        self.up_btn.setFixedSize(30, 30)
        
        self.down_btn = QPushButton()
        self.down_btn.setObjectName("btn_down")
        self.down_btn.setToolTip(language_manager.get_text("btn_down_tooltip"))
        self.down_btn.setFixedSize(30, 30)
        
        header_layout.addWidget(self.select_all_check)
        header_layout.addStretch()
        header_layout.addWidget(self.add_btn)
        header_layout.addWidget(self.del_btn)
        header_layout.addWidget(self.up_btn)
        header_layout.addWidget(self.down_btn)
        
        # 시그널 연결
        self.add_btn.clicked.connect(self.add_empty_row)
        self.del_btn.clicked.connect(self.delete_selected_rows)
        self.up_btn.clicked.connect(self.move_row_up)
        self.down_btn.clicked.connect(self.move_row_down)
        
        # 테이블 뷰 (Table View)
        self.cmd_table = QTableView()
        self.cmd_table.setProperty("class", "fixed-font")  # 테이블에 고정폭 폰트 적용
        self.model = QStandardItemModel()
        # 컬럼: 선택, 접두사, 명령어, 접미사, HEX, 지연시간, 전송버튼
        self.update_header_labels()
        self.cmd_table.setModel(self.model)
        self.cmd_table.setToolTip(language_manager.get_text("table_cmd_tooltip"))
        
        # 스크롤바 정책 - 항상 표시
        self.cmd_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.cmd_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 수직 헤더(행 번호) 숨김
        self.cmd_table.verticalHeader().setVisible(False)
        
        # 선택 모드 설정
        self.cmd_table.setSelectionBehavior(QTableView.SelectRows)
        self.cmd_table.setSelectionMode(QTableView.ExtendedSelection)
        
        # 컬럼 너비 조정
        header = self.cmd_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Prefix
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Command
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Suffix
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # HEX
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Delay
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Send Btn
        
        layout.addLayout(header_layout)
        layout.addWidget(self.cmd_table)
        
        self.setLayout(layout)
        
        # 모델 시그널 연결
        self.model.itemChanged.connect(self.on_item_changed)
        self.model.rowsInserted.connect(lambda: self.command_list_changed.emit())
        self.model.rowsRemoved.connect(lambda: self.command_list_changed.emit())
        self.model.rowsMoved.connect(lambda: self.command_list_changed.emit())

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.select_all_check.setText(language_manager.get_text("chk_select_all"))
        self.select_all_check.setToolTip(language_manager.get_text("chk_select_all_tooltip"))
        
        self.add_btn.setToolTip(language_manager.get_text("btn_add_tooltip"))
        self.del_btn.setToolTip(language_manager.get_text("btn_del_tooltip"))
        self.up_btn.setToolTip(language_manager.get_text("btn_up_tooltip"))
        self.down_btn.setToolTip(language_manager.get_text("btn_down_tooltip"))
        
        self.cmd_table.setToolTip(language_manager.get_text("table_cmd_tooltip"))
        self.update_header_labels()
        
        # Send 버튼 텍스트 업데이트 (모든 행)
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 6)
            widget = self.cmd_table.indexWidget(index)
            if widget:
                btn = widget.findChild(QPushButton)
                if btn:
                    btn.setText(language_manager.get_text("send"))

    def update_header_labels(self) -> None:
        """테이블 헤더 라벨을 업데이트합니다."""
        labels = [
            "", 
            language_manager.get_text("prefix"), 
            language_manager.get_text("command"), 
            language_manager.get_text("suffix"), 
            language_manager.get_text("hex_mode"), 
            language_manager.get_text("delay"), 
            language_manager.get_text("send")
        ]
        self.model.setHorizontalHeaderLabels(labels)
        
    def on_item_changed(self, item: QStandardItem) -> None:
        """
        모델 아이템 변경 핸들러입니다.
        Select 컬럼이 변경되면 Select All 상태를 업데이트합니다.
        """
        if item.column() == 0:  # Select column
            self.update_select_all_state()
        
        # 데이터 변경 시그널 발생 (Select 컬럼 제외)
        if item.column() != 0:
            self.command_list_changed.emit()

    def get_command_list(self) -> List[Dict[str, Any]]:
        """
        현재 커맨드 리스트 데이터를 반환합니다.
        
        Returns:
            List[Dict[str, Any]]: 커맨드 데이터 리스트.
        """
        commands = []
        for row in range(self.model.rowCount()):
            cmd_data = {
                "enabled": self.model.item(row, 0).checkState() == Qt.Checked,
                "prefix": self.model.item(row, 1).checkState() == Qt.Checked,
                "command": self.model.item(row, 2).text(),
                "suffix": self.model.item(row, 3).checkState() == Qt.Checked,
                "hex_mode": self.model.item(row, 4).checkState() == Qt.Checked,
                "delay": self.model.item(row, 5).text()
            }
            commands.append(cmd_data)
        return commands

    def set_command_list(self, commands: List[Dict[str, Any]]) -> None:
        """
        커맨드 리스트 데이터를 설정합니다.
        
        Args:
            commands (List[Dict[str, Any]]): 커맨드 데이터 리스트.
        """
        self.model.removeRows(0, self.model.rowCount())
        for cmd in commands:
            self._append_row(
                cmd.get("command", ""),
                cmd.get("prefix", True),
                cmd.get("hex_mode", False),
                cmd.get("suffix", True),
                str(cmd.get("delay", "100")),
                cmd.get("enabled", True)
            )
        self.update_select_all_state()

    def add_dummy_row(self, cmd: str, hex_mode: bool, suffix: bool, delay: str) -> None:
        """테스트용 더미 데이터를 추가합니다."""
        self._append_row(cmd, True, hex_mode, suffix, delay)

    def add_empty_row(self) -> None:
        """빈 행을 추가합니다."""
        self._append_row("", True, False, True, "100")
        
    def _append_row(self, cmd: str, prefix: bool, hex_mode: bool, suffix: bool, delay: str, enabled: bool = True) -> None:
        """
        새로운 행을 모델에 추가합니다.
        
        Args:
            cmd (str): 명령어.
            prefix (bool): 접두사 사용 여부.
            hex_mode (bool): HEX 모드 여부.
            suffix (bool): 접미사 사용 여부.
            delay (str): 지연 시간.
            enabled (bool): 활성화 여부 (Select).
        """
        row_idx = self.model.rowCount()
        
        # 0: Select Checkbox
        item_select = QStandardItem()
        item_select.setCheckable(True)
        item_select.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        item_select.setEditable(False)
        
        # 1: Prefix Checkbox
        item_prefix = QStandardItem()
        item_prefix.setCheckable(True)
        item_prefix.setCheckState(Qt.Checked if prefix else Qt.Unchecked)
        item_prefix.setEditable(False)
        
        # 2: Command
        item_cmd = QStandardItem(cmd)
        
        # 3: Suffix Checkbox
        item_suffix = QStandardItem()
        item_suffix.setCheckable(True)
        item_suffix.setCheckState(Qt.Checked if suffix else Qt.Unchecked)
        item_suffix.setEditable(False)
        
        # 4: HEX
        item_hex = QStandardItem()
        item_hex.setCheckable(True)
        item_hex.setCheckState(Qt.Checked if hex_mode else Qt.Unchecked)
        item_hex.setEditable(False)
        
        # 5: Delay
        item_delay = QStandardItem(delay)
        
        # 6: Send (Placeholder)
        item_send = QStandardItem("")
        item_send.setEditable(False)
        
        self.model.appendRow([item_select, item_prefix, item_cmd, item_suffix, item_hex, item_delay, item_send])
        
        # Send 버튼 설정
        self._set_send_button(row_idx)
        
        # Select All 상태 업데이트
        self.update_select_all_state()

    def _set_send_button(self, row: int) -> None:
        """
        해당 행에 Send 버튼을 설정합니다.
        
        Args:
            row (int): 행 인덱스.
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setAlignment(Qt.AlignCenter)
        
        btn = QPushButton(language_manager.get_text("send"))
        btn.setCursor(Qt.PointingHandCursor)
        # 초기 상태는 비활성화 (포트 연결 전)
        btn.setEnabled(False) 
        
        # 버튼 클릭 시 해당 버튼의 위치를 찾아 시그널 발생
        btn.clicked.connect(lambda: self._on_send_btn_clicked(btn))
        
        layout.addWidget(btn)
        
        index = self.model.index(row, 6)
        self.cmd_table.setIndexWidget(index, widget)

    def _on_send_btn_clicked(self, btn: QPushButton) -> None:
        """
        Send 버튼 클릭 핸들러입니다.
        버튼의 위치를 기반으로 행 인덱스를 찾아 시그널을 발생시킵니다.
        
        Args:
            btn (QPushButton): 클릭된 버튼 객체.
        """
        # 버튼의 부모 위젯(컨테이너)을 통해 위치 확인
        # btn -> layout -> widget -> table_view
        # viewport mapFromGlobal을 사용하는 것이 가장 정확함
        pos = self.cmd_table.viewport().mapFromGlobal(btn.mapToGlobal(btn.rect().center()))
        index = self.cmd_table.indexAt(pos)
        if index.isValid():
            self.send_row_requested.emit(index.row())

    def set_send_enabled(self, enabled: bool) -> None:
        """
        모든 Send 버튼의 활성화 상태를 변경합니다.
        
        Args:
            enabled (bool): 활성화 여부.
        """
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 6)
            widget = self.cmd_table.indexWidget(index)
            if widget:
                # widget은 컨테이너이므로 그 안의 버튼을 찾아야 함
                btn = widget.findChild(QPushButton)
                if btn:
                    btn.setEnabled(enabled)

    def delete_selected_rows(self) -> None:
        """선택된 행들을 삭제합니다."""
        rows = sorted(set(index.row() for index in self.cmd_table.selectionModel().selectedRows()), reverse=True)
        for row in rows:
            self.model.removeRow(row)
        self.update_select_all_state()
            
    def move_row_up(self) -> None:
        """선택된 행들을 위로 이동합니다."""
        rows = sorted(set(index.row() for index in self.cmd_table.selectionModel().selectedRows()))
        if not rows or rows[0] == 0:
            return
            
        # 위에서부터 순서대로 이동해야 인덱스가 꼬이지 않음
        for row in rows:
            self._move_row(row, row - 1)
            
        # 선택 상태 복구
        for row in rows:
            self.cmd_table.selectRow(row - 1)

    def move_row_down(self) -> None:
        """선택된 행들을 아래로 이동합니다."""
        rows = sorted(set(index.row() for index in self.cmd_table.selectionModel().selectedRows()), reverse=True)
        if not rows or rows[0] == self.model.rowCount() - 1:
            return
            
        # 아래에서부터 이동
        for row in rows:
            self._move_row(row, row + 1)
            
        # 선택 상태 복구
        for row in rows:
            self.cmd_table.selectRow(row + 1)
            
    def _move_row(self, source_row: int, dest_row: int) -> None:
        """
        행을 이동하고 위젯(버튼)을 복구합니다.
        
        Args:
            source_row (int): 원본 행 인덱스.
            dest_row (int): 대상 행 인덱스.
        """
        # 1. 데이터 가져오기
        items = self.model.takeRow(source_row)
        
        # 2. 새 위치에 삽입
        self.model.insertRow(dest_row, items)
        
        # 3. 위젯(버튼) 복구
        # 이동 시 기존 위젯은 삭제되므로 새로 생성해야 함
        self._set_send_button(dest_row)
        
        # 참고: 현재 활성화 상태에 맞춰 버튼 상태 업데이트가 필요할 수 있음
        # 현재는 기본값(False)로 생성되므로, 외부에서 상태 관리가 필요함.

    def get_selected_indices(self) -> List[int]:
        """
        체크박스가 선택된 항목의 인덱스 리스트를 반환합니다.
        
        Returns:
            List[int]: 선택된 행 인덱스 리스트.
        """
        indices: List[int] = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            if item.checkState() == Qt.Checked:
                indices.append(row)
        return indices
        
    def on_select_all_changed(self, state: int) -> None:
        """
        Select All 체크박스 상태 변경 핸들러입니다.
        
        Args:
            state (int): 체크박스 상태 (Qt.Checked 등).
        """
        if state == Qt.PartiallyChecked:
            # PartiallyChecked 상태에서 클릭하면 모두 선택으로 변경
            self.select_all_check.setCheckState(Qt.Checked)
        elif state == Qt.Checked:
            self.set_all_checked(True)
        else:  # Qt.Unchecked
            self.set_all_checked(False)

    def save_state(self) -> list:
        """
        현재 명령어 목록을 리스트로 반환합니다.
        
        Returns:
            list: 명령어 목록 데이터.
        """
        commands = self.get_command_list()
        return commands
        
    def load_state(self, state: list) -> None:
        """
        저장된 명령어 목록을 위젯에 적용합니다.
        
        Args:
            state (list): 명령어 목록 데이터.
        """
        if not state:
            return
            
        self.set_command_list(state)
        

    
    def set_all_checked(self, checked: bool) -> None:
        """
        모든 항목의 체크 상태를 변경합니다.
        
        Args:
            checked (bool): 체크 여부.
        """
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.model.rowCount()):
            item = self.model.item(row, 0)
            item.setCheckState(state)
        self.update_select_all_state()
    
    def update_select_all_state(self) -> None:
        """Select All 체크박스의 상태(전체/부분/없음)를 업데이트합니다."""
        total = self.model.rowCount()
        if total == 0:
            self.select_all_check.setCheckState(Qt.Unchecked)
            return
            
        checked_count = 0
        for row in range(total):
            item = self.model.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                checked_count += 1
        
        # 재귀 호출 방지를 위해 시그널 차단
        self.select_all_check.blockSignals(True)
        if checked_count == 0:
            self.select_all_check.setCheckState(Qt.Unchecked)
        elif checked_count == total:
            self.select_all_check.setCheckState(Qt.Checked)
        else:
            self.select_all_check.setCheckState(Qt.PartiallyChecked)
        self.select_all_check.blockSignals(False)
