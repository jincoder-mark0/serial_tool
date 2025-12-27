"""
메인 윈도우 우측 섹션 모듈

매크로 리스트와 패킷 인스펙터를 탭으로 구성하여 표시하는 컨테이너입니다.

## WHY
* 부가 기능(자동화, 분석)을 우측 영역에 배치하여 공간 효율성 증대
* 탭 인터페이스를 통해 서로 다른 성격의 기능(제어 vs 분석)을 논리적으로 분리
* 화면 레이아웃 변경 시(패널 숨김/표시) 단일 단위로 제어하기 위함

## WHAT
* QTabWidget을 사용하여 MacroPanel과 PacketPanel 배치
* 하위 패널의 상태 저장/복원 중계 (Facade 역할)
* Presenter 연결을 위한 View 객체 접근자 제공

## HOW
* QVBoxLayout 및 QTabWidget 사용
* get_state/apply_state를 통해 하위 패널들의 데이터 지속성 관리
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from typing import Optional, Dict, Any
from view.managers.language_manager import language_manager

from view.panels.macro_panel import MacroPanel
from view.panels.packet_panel import PacketPanel


class MainRightSection(QWidget):
    """
    MainWindow의 우측 영역을 담당하는 섹션 클래스입니다.

    MacroPanel(매크로 관리)과 PacketPanel(패킷 분석)을 탭으로 관리하며,
    외부(Presenter)에 필요한 View 인터페이스를 제공합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MainRightSection 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # UI 컴포넌트 변수 선언
        self._macro_panel: Optional[MacroPanel] = None
        self._packet_panel: Optional[PacketPanel] = None
        self.tabs: Optional[QTabWidget] = None

        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            - 수직 레이아웃 생성
            - QTabWidget 생성 및 하위 패널(Macro, Packet) 추가
            - 레이아웃 배치
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        # 하위 패널 생성
        self._macro_panel = MacroPanel()
        self._macro_panel.setToolTip(language_manager.get_text("right_tooltip_macro_list"))

        self._packet_panel = PacketPanel()
        self._packet_panel.setToolTip(language_manager.get_text("right_tooltip_packet"))

        # 탭 추가
        self.tabs.addTab(self._macro_panel, language_manager.get_text("right_tab_macro_list"))
        self.tabs.addTab(self._packet_panel, language_manager.get_text("right_tab_packet"))

        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """
        언어 변경 시 UI 텍스트를 업데이트합니다.
        """
        self._macro_panel.setToolTip(language_manager.get_text("right_tooltip_macro_list"))
        self._packet_panel.setToolTip(language_manager.get_text("right_tooltip_packet"))

        self.tabs.setTabText(0, language_manager.get_text("right_tab_macro_list"))
        self.tabs.setTabText(1, language_manager.get_text("right_tab_packet"))

    # -------------------------------------------------------------------------
    # View Accessors (Presenter에서 사용할 View 객체 반환)
    # -------------------------------------------------------------------------
    @property
    def macro_panel(self) -> MacroPanel:
        """
        MacroPresenter가 제어할 MacroPanel 뷰를 반환합니다.

        Returns:
            MacroPanel: 매크로 패널 객체.
        """
        return self._macro_panel

    @property
    def packet_panel(self) -> PacketPanel:
        """
        PacketPresenter가 제어할 PacketPanel 뷰를 반환합니다.

        Returns:
            PacketPanel: 패킷 패널 객체.
        """
        return self._packet_panel

    # -------------------------------------------------------------------------
    # State Persistence (상태 저장/복원)
    # -------------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """
        현재 섹션 및 하위 패널들의 상태를 수집하여 반환합니다.

        Logic:
            - 현재 선택된 탭 인덱스 저장
            - 하위 패널들의 상태(get_state) 재귀적 호출

        Returns:
            Dict[str, Any]: 상태 데이터 딕셔너리.
        """
        state = {
            "current_tab_index": self.tabs.currentIndex(),
            "macro_panel": self._macro_panel.get_state(),
            # PacketPanel의 상태(버퍼 크기, 오토스크롤 등)는 주로 PreferencesDialog에서 관리되지만,
            # 뷰 자체의 임시 상태가 있다면 여기서 저장 가능. 현재는 매크로 위주.
        }
        return state

    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        전달받은 상태 딕셔너리를 하위 패널에 주입합니다.

        Logic:
            - 매크로 패널 상태 복원
            - 저장된 탭 인덱스로 탭 전환

        Args:
            state (Dict[str, Any]): 복원할 상태 데이터.
        """
        if not state:
            return

        # 하위 패널 상태 복원
        if "macro_panel" in state:
            self._macro_panel.apply_state(state["macro_panel"])

        # 탭 인덱스 복원
        if "current_tab_index" in state:
            index = state["current_tab_index"]
            if 0 <= index < self.tabs.count():
                self.tabs.setCurrentIndex(index)