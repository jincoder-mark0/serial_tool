from PyQt5.QtWidgets import QTabWidget, QWidget, QTabBar, QInputDialog
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
from typing import Optional
from view.managers.language_manager import language_manager
from view.managers.theme_manager import ThemeManager
from view.panels.port_panel import PortPanel

class PortTabPanel(QTabWidget):
    """
    포트 탭들을 관리하는 패널입니다.
    탭 추가/삭제 및 '+' 탭 기능을 캡슐화합니다.
    """

    # 시그널 정의
    port_tab_added = pyqtSignal(object)  # 새 탭이 추가되었을 때 (패널 전달)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_port_tab)
        self.currentChanged.connect(self.on_tab_changed)
        self.setToolTip(language_manager.get_text("left_tooltip_port_tab"))

        # 탭바에서 더블클릭 이벤트 처리 위해 이벤트 필터 설치
        self.tabBar().installEventFilter(self)

        # 초기화
        self.create_add_tab_btn()

        # 언어 변경 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        self.setToolTip(language_manager.get_text("left_tooltip_port_tab"))

    def eventFilter(self, obj, event):
        """탭바 더블클릭 이벤트를 감지합니다."""
        if obj == self.tabBar() and event.type() == event.MouseButtonDblClick:
            # 더블클릭된 탭 인덱스 찾기
            index = self.tabBar().tabAt(event.pos())
            if 0 <= index < self.count() - 1:  # 플러스 탭 제외
                self.edit_tab_name(index)
                return True
        return super().eventFilter(obj, event)

    def edit_tab_name(self, index: int) -> None:
        """탭 이름을 수정합니다."""

        widget = self.widget(index)
        if not isinstance(widget, PortPanel):
            return

        current_name = widget.get_custom_name()
        new_name, ok = QInputDialog.getText(
            self,
            "Edit Tab Name",
            "Enter custom name:",
            text=current_name
        )

        if ok and new_name and new_name != current_name:
            widget.set_custom_name(new_name)

    def create_add_tab_btn(self) -> None:
        """탭 추가를 위한 '+' 탭을 생성합니다."""
        # 빈 위젯 추가
        self.addTab(QWidget(), "")

        self.update_plus_tab_icon()

        # 마지막 탭(+)은 닫기 버튼 제거
        index = self.count() - 1
        self.tabBar().setTabButton(index, QTabBar.RightSide, None)
        self.tabBar().setTabButton(index, QTabBar.LeftSide, None)

    def update_plus_tab_icon(self) -> None:
        """플러스 탭의 아이콘을 테마에 맞춰 업데이트합니다."""
        count = self.count()
        if count == 0:
            return

        index = count - 1
        theme_manager = ThemeManager()
        icon = theme_manager.get_icon("add")

        if icon.isNull():
             self.setTabText(index, "+")
             self.setTabIcon(index, QIcon())
        else:
             self.setTabIcon(index, icon)
             self.setTabText(index, "")

    def close_port_tab(self, index: int) -> None:
        """탭 닫기 요청 처리"""
        # 마지막 탭(+)은 닫을 수 없음
        if index == self.count() - 1:
            return

        # 최소 1개의 포트 탭은 유지 (플러스 탭 제외)
        # count가 2이면 [포트탭1개, +탭] 이므로 삭제 불가
        if self.count() <= 2:
            return

        # 시그널 차단하여 탭 삭제 시 on_tab_changed가 호출되지 않도록 함
        self.blockSignals(True)
        try:
            self.removeTab(index)

            # 삭제 후 적절한 탭으로 포커스 이동
            # 플러스 탭이 아닌 탭으로 이동
            if self.count() > 1:  # 플러스 탭 외에 다른 탭이 있으면
                # 삭제된 탭의 이전 탭으로 이동 (또는 0번 탭)
                new_index = max(0, index - 1)
                self.setCurrentIndex(new_index)
            # else: 플러스 탭만 남은 경우는 그대로 둠
        finally:
            self.blockSignals(False)

    def on_tab_changed(self, index: int) -> None:
        """탭 변경 시 처리"""
        if index == -1: return

        # 마지막 탭(+)을 클릭하면 새 탭 추가
        if index == self.count() - 1:
            self.add_new_port_tab()

    def add_new_port_tab(self) -> "PortPanel":
        """새로운 포트 탭을 추가하고 패널을 반환합니다."""
        # 시그널 차단 (탭 조작 중 불필요한 이벤트 방지)
        self.blockSignals(True)
        try:
            # 1. 기존 플러스 탭 제거 (항상 마지막에 있음)
            count = self.count()
            if count > 0:
                self.removeTab(count - 1)

            # 2. 새 패널 추가 (닫기 버튼 자동 생성됨)
            panel = PortPanel()
            initial_title = panel.get_tab_title()
            self.addTab(panel, initial_title)

            # 탭 제목 변경 시그널 연결
            panel.tab_title_changed.connect(lambda title, p=panel: self._on_panel_title_changed(p, title))

            # 3. 플러스 탭 다시 추가
            self.create_add_tab_btn()

            # 4. 새 탭으로 포커스 이동
            # 플러스 탭이 추가되었으므로 새 탭은 count-2 인덱스임
            new_tab_index = self.count() - 2
            self.setCurrentIndex(new_tab_index)

        finally:
            self.blockSignals(False)

        # 시그널 차단 해제 후 변경 알림 (필요 시)
        # self.currentChanged.emit(self.currentIndex())

        self.port_tab_added.emit(panel)
        return panel

    def _on_panel_title_changed(self, panel: "PortPanel", title: str) -> None:
        """패널의 탭 제목이 변경되었을 때 호출됩니다."""
        index = self.indexOf(panel)
        if index >= 0:
            self.setTabText(index, title)
