"""
정보 대화상자 모듈

애플리케이션의 버전, 저작권, 설명 정보를 표시합니다.

## WHY
* 사용자에게 소프트웨어 정보를 제공하는 표준 인터페이스 필요

## WHAT
* 앱 이름, 버전, 설명, 저작권 정보 표시
* 닫기 버튼 제공

## HOW
* QDialog 상속 및 QVBoxLayout 구성
* LanguageManager를 통한 다국어 텍스트 적용
"""
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
        title_lbl = QLabel(language_manager.get_text("about_lbl_app_name"))
        title_lbl.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_lbl.setAlignment(Qt.AlignCenter)

        version_lbl = QLabel(language_manager.get_text("about_lbl_version"))
        version_lbl.setStyleSheet("font-size: 14px; color: #888;")
        version_lbl.setAlignment(Qt.AlignCenter)

        # 설명
        desc_lbl = QLabel(language_manager.get_text("about_lbl_description"))
        desc_lbl.setAlignment(Qt.AlignCenter)

        # 저작권
        copyright_lbl = QLabel(language_manager.get_text("about_lbl_copyright"))
        copyright_lbl.setStyleSheet("font-size: 12px; color: #666;")
        copyright_lbl.setAlignment(Qt.AlignCenter)

        # 닫기 버튼
        close_btn = QPushButton(language_manager.get_text("about_btn_close"))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)

        layout.addStretch()
        layout.addWidget(title_lbl)
        layout.addWidget(version_lbl)
        layout.addWidget(desc_lbl)
        layout.addStretch()
        layout.addWidget(copyright_lbl)
        layout.addStretch()
        layout.addWidget(close_btn)
        layout.setAlignment(close_btn, Qt.AlignCenter)
        layout.addStretch()

        self.setLayout(layout)
