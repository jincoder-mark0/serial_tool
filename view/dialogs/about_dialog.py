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
from common.app_info import __version__
from common.constants import (
    DIALOG_SIZE_ABOUT_WIDTH, DIALOG_SIZE_ABOUT_HEIGHT,
    DIALOG_SPACING_ABOUT, CONTROL_WIDTH_ABOUT_CLOSE_BTN
)

class AboutDialog(QDialog):
    """
    애플리케이션 정보를 보여주는 About 다이얼로그입니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(language_manager.get_text("about_title"))
        # 고정 크기 대신 초기 크기 제안으로 둔다 (S-076).
        # 번역이 길어지거나 폰트 크기를 키우면 고정 크기는 내용을 수용하지 못하고
        # 위젯을 겹쳐 그린다 — 파일 전송 다이얼로그에서 실제로 그 일이 있었다.
        self.resize(DIALOG_SIZE_ABOUT_WIDTH, DIALOG_SIZE_ABOUT_HEIGHT)
        self.setMinimumWidth(DIALOG_SIZE_ABOUT_WIDTH)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(DIALOG_SPACING_ABOUT)

        # 앱 이름 및 버전
        title_lbl = QLabel(language_manager.get_text("about_lbl_app_name"))
        title_lbl.setProperty("class", "about-title")
        title_lbl.setAlignment(Qt.AlignCenter)

        version_lbl = QLabel(language_manager.get_text("about_lbl_version").format(__version__))
        version_lbl.setProperty("class", "about-version")
        version_lbl.setAlignment(Qt.AlignCenter)

        # 설명
        desc_lbl = QLabel(language_manager.get_text("about_lbl_description"))
        desc_lbl.setAlignment(Qt.AlignCenter)

        # 저작권
        copyright_lbl = QLabel(language_manager.get_text("about_lbl_copyright"))
        copyright_lbl.setProperty("class", "about-copyright")
        copyright_lbl.setAlignment(Qt.AlignCenter)

        # 닫기 버튼
        close_btn = QPushButton(language_manager.get_text("about_btn_close"))
        close_btn.setFixedWidth(CONTROL_WIDTH_ABOUT_CLOSE_BTN)
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
