from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional, Dict, Any
from view.managers.language_manager import language_manager

from view.panels.macro_panel import MacroPanel
from view.panels.packet_panel import PacketPanel

class MainRightSection(QWidget):
    """
    MainWindow의 우측 영역을 담당하는 패널 클래스입니다.
    Macro List와 Packet Inspector를 탭으로 관리합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MainRightSection을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.packet_panel = None
        self.macro_panel = None
        self.tabs = None
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        self.macro_panel = MacroPanel()
        self.macro_panel.setToolTip(language_manager.get_text("right_tooltip_macro_list"))

        self.packet_panel = PacketPanel()
        self.packet_panel.setToolTip(language_manager.get_text("right_tooltip_packet"))

        self.tabs.addTab(self.macro_panel, language_manager.get_text("right_tab_macro_list"))
        self.tabs.addTab(self.packet_panel, language_manager.get_text("right_tab_packet"))

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.macro_panel.setToolTip(language_manager.get_text("right_tooltip_macro_list"))
        self.packet_panel.setToolTip(language_manager.get_text("right_tooltip_packet"))

        self.tabs.setTabText(0, language_manager.get_text("right_tab_macro_list"))
        self.tabs.setTabText(1, language_manager.get_text("right_tab_packet"))

    def save_state(self) -> Dict[str, Any]:
        """
        하위 패널들의 상태를 수집하여 반환합니다.

        Returns:
            Dict[str, Any]: {'macro_panel': {...}} 구조의 상태 데이터.
        """
        return {
            "macro_panel": self.macro_panel.save_state(),
            # PacketInspector 상태가 있다면 여기에 추가
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """
        전달받은 상태 딕셔너리를 하위 패널에 주입합니다.

        Args:
            state (Dict[str, Any]): {'macro_panel': {...}} 구조의 데이터.
        """
        if "macro_panel" in state:
            self.macro_panel.load_state(state["macro_panel"])