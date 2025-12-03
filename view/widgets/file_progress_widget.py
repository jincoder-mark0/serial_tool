from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QLabel, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.language_manager import language_manager

class FileProgressWidget(QWidget):
    """
    파일 전송 진행률을 표시하는 위젯입니다.
    진행률 바, 전송 속도, 남은 시간(ETA), 취소 버튼을 포함합니다.
    """
    
    cancel_requested = pyqtSignal()  # 취소 요청 시그널

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        self.reset()
        
        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # 파일명 및 상태 레이블
        self.status_label = QLabel(language_manager.get_text("ready"))
        self.status_label.setStyleSheet("font-weight: bold;")
        
        # 진행률 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        
        # 상세 정보 (속도, ETA) 및 취소 버튼
        info_layout = QHBoxLayout()
        
        self.speed_label = QLabel("0 KB/s")
        self.eta_label = QLabel(language_manager.get_text("eta_placeholder"))
        
        self.cancel_btn = QPushButton(language_manager.get_text("cancel"))
        self.cancel_btn.setFixedWidth(60)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.setEnabled(False)
        
        info_layout.addWidget(self.speed_label)
        info_layout.addStretch()
        info_layout.addWidget(self.eta_label)
        info_layout.addWidget(self.cancel_btn)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addLayout(info_layout)
        
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        # 상태 레이블은 현재 상태에 따라 동적으로 변경되므로 여기서 일괄 변경하기 어려움
        # 다만, Ready 상태라면 변경 가능
        if self.status_label.text() == language_manager.get_text("ready", "en") or \
           self.status_label.text() == language_manager.get_text("ready", "ko"):
            self.status_label.setText(language_manager.get_text("ready"))
            
        self.cancel_btn.setText(language_manager.get_text("cancel"))
        
        # ETA 플레이스홀더 업데이트 (진행 중이 아닐 때)
        if self.eta_label.text() == language_manager.get_text("eta_placeholder", "en") or \
           self.eta_label.text() == language_manager.get_text("eta_placeholder", "ko"):
            self.eta_label.setText(language_manager.get_text("eta_placeholder"))

    def update_progress(self, sent_bytes: int, total_bytes: int, speed_bps: float, eta_seconds: float) -> None:
        """
        진행률 및 상태를 업데이트합니다.
        
        Args:
            sent_bytes (int): 전송된 바이트 수
            total_bytes (int): 전체 바이트 수
            speed_bps (float): 전송 속도 (bytes/sec)
            eta_seconds (float): 남은 시간 (초)
        """
        if total_bytes > 0:
            percent = int((sent_bytes / total_bytes) * 100)
            self.progress_bar.setValue(percent)
        
        # 속도 포맷팅 (KB/s, MB/s)
        if speed_bps < 1024:
            speed_str = f"{speed_bps:.1f} B/s"
        elif speed_bps < 1024 * 1024:
            speed_str = f"{speed_bps/1024:.1f} KB/s"
        else:
            speed_str = f"{speed_bps/(1024*1024):.1f} MB/s"
            
        self.speed_label.setText(speed_str)
        
        # ETA 포맷팅 (MM:SS)
        eta_min = int(eta_seconds // 60)
        eta_sec = int(eta_seconds % 60)
        self.eta_label.setText(f"ETA: {eta_min:02d}:{eta_sec:02d}")
        
        # 상태 메시지 업데이트
        status_msg = language_manager.get_text("sending_status").format(sent_bytes, total_bytes)
        self.status_label.setText(status_msg)
        self.cancel_btn.setEnabled(True)

    def reset(self) -> None:
        """위젯 상태를 초기화합니다."""
        self.progress_bar.setValue(0)
        self.status_label.setText(language_manager.get_text("ready"))
        self.speed_label.setText("0 KB/s")
        self.eta_label.setText(language_manager.get_text("eta_placeholder"))
        self.cancel_btn.setEnabled(False)
        
    def set_complete(self, success: bool, message: str = "") -> None:
        """
        전송 완료 상태를 설정합니다.
        
        Args:
            success (bool): 성공 여부
            message (str): 완료 메시지
        """
        self.cancel_btn.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            status_msg = language_manager.get_text("completed_status").format(message)
            self.status_label.setText(status_msg)
        else:
            status_msg = language_manager.get_text("failed_status").format(message)
            self.status_label.setText(status_msg)
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
