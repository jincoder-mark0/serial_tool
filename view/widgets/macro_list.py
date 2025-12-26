"""
매크로 리스트 위젯 모듈

전송할 명령어(Macro) 목록을 테이블 형태로 관리하고 편집하는 위젯입니다.
사용자는 매크로를 추가, 수정, 삭제, 순서 변경할 수 있으며,
각 행의 전송 버튼을 통해 개별 명령을 즉시 실행할 수 있습니다.

## WHY
* 다수의 명령어를 순차적으로 관리하고 편집할 수 있는 직관적인 UI 필요
* 각 명령어별 옵션(Hex, Delay, Prefix/Suffix 등)을 개별적으로 설정해야 함
* 매크로 데이터의 저장/복원(Persistence) 및 실행 엔진(Runner)과의 연동 데이터 제공

## WHAT
* QTableView 기반의 매크로 목록 표시 및 편집
* 행 추가/삭제/이동 및 컨텍스트 메뉴 지원
* 체크박스를 통한 활성화/비활성화 및 전체 선택 기능
* DTO(MacroEntry) 기반의 데이터 추출 및 삽입

## HOW
* QStandardItemModel을 사용하여 데이터 관리
* setIndexWidget을 사용하여 테이블 셀 내에 버튼 배치
* 시그널(send_row_requested)을 통해 Presenter에 DTO 전달
"""
from typing import Optional, List, Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton,
    QHeaderView, QCheckBox, QMenu, QAction
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, pyqtSignal, QPoint

from view.managers.language_manager import language_manager
from common.dtos import MacroEntry


class MacroListWidget(QWidget):
    """
    매크로 목록을 관리하는 위젯 클래스입니다.

    QTableView와 QStandardItemModel을 사용하여 매크로 데이터를 관리하며,
    Presenter와 DTO를 통해 데이터를 교환합니다.
    """

    # 시그널 정의
    # row_index와 MacroEntry DTO를 함께 전달하여 Presenter의 View 재조회를 방지 (Passive View)
    send_row_requested = pyqtSignal(int, object)  # (row_index, MacroEntry)
    macro_list_changed = pyqtSignal()  # 데이터 변경 알림

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroListWidget을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # UI 컴포넌트 초기화
        self.macro_table_model: Optional[QStandardItemModel] = None
        self.macro_table: Optional[QTableView] = None
        self.down_row_btn: Optional[QPushButton] = None
        self.up_row_btn: Optional[QPushButton] = None
        self.remove_row_btn: Optional[QPushButton] = None
        self.add_row_btn: Optional[QPushButton] = None
        self.select_all_chk: Optional[QCheckBox] = None

        self._send_enabled = False  # 전송 버튼 활성화 상태

        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            - 헤더 레이아웃(제어 버튼) 구성
            - 테이블 뷰 및 모델 설정
            - 컨텍스트 메뉴 및 시그널 연결
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # ---------------------------------------------------------
        # 1. 헤더 / 제어 버튼 (Header / Controls)
        # ---------------------------------------------------------
        header_layout = QHBoxLayout()

        # 전체 선택 체크박스 (Tristate 지원)
        self.select_all_chk = QCheckBox(language_manager.get_text("macro_list_chk_select_all"))
        self.select_all_chk.setToolTip(language_manager.get_text("macro_list_chk_select_all_tooltip"))
        self.select_all_chk.setTristate(True)
        self.select_all_chk.stateChanged.connect(self.on_select_all_changed)

        # 제어 버튼 생성
        self.add_row_btn = QPushButton()
        self.add_row_btn.setObjectName("add_row_btn")
        self.add_row_btn.setToolTip(language_manager.get_text("macro_list_btn_add_row_tooltip"))
        self.add_row_btn.setFixedSize(30, 30)

        self.remove_row_btn = QPushButton()
        self.remove_row_btn.setObjectName("remove_row_btn")
        self.remove_row_btn.setToolTip(language_manager.get_text("macro_list_btn_remove_row_tooltip"))
        self.remove_row_btn.setFixedSize(30, 30)

        self.up_row_btn = QPushButton()
        self.up_row_btn.setObjectName("up_row_btn")
        self.up_row_btn.setToolTip(language_manager.get_text("macro_list_btn_up_row_tooltip"))
        self.up_row_btn.setFixedSize(30, 30)

        self.down_row_btn = QPushButton()
        self.down_row_btn.setObjectName("down_row_btn")
        self.down_row_btn.setToolTip(language_manager.get_text("macro_list_btn_down_row_tooltip"))
        self.down_row_btn.setFixedSize(30, 30)

        header_layout.addWidget(self.select_all_chk)
        header_layout.addStretch()
        header_layout.addWidget(self.add_row_btn)
        header_layout.addWidget(self.remove_row_btn)
        header_layout.addWidget(self.up_row_btn)
        header_layout.addWidget(self.down_row_btn)

        # 버튼 시그널 연결
        self.add_row_btn.clicked.connect(self.add_macro_row)
        self.remove_row_btn.clicked.connect(self.remove_selected_rows)
        self.up_row_btn.clicked.connect(self.move_up_selected_row)
        self.down_row_btn.clicked.connect(self.move_down_selected_row)

        # ---------------------------------------------------------
        # 2. 테이블 뷰 (Table View)
        # ---------------------------------------------------------
        self.macro_table = QTableView()
        self.macro_table.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        self.macro_table_model = QStandardItemModel()

        # 컬럼 헤더 설정
        self.update_header_labels()
        self.macro_table.setModel(self.macro_table_model)
        self.macro_table.setToolTip(language_manager.get_text("macro_list_table_command"))

        # 컨텍스트 메뉴 설정
        self.macro_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.macro_table.customContextMenuRequested.connect(self.show_context_menu)

        # 스크롤바 정책 - 항상 표시
        self.macro_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.macro_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 수직 헤더(행 번호) 숨김
        self.macro_table.verticalHeader().setVisible(False)

        # 선택 모드 설정
        self.macro_table.setSelectionBehavior(QTableView.SelectRows)
        self.macro_table.setSelectionMode(QTableView.ExtendedSelection)

        # 컬럼 너비 조정
        header = self.macro_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Prefix
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # Command
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Suffix
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # HEX
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Delay
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Send Btn

        layout.addLayout(header_layout)
        layout.addWidget(self.macro_table)

        self.setLayout(layout)

        # 모델 시그널 연결 (데이터 변경 감지)
        self.macro_table_model.itemChanged.connect(self.on_item_changed)
        self.macro_table_model.rowsInserted.connect(lambda: self.macro_list_changed.emit())
        self.macro_table_model.rowsRemoved.connect(lambda: self.macro_list_changed.emit())
        self.macro_table_model.rowsMoved.connect(lambda: self.macro_list_changed.emit())

    def show_context_menu(self, pos: QPoint) -> None:
        """
        테이블 뷰에서 우클릭 시 컨텍스트 메뉴를 표시합니다.

        Args:
            pos (QPoint): 마우스 클릭 좌표.
        """
        menu = QMenu(self)

        add_action = QAction(language_manager.get_text("macro_list_btn_add_row_tooltip"), self)
        add_action.triggered.connect(self.add_macro_row)
        menu.addAction(add_action)

        del_action = QAction(language_manager.get_text("macro_list_btn_remove_row_tooltip"), self)
        del_action.triggered.connect(self.remove_selected_rows)
        menu.addAction(del_action)

        menu.addSeparator()

        up_action = QAction(language_manager.get_text("macro_list_btn_up_row_tooltip"), self)
        up_action.triggered.connect(self.move_up_selected_row)
        menu.addAction(up_action)

        down_action = QAction(language_manager.get_text("macro_list_btn_down_row_tooltip"), self)
        down_action.triggered.connect(self.move_down_selected_row)
        menu.addAction(down_action)

        menu.exec_(self.macro_table.mapToGlobal(pos))

    def retranslate_ui(self) -> None:
        """
        언어 변경 시 UI 텍스트를 현재 언어 설정에 맞게 업데이트합니다.
        """
        self.select_all_chk.setText(language_manager.get_text("macro_list_chk_select_all"))
        self.select_all_chk.setToolTip(language_manager.get_text("macro_list_chk_select_all_tooltip"))

        self.add_row_btn.setToolTip(language_manager.get_text("macro_list_btn_add_row_tooltip"))
        self.remove_row_btn.setToolTip(language_manager.get_text("macro_list_btn_remove_row_tooltip"))
        self.up_row_btn.setToolTip(language_manager.get_text("macro_list_btn_up_row_tooltip"))
        self.down_row_btn.setToolTip(language_manager.get_text("macro_list_btn_down_row_tooltip"))

        self.macro_table.setToolTip(language_manager.get_text("macro_list_table_command"))
        self.update_header_labels()

        # Send 버튼 텍스트 업데이트 (모든 행 순회)
        for row in range(self.macro_table_model.rowCount()):
            index = self.macro_table_model.index(row, 6)
            widget = self.macro_table.indexWidget(index)
            if widget:
                send_btn = widget.findChild(QPushButton)
                if send_btn:
                    send_btn.setText(language_manager.get_text("macro_list_send_btn"))

    def update_header_labels(self) -> None:
        """테이블 헤더 라벨을 업데이트합니다."""
        labels = [
            "",  # Checkbox
            language_manager.get_text("macro_list_col_prefix"),
            language_manager.get_text("macro_list_col_command"),
            language_manager.get_text("macro_list_col_suffix"),
            language_manager.get_text("macro_list_col_hex"),
            language_manager.get_text("macro_list_col_delay"),
            language_manager.get_text("macro_list_col_send")
        ]
        self.macro_table_model.setHorizontalHeaderLabels(labels)

    def on_item_changed(self, item: QStandardItem) -> None:
        """
        모델 아이템 변경 핸들러입니다.
        Select 컬럼이 변경되면 Select All 상태를 업데이트합니다.

        Args:
            item (QStandardItem): 변경된 아이템.
        """
        if item.column() == 0:  # Select column
            self.update_select_all_state()

        # 데이터 변경 시그널 발생 (Select 컬럼 제외)
        if item.column() != 0:
            self.macro_list_changed.emit()

    def get_macro_entries(self) -> List[MacroEntry]:
        """
        모든 행을 MacroEntry DTO 리스트로 변환하여 반환합니다.
        (Logic Layer 또는 Runner에서 사용)

        Returns:
            List[MacroEntry]: MacroEntry 객체 리스트.
        """
        entries = []
        for row in range(self.macro_table_model.rowCount()):
            entry = self.get_entry_at(row)
            if entry:
                entries.append(entry)
        return entries

    def get_entry_at(self, row: int) -> Optional[MacroEntry]:
        """
        특정 행의 데이터를 MacroEntry DTO로 반환합니다.

        Args:
            row (int): 행 인덱스.

        Returns:
            Optional[MacroEntry]: 생성된 DTO, 실패 시 None.
        """
        if row < 0 or row >= self.macro_table_model.rowCount():
            return None

        # 데이터 안전하게 추출
        try:
            enabled = self.macro_table_model.item(row, 0).checkState() == Qt.Checked
            prefix_enabled = self.macro_table_model.item(row, 1).checkState() == Qt.Checked
            command = self.macro_table_model.item(row, 2).text()
            suffix_enabled = self.macro_table_model.item(row, 3).checkState() == Qt.Checked
            hex_mode = self.macro_table_model.item(row, 4).checkState() == Qt.Checked
            delay_text = self.macro_table_model.item(row, 5).text()

            # 지연 시간 안전 변환
            delay_ms = 100
            if delay_text.isdigit():
                delay_ms = int(delay_text)

            return MacroEntry(
                enabled=enabled,
                command=command,
                hex_mode=hex_mode,
                prefix_enabled=prefix_enabled,
                suffix_enabled=suffix_enabled,
                delay_ms=delay_ms
            )
        except Exception:
            return None

    def export_macros(self) -> List[Dict[str, Any]]:
        """
        현재 커맨드 리스트 데이터를 추출하여 Dictionary 리스트로 반환합니다.
        (Persistence / SettingsManager 용)

        Returns:
            List[Dict[str, Any]]: 커맨드 데이터 리스트.
        """
        commands = []
        for row in range(self.macro_table_model.rowCount()):
            # DTO를 생성한 후 to_dict() 호출하여 일관성 유지
            entry = self.get_entry_at(row)
            if entry:
                commands.append(entry.to_dict())
        return commands

    def import_macros(self, commands: List[Dict[str, Any]]) -> None:
        """
        커맨드 리스트 데이터를 UI에 주입합니다.
        기존 데이터를 모두 지우고 새로 생성합니다.

        Args:
            commands (List[Dict[str, Any]]): 커맨드 데이터 리스트.
        """
        self.macro_table_model.removeRows(0, self.macro_table_model.rowCount())
        for i, command_dict in enumerate(commands):
            # DTO를 통해 안전하게 변환 (from_dict 내부에 _safe_cast 있음)
            entry = MacroEntry.from_dict(command_dict)
            self._insert_row(
                i,
                entry.command,
                entry.prefix_enabled,
                entry.hex_mode,
                entry.suffix_enabled,
                str(entry.delay_ms),
                entry.enabled
            )
        self.update_select_all_state()

    def add_dummy_row(self, command: str, hex_mode: bool, suffix: bool, delay: str) -> None:
        """
        테스트용 더미 데이터를 추가합니다.

        Args:
            command (str): 명령어.
            hex_mode (bool): Hex 모드 여부.
            suffix (bool): 접미사 사용 여부.
            delay (str): 지연 시간.
        """
        self._insert_row(self.macro_table_model.rowCount(), command, True, hex_mode, suffix, delay)

    def add_macro_row(self) -> None:
        """
        빈 행을 추가합니다.
        선택된 행이 있으면 그 아래에 추가하고 옵션을 복사합니다.
        """
        # 기본값
        command = ""
        prefix = True
        hex_mode = False
        suffix = True
        delay = "100"
        enabled = True

        # 선택된 행 확인
        selected_rows = self.macro_table.selectionModel().selectedRows()
        copy_source_row = -1
        insert_row_index = -1

        if selected_rows:
            # 선택된 행 중 마지막 행을 기준으로 함
            last_selected_row = selected_rows[-1].row()
            copy_source_row = last_selected_row
            insert_row_index = last_selected_row + 1
        else:
            # 선택된 행이 없으면 맨 뒤에 추가
            if self.macro_table_model.rowCount() > 0:
                copy_source_row = self.macro_table_model.rowCount() - 1
            insert_row_index = self.macro_table_model.rowCount()

        if copy_source_row >= 0:
            # 옵션 복사
            enabled = self.macro_table_model.item(copy_source_row, 0).checkState() == Qt.Checked
            prefix = self.macro_table_model.item(copy_source_row, 1).checkState() == Qt.Checked
            command = ""  # Command는 복사하지 않음 (빈 칸)
            suffix = self.macro_table_model.item(copy_source_row, 3).checkState() == Qt.Checked
            hex_mode = self.macro_table_model.item(copy_source_row, 4).checkState() == Qt.Checked
            delay = self.macro_table_model.item(copy_source_row, 5).text()

        self._insert_row(insert_row_index, command, prefix, hex_mode, suffix, delay, enabled)

        # 추가된 행 선택
        self.macro_table.selectRow(insert_row_index)

    def _insert_row(self, row_index: int, command: str, prefix: bool, hex_mode: bool, suffix: bool, delay: str, enabled: bool = True) -> None:
        """
        새로운 행을 모델의 특정 위치에 삽입합니다.

        Args:
            row_index (int): 삽입할 행 인덱스.
            command (str): Command.
            prefix (bool): 접두사 사용 여부.
            hex_mode (bool): HEX 모드 여부.
            suffix (bool): 접미사 사용 여부.
            delay (str): 지연 시간.
            enabled (bool): 활성화 여부 (Select).
        """
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
        item_command = QStandardItem(command)

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

        self.macro_table_model.insertRow(row_index, [item_select, item_prefix, item_command, item_suffix, item_hex, item_delay, item_send])

        # Send 버튼 설정
        self._set_send_button(row_index)

        # Select All 상태 업데이트
        self.update_select_all_state()

    def _refresh_send_buttons(self) -> None:
        """
        모든 행의 Send 버튼을 새로 설정(갱신)합니다.
        행 삭제나 이동 시 인덱스가 변경되므로 호출이 필수입니다.
        """
        for row in range(self.macro_table_model.rowCount()):
            self._set_send_button(row)

    def _set_send_button(self, row: int) -> None:
        """
        해당 행에 Send 버튼을 설정합니다.
        Widget을 생성하여 테이블 셀에 배치합니다.

        Args:
            row (int): 행 인덱스.
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setAlignment(Qt.AlignCenter)

        btn = QPushButton(language_manager.get_text("macro_list_btn_send"))
        btn.setCursor(Qt.PointingHandCursor)
        # 현재 활성화 상태에 따라 설정
        btn.setEnabled(self._send_enabled)

        # 버튼 클릭 시 헬퍼 메서드를 통해 DTO 생성 및 시그널 발생
        btn.clicked.connect(lambda _, r=row: self._on_send_clicked(r))

        layout.addWidget(btn)

        index = self.macro_table_model.index(row, 6)
        self.macro_table.setIndexWidget(index, widget)

    def _on_send_clicked(self, row: int) -> None:
        """
        Send 버튼 클릭 헬퍼 메서드입니다.
        View에서 DTO를 생성하여 Presenter로 전달합니다 (Passive View).

        Args:
            row (int): 클릭된 행 인덱스.
        """
        entry = self.get_entry_at(row)
        if entry:
            self.send_row_requested.emit(row, entry)

    def set_send_enabled(self, enabled: bool) -> None:
        """
        모든 Send 버튼의 활성화 상태를 변경합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        self._send_enabled = enabled
        for row in range(self.macro_table_model.rowCount()):
            index = self.macro_table_model.index(row, 6)
            widget = self.macro_table.indexWidget(index)
            if widget:
                # widget은 컨테이너이므로 그 안의 버튼을 찾아야 함
                btn = widget.findChild(QPushButton)
                if btn:
                    btn.setEnabled(enabled)

    def remove_selected_rows(self) -> None:
        """선택된 행들을 삭제합니다."""
        rows = sorted(set(index.row() for index in self.macro_table.selectionModel().selectedRows()), reverse=True)
        for row in rows:
            self.macro_table_model.removeRow(row)
        self._refresh_send_buttons()
        self.update_select_all_state()

    def move_up_selected_row(self) -> None:
        """선택된 행들을 위로 이동합니다."""
        rows = sorted(set(index.row() for index in self.macro_table.selectionModel().selectedRows()))
        if not rows or rows[0] == 0:
            return

        # 위에서부터 순서대로 이동해야 인덱스가 꼬이지 않음
        for row in rows:
            self._move_row(row, row - 1)

        # 버튼 갱신
        self._refresh_send_buttons()

        # 선택 상태 복구
        self._restore_selection([row - 1 for row in rows])

    def move_down_selected_row(self) -> None:
        """선택된 행들을 아래로 이동합니다."""
        rows = sorted(set(index.row() for index in self.macro_table.selectionModel().selectedRows()), reverse=True)
        if not rows or rows[0] == self.macro_table_model.rowCount() - 1:
            return

        # 아래에서부터 이동
        for row in rows:
            self._move_row(row, row + 1)

        # 버튼 갱신
        self._refresh_send_buttons()

        # 선택 상태 복구
        self._restore_selection([row + 1 for row in rows])

    def _restore_selection(self, rows: List[int]) -> None:
        """
        주어진 행 인덱스 리스트를 선택 상태로 복원합니다.

        Args:
            rows (List[int]): 선택할 행 인덱스 리스트.
        """
        self.macro_table.clearSelection()
        for row in rows:
            self.macro_table.selectRow(row)

    def _move_row(self, source_row: int, dest_row: int) -> None:
        """
        행을 이동합니다. (데이터만 이동, 버튼은 호출자가 일괄 갱신)

        Args:
            source_row (int): 원본 행 인덱스.
            dest_row (int): 대상 행 인덱스.
        """
        # 1. 데이터 가져오기
        items = self.macro_table_model.takeRow(source_row)

        # 2. 새 위치에 삽입
        self.macro_table_model.insertRow(dest_row, items)

    def get_selected_indices(self) -> List[int]:
        """
        체크박스가 선택된 항목의 인덱스 리스트를 반환합니다.

        Returns:
            List[int]: 선택된 행 인덱스 리스트.
        """
        indices: List[int] = []
        for row in range(self.macro_table_model.rowCount()):
            item = self.macro_table_model.item(row, 0)
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
            self.select_all_chk.setCheckState(Qt.Checked)
        elif state == Qt.Checked:
            self.set_all_checked(True)
        else:  # Qt.Unchecked
            self.set_all_checked(False)

    def get_state(self) -> list:
        """
        현재 Command 목록을 리스트로 반환합니다 (Persistence용).

        Returns:
            list: Command 목록 데이터 (dict list).
        """
        commands = self.export_macros()
        return commands

    def apply_state(self, state: list) -> None:
        """
        저장된 Command 목록을 위젯에 적용합니다.

        Args:
            state (list): Command 목록 데이터 (dict list).
        """
        if not state:
            return

        self.import_macros(state)

    def set_all_checked(self, checked: bool) -> None:
        """
        모든 항목의 체크 상태를 변경합니다.

        Args:
            checked (bool): 체크 여부.
        """
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.macro_table_model.rowCount()):
            item = self.macro_table_model.item(row, 0)
            item.setCheckState(state)
        self.update_select_all_state()

    def update_select_all_state(self) -> None:
        """Select All 체크박스의 상태(전체/부분/없음)를 업데이트합니다."""
        total = self.macro_table_model.rowCount()
        if total == 0:
            self.select_all_chk.setCheckState(Qt.Unchecked)
            return

        checked_count = 0
        for row in range(total):
            item = self.macro_table_model.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                checked_count += 1

        # 재귀 호출 방지를 위해 시그널 차단
        self.select_all_chk.blockSignals(True)
        if checked_count == 0:
            self.select_all_chk.setCheckState(Qt.Unchecked)
        elif checked_count == total:
            self.select_all_chk.setCheckState(Qt.Checked)
        else:
            self.select_all_chk.setCheckState(Qt.PartiallyChecked)
        self.select_all_chk.blockSignals(False)