"""
포트 탭 패널 모듈

여러 개의 PortPanel을 탭 형태로 관리하는 컨테이너입니다.

## WHY
* 멀티 포트 환경에서 효율적인 공간 활용
* 탭 추가/삭제 및 동적 관리 기능 캡슐화
* '플러스(+)' 탭을 통한 직관적인 추가 UX 제공

## WHAT
* QTabWidget 상속 및 커스텀 동작 구현
* 탭 추가, 닫기, 이름 변경 기능
* 특정 포트 탭으로의 데이터 라우팅 지원

## HOW
* EventFilter를 통한 탭바 더블클릭 감지
* 플러스 탭 로직(항상 마지막에 위치, 클릭 시 새 탭 생성) 구현
"""
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
        """
        PortTabPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯
        """
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
        """
        UI를 언어에 맞게 재번역합니다.
        """
        self.setToolTip(language_manager.get_text("left_tooltip_port_tab"))

    def eventFilter(self, obj, event):
        """
        탭바 더블클릭 이벤트를 감지합니다.

        Args:
            obj: 이벤트 발생 객체
            event: 이벤트 객체
        """
        if obj == self.tabBar() and event.type() == event.MouseButtonDblClick:
            # 더블클릭된 탭 인덱스 찾기
            index = self.tabBar().tabAt(event.pos())
            if 0 <= index < self.count() - 1:  # 플러스 탭 제외
                self.edit_tab_name(index)
                return True
        return super().eventFilter(obj, event)

    def edit_tab_name(self, index: int) -> None:
        """
        탭 이름을 수정합니다.

        Args:
            index (int): 수정할 탭의 인덱스
        """

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
        """
        탭 추가를 위한 '+' 탭을 생성합니다.

        Logic:
            - 빈 위젯 추가
            - 플러스 탭 아이콘 업데이트
            - 마지막 탭(+)은 닫기 버튼 제거
        """
        # 빈 위젯 추가
        self.addTab(QWidget(), "")

        self.update_plus_tab_icon()

        # 마지막 탭(+)은 닫기 버튼 제거
        index = self.count() - 1
        self.tabBar().setTabButton(index, QTabBar.RightSide, None)
        self.tabBar().setTabButton(index, QTabBar.LeftSide, None)

    def update_plus_tab_icon(self) -> None:
        """
        플러스 탭의 아이콘을 테마에 맞춰 업데이트합니다.

        Logic:
            - 마지막 탭이 플러스 탭인지 확인
            - 테마 관리자에서 아이콘 가져오기
            - 아이콘 설정
        """
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
        """
        탭 닫기 요청 처리

        Args:
            index (int): 닫을 탭의 인덱스
        """
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
        """
        탭 변경 시 처리

        Args:
            index (int): 변경된 탭의 인덱스
        """
        if index == -1: return

        # 마지막 탭(+)을 클릭하면 새 탭 추가
        if index == self.count() - 1:
            self.add_new_port_tab()

    def add_new_port_tab(self) -> "PortPanel":
        """
        새로운 포트 탭을 추가하고 패널을 반환합니다.

        Returns:
            PortPanel: 추가된 포트 패널
        """
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

    def append_rx_data(self, port_name: str, data: bytes) -> None:
        """
        지정된 포트 이름을 가진 탭을 찾아 데이터를 추가합니다.

        Logic:
            - 모든 탭을 순회
            - PortPanel인지 확인하고 get_port_name() 비교
            - 일치하면 data_log_widget에 데이터 추가

        Args:
            port_name (str): 포트 이름
            data (bytes): 수신 데이터
        """
        count = self.count()
        for i in range(count):
            # 마지막 탭(+) 제외
            if i == count - 1:
                continue

            widget = self.widget(i)
            if isinstance(widget, PortPanel):
                if widget.get_port_name() == port_name:
                    if hasattr(widget, 'data_log_widget'):
                        widget.data_log_widget.append_data(data)
                    return # 찾았으면 종료

    def _on_panel_title_changed(self, panel: "PortPanel", title: str) -> None:
        """
        패널의 탭 제목이 변경되었을 때 호출됩니다.

        Args:
            panel (PortPanel): 변경된 패널
            title (str): 새로운 탭 제목
        """
        index = self.indexOf(panel)
        if index >= 0:
            self.setTabText(index, title)
