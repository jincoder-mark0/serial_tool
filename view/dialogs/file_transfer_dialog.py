from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QGroupBox
)
from PyQt5.QtCore import pyqtSignal
from typing import Optional
from view.managers.lang_manager import lang_manager
from view.widgets.file_progress import FileProgressWidget

class FileTransferDialog(QDialog):
    """
    파일 전송을 위한 다이얼로그입니다.
    파일 선택 및 전송 진행률을 표시합니다.
    """
    
    # 시그널 정의
    file_selected = pyqtSignal(str)
    send_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang_manager.get_text("manual_ctrl_grp_file"))
        self.resize(400, 200)
        
        self.file_path_lbl = None
        self.select_file_btn = None
        self.send_btn = None
        self.progress_widget = None
        
        self.init_ui()
        
        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. 파일 선택 영역
        file_grp = QGroupBox(lang_manager.get_text("manual_ctrl_grp_file"))
        file_layout = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        self.file_path_lbl = QLabel(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))
        self.file_path_lbl.setStyleSheet("color: gray; border: 1px solid #555; padding: 5px; border-radius: 2px;")
        self.file_path_lbl.setWordWrap(True)
        
        self.select_file_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.select_file_btn.clicked.connect(self.on_select_file_clicked)
        
        path_layout.addWidget(self.file_path_lbl, 1)
        path_layout.addWidget(self.select_file_btn)
        
        self.send_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_send_file"))
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.send_btn.setEnabled(False) # 파일 선택 전까지 비활성화
        
        file_layout.addLayout(path_layout)
        file_layout.addWidget(self.send_btn)
        file_grp.setLayout(file_layout)
        
        # 2. 진행률 표시 영역
        self.progress_widget = FileProgressWidget()
        self.progress_widget.cancel_requested.connect(self.on_cancel_clicked)
        
        layout.addWidget(file_grp)
        layout.addWidget(self.progress_widget)
        layout.addStretch()
        
        self.setLayout(layout)
        
    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.setWindowTitle(lang_manager.get_text("manual_ctrl_grp_file"))
        self.select_file_btn.setText(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.send_btn.setText(lang_manager.get_text("manual_ctrl_btn_send_file"))
        
        if lang_manager.text_matches_key(self.file_path_lbl.text(), "manual_ctrl_lbl_file_path_no_file"):
            self.file_path_lbl.setText(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))
            
    def on_select_file_clicked(self) -> None:
        """파일 선택 버튼 클릭 핸들러"""
        path, _ = QFileDialog.getOpenFileName(self, lang_manager.get_text("manual_ctrl_dialog_select_file"))
        if path:
            self.file_path_lbl.setText(path)
            self.send_btn.setEnabled(True)
            self.file_selected.emit(path)
            # 진행률 위젯 초기화
            self.progress_widget.reset()
            
    def on_send_clicked(self) -> None:
        """전송 버튼 클릭 핸들러"""
        path = self.file_path_lbl.text()
        if path and path != lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"):
            self.send_requested.emit(path)
            self.select_file_btn.setEnabled(False)
            self.send_btn.setEnabled(False)
            
    def on_cancel_clicked(self) -> None:
        """취소 요청 핸들러"""
        self.cancel_requested.emit()
        self.select_file_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        
    def update_progress(self, sent: int, total: int, speed: float, eta: float) -> None:
        """진행률 업데이트"""
        self.progress_widget.update_progress(sent, total, speed, eta)
        
    def set_complete(self, success: bool, message: str = "") -> None:
        """완료 상태 설정"""
        self.progress_widget.set_complete(success, message)
        self.select_file_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        """다이얼로그 닫기 시 전송 중이면 취소 요청"""
        # 전송 중인지 확인하는 로직이 필요할 수 있음 (MainPresenter에서 관리하므로 여기선 시그널만)
        self.cancel_requested.emit()
        event.accept()
