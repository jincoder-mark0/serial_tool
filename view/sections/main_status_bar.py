from PyQt5.QtWidgets import QStatusBar
from view.language_manager import language_manager

class MainStatusBar(QStatusBar):
    """
    메인 윈도우의 상태바를 관리하는 클래스입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        """상태바 초기화"""
        self.showMessage(language_manager.get_text("main_status_msg_ready"))

    def show_message(self, message: str, timeout: int = 0) -> None:
        """
        상태바에 메시지를 표시합니다.

        Args:
            message (str): 표시할 메시지
            timeout (int): 메시지 표시 시간 (ms). 0이면 계속 표시.
        """
        self.showMessage(message, timeout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 상태바 텍스트를 업데이트합니다."""
        # (임시 메시지가 떠있는 경우는 그대로 둠)
        current_msg = self.currentMessage()
        if not current_msg or language_manager.text_matches_key(current_msg, "main_status_msg_ready"):
            self.showMessage(language_manager.get_text("main_status_msg_ready"))
