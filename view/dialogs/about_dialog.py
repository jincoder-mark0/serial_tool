from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from typing import Optional
import version

class AboutDialog(QDialog):
    """
    애플리케이션 정보를 표시하는 대화상자입니다.
    버전, 저작권, 라이선스 정보를 포함합니다.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About SerialTool")
        self.setFixedSize(400, 300)
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트를 초기화합니다."""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # 앱 이름 및 버전
        title_label = QLabel("SerialTool")
        title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        
        version_label = QLabel(f"Version {version.__version__}")
        version_label.setFont(QFont("Segoe UI", 12))
        version_label.setAlignment(Qt.AlignCenter)
        
        # 저작권 및 설명
        copyright_label = QLabel("© 2025 SerialTool Team. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        
        desc_label = QLabel(
            "SerialTool is a professional serial communication utility\n"
            "designed for high-performance logging and automation."
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        
        # 라이선스 정보
        license_label = QLabel("Licensed under MIT License")
        license_label.setAlignment(Qt.AlignCenter)
        
        # 닫기 버튼
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        
        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addSpacing(20)
        layout.addWidget(desc_label)
        layout.addSpacing(20)
        layout.addWidget(copyright_label)
        layout.addWidget(license_label)
        layout.addStretch()
        layout.addWidget(close_btn)
        layout.setAlignment(close_btn, Qt.AlignCenter)
        
        self.setLayout(layout)
