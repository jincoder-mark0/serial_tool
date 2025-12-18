"""
파일 전송 대화상자 모듈

파일 선택부터 전송 완료까지의 과정을 시각화하고 제어합니다.

## WHY
* 파일 전송은 긴 시간이 소요될 수 있으므로 전용 UI 필요
* 전송 진행률, 속도, 남은 시간 등 상세 정보 제공
* 사용자에게 취소 권한 부여

## WHAT
* 파일 선택 UI 및 전송/취소 버튼
* FileProgressWidget을 포함하여 진행 상황 표시
* Presenter와 통신하기 위한 시그널 정의

## HOW
* Passive View 패턴 적용 (로직은 FilePresenter에 위임)
* Modal 다이얼로그로 동작
"""
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QGroupBox, QMessageBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.managers.language_manager import language_manager
from view.widgets.file_progress import FileProgressWidget
from common.dtos import FileProgressState

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
        self.setWindowTitle(language_manager.get_text("manual_control_grp_file"))
        self.setFixedSize(450, 250)
        self.setModal(True)

        # UI Components
        self.file_path_lbl: Optional[QLabel] = None
        self.select_file_btn: Optional[QPushButton] = None
        self.send_btn: Optional[QPushButton] = None
        self.close_btn: Optional[QPushButton] = None
        self.progress_widget = None

        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃 초기화"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # ---------------------------------------------------------
        # 1. 파일 선택 영역
        # ---------------------------------------------------------
        file_grp = QGroupBox(language_manager.get_text("manual_control_grp_file"))
        file_layout = QVBoxLayout()

        path_layout = QHBoxLayout()
        self.file_path_lbl = QLabel(language_manager.get_text("manual_control_lbl_file_path_no_file"))
        self.file_path_lbl.setStyleSheet(
            "color: gray; border: 1px solid #555; padding: 5px; border-radius: 4px; background-color: #2b2b2b;"
        )
        self.file_path_lbl.setWordWrap(True)

        self.select_file_btn = QPushButton(language_manager.get_text("manual_control_btn_select_file"))
        self.select_file_btn.setFixedWidth(100)
        self.select_file_btn.clicked.connect(self.on_select_file_clicked)

        path_layout.addWidget(self.file_path_lbl, 1)
        path_layout.addWidget(self.select_file_btn)

        self.send_btn = QPushButton(language_manager.get_text("manual_control_btn_send_file"))
        self.send_btn.setProperty("class", "accent")
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.send_btn.setEnabled(False)

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
        self.close_btn = QPushButton(language_manager.get_text("manual_control_btn_close"))
        self.close_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.close_btn)

        layout.addWidget(file_grp)
        layout.addWidget(self.progress_widget)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """다국어 텍스트 업데이트"""
        self.setWindowTitle(language_manager.get_text("manual_control_grp_file"))
        self.select_file_btn.setText(language_manager.get_text("manual_control_btn_select_file"))
        self.send_btn.setText(language_manager.get_text("manual_control_btn_send_file"))
        self.close_btn.setText(language_manager.get_text("manual_control_btn_close"))

        # 기본 텍스트일 경우만 번역
        current_path = self.file_path_lbl.text()
        if language_manager.text_matches_key(current_path, "manual_control_lbl_file_path_no_file"):
            self.file_path_lbl.setText(language_manager.get_text("manual_control_lbl_file_path_no_file"))

    def on_select_file_clicked(self) -> None:
        """파일 선택 버튼 핸들러"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            language_manager.get_text("manual_control_dialog_select_file")
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
        if path and path != language_manager.get_text("manual_control_lbl_file_path_no_file"):
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
        self.close_btn.setEnabled(not busy)

    def update_progress(self, state: FileProgressState) -> None:
        """
        진행률 업데이트 (Presenter가 호출)

        Args:
            state (FileProgressState): 파일 전송 상태 DTO
        """
        self.progress_widget.update_progress(state.sent_bytes, state.total_bytes, state.speed, state.eta)

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
        if not self.send_btn.isEnabled():
            self.cancel_requested.emit()
        super().closeEvent(event)
