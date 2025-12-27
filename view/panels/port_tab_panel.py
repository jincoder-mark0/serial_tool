"""
포트 탭 패널 모듈

여러 개의 PortPanel을 탭 형태로 관리하는 컨테이너입니다.

## WHY
* 멀티 포트 환경에서 효율적인 공간 활용
* 탭 추가/삭제 및 동적 관리 기능 캡슐화
* '플러스(+)' 탭을 통한 직관적인 추가 UX 제공
* 외부에서 개별 탭의 내부 구현을 몰라도 데이터를 라우팅할 수 있는 인터페이스 제공

## WHAT
* QTabWidget 상속 및 커스텀 동작 구현
* 탭 추가, 닫기, 이름 변경 기능
* 특정 포트 탭으로의 데이터 라우팅 지원 (DTO 기반)
* 활성 탭 및 특정 인덱스 탭에 대한 안전한 접근자 제공

## HOW
* EventFilter를 통한 탭바 더블클릭 감지
* 플러스 탭 로직(항상 마지막에 위치, 클릭 시 새 탭 생성) 구현
* LogDataBatch DTO를 사용하여 데이터 분배
"""
from typing import Optional

from PyQt5.QtWidgets import QTabWidget, QWidget, QTabBar, QInputDialog
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon

from view.managers.language_manager import language_manager
from view.managers.theme_manager import theme_manager
from view.panels.port_panel import PortPanel
from common.dtos import LogDataBatch


class PortTabPanel(QTabWidget):
    """
    포트 탭들을 관리하는 패널입니다.
    탭 추가/삭제 및 '+' 탭 기능을 캡슐화하며, 하위 패널에 대한 접근 인터페이스를 제공합니다.
    """

    # 시그널 정의
    port_tab_added = pyqtSignal(object)  # 새 탭이 추가되었을 때 (PortPanel 객체 전달)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PortTabPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_port_tab)
        self.currentChanged.connect(self.on_tab_changed)
        self.setToolTip(language_manager.get_text("left_tooltip_port_tab"))

        # 탭바에서 더블클릭 이벤트 처리 위해 이벤트 필터 설치
        self.tabBar().installEventFilter(self)

        # 초기화: 플러스 탭 생성
        self.create_add_tab_btn()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        """
        UI를 현재 언어 설정에 맞게 업데이트합니다.
        """
        self.setToolTip(language_manager.get_text("left_tooltip_port_tab"))

    # -------------------------------------------------------------------------
    # Facade Accessors (View 내부 및 Presenter용 접근자)
    # -------------------------------------------------------------------------
    def get_current_port_panel(self) -> Optional[PortPanel]:
        """
        현재 선택된 탭의 PortPanel을 반환합니다.

        Returns:
            Optional[PortPanel]: 현재 활성화된 포트 패널. (없거나 +탭인 경우 None)
        """
        current_widget = self.currentWidget()
        if isinstance(current_widget, PortPanel):
            return current_widget
        return None

    def get_port_panel_at(self, index: int) -> Optional[PortPanel]:
        """
        특정 인덱스의 PortPanel을 반환합니다.

        Args:
            index (int): 탭 인덱스.

        Returns:
            Optional[PortPanel]: 해당 인덱스의 포트 패널.
        """
        widget = self.widget(index)
        if isinstance(widget, PortPanel):
            return widget
        return None

    # -------------------------------------------------------------------------
    # Event Handlers & Logic
    # -------------------------------------------------------------------------
    def eventFilter(self, obj, event):
        """
        탭바 더블클릭 이벤트를 감지합니다.
        더블클릭 시 탭 이름을 수정하는 다이얼로그를 띄웁니다.

        Args:
            obj: 이벤트 발생 객체.
            event: 이벤트 객체.

        Returns:
            bool: 이벤트 처리 여부.
        """
        if obj == self.tabBar() and event.type() == event.MouseButtonDblClick:
            # 더블클릭된 탭 인덱스 찾기
            index = self.tabBar().tabAt(event.pos())
            # 유효한 인덱스이고, 마지막 탭(플러스 탭)이 아닌 경우
            if 0 <= index < self.count() - 1:
                self.edit_tab_name(index)
                return True
        return super().eventFilter(obj, event)

    def edit_tab_name(self, index: int) -> None:
        """
        사용자 입력을 받아 탭 이름을 수정합니다.

        Args:
            index (int): 수정할 탭의 인덱스.
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
            - 마지막 탭(+)은 닫기 버튼 제거 (삭제 불가)
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
        플러스 탭의 아이콘을 현재 테마에 맞춰 업데이트합니다.

        Logic:
            - ThemeManager에서 'add' 아이콘 획득
            - 아이콘이 없으면 텍스트 '+'로 대체
        """
        count = self.count()
        if count == 0:
            return

        index = count - 1
        icon = theme_manager.get_icon("add")

        if icon.isNull():
            self.setTabText(index, "+")
            self.setTabIcon(index, QIcon())
        else:
            self.setTabIcon(index, icon)
            self.setTabText(index, "")

    def close_port_tab(self, index: int) -> None:
        """
        탭 닫기 요청을 처리합니다.

        Logic:
            - 마지막 탭(플러스 탭)은 닫을 수 없음
            - 최소 1개의 포트 탭은 유지 (플러스 탭 제외 count <= 2)
            - 시그널 차단 후 탭 제거 및 포커스 이동

        Args:
            index (int): 닫을 탭의 인덱스.
        """
        # 마지막 탭(+)은 닫을 수 없음
        if index == self.count() - 1:
            return

        # 최소 1개의 포트 탭은 유지 (플러스 탭 제외)
        # count가 2이면 [포트탭1개, +탭] 이므로 삭제 불가
        if self.count() <= 2:
            return

        # 시그널 차단하여 탭 삭제 시 on_tab_changed가 호출되지 않도록 함
        # (의도치 않은 새 탭 생성 방지)
        self.blockSignals(True)
        try:
            self.removeTab(index)

            # 삭제 후 적절한 탭으로 포커스 이동
            # 플러스 탭이 아닌 일반 탭으로 이동
            if self.count() > 1:
                # 삭제된 탭의 이전 탭으로 이동 (또는 0번 탭)
                new_index = max(0, index - 1)
                self.setCurrentIndex(new_index)
        finally:
            self.blockSignals(False)

    def on_tab_changed(self, index: int) -> None:
        """
        탭 변경 시 처리합니다.

        Args:
            index (int): 변경된 탭의 인덱스.
        """
        if index == -1:
            return

        # 마지막 탭(+)을 클릭하면 새 탭 추가 로직 실행
        if index == self.count() - 1:
            self.add_new_port_tab()

    def add_new_port_tab(self) -> PortPanel:
        """
        새로운 포트 탭을 추가하고 생성된 패널을 반환합니다.

        Logic:
            1. 기존 플러스 탭 제거
            2. 새 PortPanel 생성 및 추가
            3. 플러스 탭 다시 추가 (항상 마지막 유지)
            4. 새 탭으로 포커스 이동

        Returns:
            PortPanel: 추가된 포트 패널 객체.
        """
        # 시그널 차단 (탭 조작 중 불필요한 이벤트 방지)
        self.blockSignals(True)
        panel = PortPanel()

        try:
            # 1. 기존 플러스 탭 제거 (항상 마지막에 있음)
            count = self.count()
            if count > 0:
                self.removeTab(count - 1)

            # 2. 새 패널 추가 (닫기 버튼 자동 생성됨)
            initial_title = panel.get_tab_title()
            self.addTab(panel, initial_title)

            # 탭 제목 변경 시그널 연결 (PortPanel 내부 변경 -> 탭 제목 반영)
            panel.tab_title_changed.connect(lambda title, p=panel: self._on_panel_title_changed(p, title))

            # 3. 플러스 탭 다시 추가
            self.create_add_tab_btn()

            # 4. 새 탭으로 포커스 이동
            # 플러스 탭이 추가되었으므로 새 탭은 count-2 인덱스임
            new_tab_index = self.count() - 2
            self.setCurrentIndex(new_tab_index)

        finally:
            self.blockSignals(False)

        # 시그널 발행
        self.port_tab_added.emit(panel)
        return panel

    def append_rx_data(self, batch: LogDataBatch) -> None:
        """
        지정된 포트 이름을 가진 탭을 찾아 데이터를 추가합니다.

        Logic:
            - DTO에서 포트 이름과 데이터 추출
            - 모든 탭을 순회하며 일치하는 PortPanel 검색
            - 일치 시 해당 패널의 로그 인터페이스(Facade) 호출

        Args:
            batch (LogDataBatch): 로그 데이터 배치 DTO.
        """
        count = self.count()
        for i in range(count):
            # 마지막 탭(+) 제외
            if i == count - 1:
                continue

            widget = self.widget(i)
            if isinstance(widget, PortPanel):
                # DTO의 포트 이름과 일치하는지 확인
                if widget.get_port_name() == batch.port:
                    widget.append_log_data(batch.data)
                    return  # 찾았으면 종료

    def _on_panel_title_changed(self, panel: PortPanel, title: str) -> None:
        """
        패널의 탭 제목이 변경되었을 때 호출됩니다.
        실제 QTabWidget의 탭 텍스트를 업데이트합니다.

        Args:
            panel (PortPanel): 변경된 패널 객체.
            title (str): 새로운 탭 제목.
        """
        index = self.indexOf(panel)
        if index >= 0:
            self.setTabText(index, title)