from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt
from view.managers.language_manager import language_manager

class AboutDialog(QDialog):
    """
    애플리케이션 정보를 보여주는 About 다이얼로그입니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(language_manager.get_text("about_title"))
        self.setFixedSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        # 앱 이름 및 버전
        title_label = QLabel(language_manager.get_text("about_lbl_app_name"))
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)

        version_label = QLabel(language_manager.get_text("about_lbl_version"))
        version_label.setStyleSheet("font-size: 14px; color: #888;")
        version_label.setAlignment(Qt.AlignCenter)

        # 설명
        desc_label = QLabel(language_manager.get_text("about_lbl_description"))
        desc_label.setAlignment(Qt.AlignCenter)

        # 저작권
        copyright_label = QLabel(language_manager.get_text("about_lbl_copyright"))
        copyright_label.setStyleSheet("font-size: 12px; color: #666;")
        copyright_label.setAlignment(Qt.AlignCenter)

        # 닫기 버튼
        close_btn = QPushButton(language_manager.get_text("about_btn_close"))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)

        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(copyright_label)
        layout.addStretch()
        layout.addWidget(close_btn)
        layout.setAlignment(close_btn, Qt.AlignCenter)
        layout.addStretch()

        self.setLayout(layout)
