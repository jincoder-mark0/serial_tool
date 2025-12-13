"""
파일 전송 다이얼로그 모듈

사용자로부터 파일을 선택받고 전송 진행 상황을 표시합니다.

## WHY
* 파일 전송 과정을 시각화하여 사용자 경험 향상
* 전송 시작 및 취소에 대한 사용자 제어 제공
* MVP 패턴의 View 역할 수행

## WHAT
* 파일 선택 및 경로 표시
* 진행률(ProgressBar), 속도, ETA 표시
* Presenter로 사용자 이벤트(전송, 취소) 전달
* Presenter로부터 받은 데이터로 UI 갱신

## HOW
* QDialog 상속
* PyQt Signal을 통한 이벤트 버블링
* 수동적인 뷰(Passive View)로서 로직 없이 UI 업데이트만 수행
"""
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QGroupBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.managers.lang_manager import lang_manager
from view.widgets.file_progress import FileProgressWidget

class FileTransferDialog(QDialog):
    """
    파일 전송 다이얼로그 클래스 (View)

    Presenter에 의해 제어되며, 사용자 입력을 시그널로 전달하고
    Presenter의 요청에 따라 UI를 갱신합니다.
    """

    # User Actions (View -> Presenter)
    file_selected = pyqtSignal(str)
    send_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        FileTransferDialog 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
        super().__init__(parent)
        self.setWindowTitle(lang_manager.get_text("manual_ctrl_grp_file"))
        self.setFixedSize(450, 250)
        self.setModal(True)

        # UI Components
        self.file_path_lbl = None
        self.select_file_btn = None
        self.send_btn = None
        self.close_btn = None
        self.progress_widget = None

        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        lang_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # ---------------------------------------------------------
        # 1. 파일 선택 영역
        # ---------------------------------------------------------
        file_grp = QGroupBox(lang_manager.get_text("manual_ctrl_grp_file"))
        file_layout = QVBoxLayout()

        path_layout = QHBoxLayout()
        self.file_path_lbl = QLabel(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))
        self.file_path_lbl.setStyleSheet(
            "color: gray; border: 1px solid #555; padding: 5px; border-radius: 4px; background-color: #2b2b2b;"
        )
        self.file_path_lbl.setWordWrap(True)

        self.select_file_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.select_file_btn.setFixedWidth(100)
        self.select_file_btn.clicked.connect(self.on_select_file_clicked)

        path_layout.addWidget(self.file_path_lbl, 1)
        path_layout.addWidget(self.select_file_btn)

        self.send_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_send_file"))
        self.send_btn.setProperty("class", "accent")  # 강조 스타일
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.send_btn.setEnabled(False) # 파일 선택 전까지 비활성화

        file_layout.addLayout(path_layout)
        file_layout.addWidget(self.send_btn)
        file_grp.setLayout(file_layout)

        # ---------------------------------------------------------
        # 2. 진행률 표시 영역 (FileProgressWidget 재사용)
        # ---------------------------------------------------------
        self.progress_widget = FileProgressWidget()
        # 위젯 내부의 취소 버튼 시그널을 다이얼로그 시그널로 연결
        self.progress_widget.cancel_requested.connect(self.cancel_requested.emit)

        # ---------------------------------------------------------
        # 3. 하단 버튼
        # ---------------------------------------------------------
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.close_btn = QPushButton(lang_manager.get_text("manual_ctrl_btn_close"))
        self.close_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.close_btn)

        layout.addWidget(file_grp)
        layout.addWidget(self.progress_widget)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """다국어 텍스트 업데이트"""
        self.setWindowTitle(lang_manager.get_text("manual_ctrl_grp_file"))
        self.select_file_btn.setText(lang_manager.get_text("manual_ctrl_btn_select_file"))
        self.send_btn.setText(lang_manager.get_text("manual_ctrl_btn_send_file"))
        self.close_btn.setText(lang_manager.get_text("manual_ctrl_btn_close"))

        # 기본 텍스트일 경우만 번역
        current_path = self.file_path_lbl.text()
        if lang_manager.text_matches_key(current_path, "manual_ctrl_lbl_file_path_no_file"):
            self.file_path_lbl.setText(lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"))

    def on_select_file_clicked(self) -> None:
        """파일 선택 버튼 핸들러"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang_manager.get_text("manual_ctrl_dialog_select_file")
        )
        if path:
            self.file_path_lbl.setText(path)
            self.send_btn.setEnabled(True)
            self.file_selected.emit(path)
            self.progress_widget.reset()

    def on_send_clicked(self) -> None:
        """전송 버튼 핸들러"""
        path = self.file_path_lbl.text()
        # 파일 경로 유효성 체크는 Presenter나 Dialog 로직에서 수행하되, 여기서는 UI 상태만 확인
        if path and path != lang_manager.get_text("manual_ctrl_lbl_file_path_no_file"):
            self.set_ui_busy_state(True)
            self.send_requested.emit(path)

    def set_ui_busy_state(self, busy: bool) -> None:
        """
        전송 중 UI 활성/비활성 상태 설정

        Args:
            busy (bool): 전송 중이면 True
        """
        self.select_file_btn.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.close_btn.setEnabled(not busy) # 전송 중에는 닫기 방지 (취소 버튼 유도)

    def update_progress(self, sent: int, total: int, speed: float, eta: float) -> None:
        """
        진행률 업데이트 (Presenter가 호출)

        Args:
            sent (int): 전송된 바이트
            total (int): 전체 바이트
            speed (float): 전송 속도 (bytes/s)
            eta (float): 남은 시간 (초)
        """
        self.progress_widget.update_progress(sent, total, speed, eta)

    def set_complete(self, success: bool, message: str = "") -> None:
        """
        완료 상태 설정 (Presenter가 호출)

        Args:
            success (bool): 성공 여부
            message (str): 완료 메시지
        """
        self.set_ui_busy_state(False)
        self.progress_widget.set_complete(success, message)

    def closeEvent(self, event) -> None:
        """다이얼로그 닫기 이벤트 핸들러"""
        # 전송 중 닫기 시도 시 취소 요청 발생
        if not self.send_btn.isEnabled(): # 전송 중임
            self.cancel_requested.emit()
        super().closeEvent(event)
