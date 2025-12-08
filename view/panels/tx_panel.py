from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QCheckBox, QLabel, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt

class TxPanel(QWidget):
    """
    데이터 전송을 담당하는 패널 클래스입니다.
    텍스트 입력, HEX 모드, CR/LF 설정 및 전송 내역 기능을 제공합니다.
    """
    text_data_send_requested = pyqtSignal(str, bool, bool) # text, hex_mode, with_enter

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        TxPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 입력 영역 (Input Area)
        self.tx_data_edit = QTextEdit()
        self.tx_data_edit.setMaximumHeight(60)
        self.tx_data_edit.setPlaceholderText("Enter command here...")
        self.tx_data_edit.setToolTip("전송할 데이터를 입력하세요 (Ctrl+Enter로 전송)")

        # 제어 버튼 영역 (Controls)
        controls_layout = QHBoxLayout()

        self.tx_hex_chk = QCheckBox("HEX")
        self.tx_hex_chk.setToolTip("HEX 문자열로 전송합니다 (예: '41 42')")
        self.tx_cr_chk = QCheckBox("CR")
        self.tx_cr_chk.setChecked(True)
        self.tx_cr_chk.setToolTip("Carriage Return (\\r)을 추가합니다")
        self.tx_lf_chk = QCheckBox("LF")
        self.tx_lf_chk.setChecked(True)
        self.tx_lf_chk.setToolTip("Line Feed (\\n)을 추가합니다")

        self.send_text_data_btn = QPushButton("Send")
        self.send_text_data_btn.clicked.connect(self.on_send_text_data_clicked)
        self.send_text_data_btn.setToolTip("데이터를 전송합니다 (Enter)")

        controls_layout.addWidget(self.tx_hex_chk)
        controls_layout.addWidget(self.tx_cr_chk)
        controls_layout.addWidget(self.tx_lf_chk)
        controls_layout.addStretch()
        controls_layout.addWidget(self.send_text_data_btn)

        # 전송 내역 (History)
        self.tx_history_combo = QComboBox()
        self.tx_history_combo.setPlaceholderText("History...")
        self.tx_history_combo.setToolTip("전송 내역")
        self.tx_history_combo.currentIndexChanged.connect(self.on_tx_history_selected)

        layout.addWidget(QLabel("TX Input"))
        layout.addWidget(QLabel("TX Input"))
        layout.addWidget(self.tx_data_edit)
        layout.addLayout(controls_layout)
        layout.addWidget(self.tx_history_combo)

        self.setLayout(layout)

    def on_send_text_data_clicked(self) -> None:
        """전송 버튼 클릭 핸들러입니다."""
        text = self.tx_data_edit.toPlainText()
        if not text:
            return

        hex_mode = self.tx_hex_chk.isChecked()

        # CR/LF 처리
        # Presenter로 플래그를 넘기는 것이 더 깔끔하지만, 여기서는 직접 처리 후 전송
        with_enter = False

        suffix = ""
        if self.tx_cr_chk.isChecked(): suffix += "\r"
        if self.tx_lf_chk.isChecked(): suffix += "\n"

        # HEX 모드가 아닐 경우에만 접미사 추가
        if not hex_mode:
            text += suffix

        self.text_data_send_requested.emit(text, hex_mode, False) # with_enter는 수동 처리했으므로 False

        # 내역에 추가
        if self.tx_history_combo.findText(text.strip()) == -1:
            self.tx_history_combo.addItem(text.strip())

    def on_tx_history_selected(self, index: int) -> None:
        """
        전송 내역 선택 핸들러입니다.

        Args:
            index (int): 선택된 내역의 인덱스.
        """
        if index >= 0:
            self.tx_data_edit.setPlainText(self.tx_history_combo.itemText(index))
