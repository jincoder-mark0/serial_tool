"""
메인 윈도우 좌측 섹션 모듈

포트 탭 패널, 수동 제어 패널, 시스템 로그 위젯을 포함하는 좌측 영역 컨테이너입니다.

## WHY
* 화면 레이아웃의 논리적 구획(좌/우)을 분리하여 관리
* 포트 연결 및 제어와 관련된 기능들을 물리적으로 그룹화
* 하위 패널 간의 상호작용(예: 탭 변경 시 제어 패널 활성화 상태 동기화) 중재

## WHAT
* PortTabPanel, ManualControlPanel, SystemLogWidget 배치 및 레이아웃 설정
* 하위 패널 간의 시그널 라우팅 및 상태 동기화 로직
* Presenter와의 통신을 위한 시그널 집계 및 Facade 메서드 제공

## HOW
* QVBoxLayout을 사용하여 위젯들을 수직으로 배치
* PortTabPanel에 가변 공간(Stretch)을 할당하여 윈도우 리사이징 대응
* DTO(LogDataBatch, SystemLogEvent)를 사용하여 데이터 흐름 처리
"""
from typing import Optional, Dict, Any, Callable, List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtCore import pyqtSignal, QTimer

from view.managers.language_manager import language_manager
from view.panels.port_panel import PortPanel
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.port_tab_panel import PortTabPanel
from view.widgets.system_log import SystemLogWidget
from common.dtos import LogDataBatch, SystemLogEvent, ColorRule, PortInfo
from common.constants import LAYOUT_MARGIN_NONE


class MainLeftSection(QWidget):
    """
    좌측 섹션 관리 클래스

    PortTabPanel, ManualControlPanel, SystemLogWidget을 포함하며,
    외부(Presenter)에서 내부 구조를 몰라도 기능을 수행할 수 있도록 Facade 메서드를 제공합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 하위 패널의 이벤트를 상위(MainWindow/Presenter)로 전달하기 위한 시그널
    send_requested = pyqtSignal(object)  # ManualCommand DTO 전달
    port_tab_added = pyqtSignal(object)  # 생성된 PortPanel 객체 전달
    port_tab_closed = pyqtSignal(str)    # 닫힌 탭의 포트 이름 전달
    current_tab_changed = pyqtSignal()   # 탭 변경 알림 (Presenter 동기화용)

    # 시스템 로그 REC 토글 요청 (S-052: SystemLogWidget 시그널을 그대로 재발행 —
    # PortPanel이 DataLogWidget의 logging_start/stop_requested를 재발행하는 것과 동일 패턴)
    sys_logging_start_requested = pyqtSignal()
    sys_logging_stop_requested = pyqtSignal()
    # 시스템 로그 화면에 실제로 추가된 한 줄 재발행 (S-055: 실제 파일 기록 연동용)
    system_log_line_appended = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MainLeftSection을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)

        # UI 컴포넌트 변수 초기화 (은닉화)
        self._port_tab_panel: Optional[PortTabPanel] = None
        self._manual_control_panel: Optional[ManualControlPanel] = None
        self._system_log_widget: Optional[SystemLogWidget] = None

        self.init_ui()

        # 언어 변경 시그널 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            1. 수직 레이아웃(QVBoxLayout) 생성
            2. 포트 탭 패널 생성 및 시그널 연결
            3. 수동 제어 패널 생성 및 시그널 연결
            4. 시스템 로그 위젯 생성
            5. 레이아웃에 위젯 추가 (포트 탭 패널에 Stretch 부여)
        """
        layout = QVBoxLayout()
        layout.setContentsMargins(LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE,
                                   LAYOUT_MARGIN_NONE, LAYOUT_MARGIN_NONE)
        layout.setSpacing(10)  # 형제 패널 폭 대비 넓은 간격 유지 (기존 값, 상수 목록에 없음)

        # ---------------------------------------------------------
        # 1. 포트 탭 패널 (Port Tabs)
        # ---------------------------------------------------------
        self._port_tab_panel = PortTabPanel()
        # 내부 핸들러 연결 (상태 동기화용)
        self._port_tab_panel.port_tab_added.connect(self._on_port_tab_added)
        # 외부 전달용 시그널 연결
        self._port_tab_panel.port_tab_added.connect(self.port_tab_added.emit)
        self._port_tab_panel.port_tab_closed.connect(self.port_tab_closed.emit)

        # 탭 변경 시 시그널 연결
        self._port_tab_panel.currentChanged.connect(self._on_tab_changed)
        self._port_tab_panel.currentChanged.connect(self.current_tab_changed.emit)

        # ---------------------------------------------------------
        # 2. 수동 제어 패널 (Manual Control)
        # ---------------------------------------------------------
        self._manual_control_panel = ManualControlPanel()
        self._manual_control_panel.send_requested.connect(self.send_requested.emit)

        # ---------------------------------------------------------
        # 3. 시스템 로그 (System Log)
        # ---------------------------------------------------------
        self._system_log_widget = SystemLogWidget()
        # 로깅 요청 시그널 재발행 (S-052: PortPanel이 DataLogWidget 시그널을
        # 재발행하는 것과 동일한 Facade 패턴 — Presenter는 위젯 내부 구조를 모른다)
        self._system_log_widget.sys_logging_start_requested.connect(
            self.sys_logging_start_requested.emit
        )
        self._system_log_widget.sys_logging_stop_requested.connect(
            self.sys_logging_stop_requested.emit
        )
        # 실제 파일 기록용 라인 재발행 (S-055)
        self._system_log_widget.system_log_line_appended.connect(
            self.system_log_line_appended.emit
        )

        # 레이아웃 배치
        # 포트 탭 패널이 남은 공간을 모두 차지하도록 설정 (Stretch 1)
        layout.addWidget(self._port_tab_panel, 1)
        layout.addWidget(self._manual_control_panel)
        layout.addWidget(self._system_log_widget)

        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """
        다국어 텍스트를 업데이트합니다.
        (현재 섹션 자체에는 텍스트가 없으나, 하위 위젯들이 각자 처리함)
        """
        pass

    # -------------------------------------------------------------------------
    # Accessors (Properties for MainWindow/Presenter)
    # -------------------------------------------------------------------------
    @property
    def manual_control_panel(self) -> ManualControlPanel:
        """
        ManualControlPanel 객체를 반환합니다.
        (MainPresenter에서 ManualControlPresenter를 초기화할 때 필요)

        Returns:
            ManualControlPanel: 수동 제어 패널 인스턴스.
        """
        return self._manual_control_panel

    @property
    def port_tab_panel(self) -> PortTabPanel:
        """
        PortTabPanel 객체를 반환합니다.

        Returns:
            PortTabPanel: 포트 탭 패널 인스턴스.
        """
        return self._port_tab_panel

    # -------------------------------------------------------------------------
    # Facade Interface (Presenter 연동)
    # -------------------------------------------------------------------------
    def is_current_port_connected(self) -> bool:
        """
        현재 활성 포트 패널의 연결 여부를 반환합니다.

        Returns:
            bool: 연결 여부. 탭이 없거나 선택되지 않았으면 False.
        """
        current_widget = self._port_tab_panel.currentWidget()
        if isinstance(current_widget, PortPanel):
            if hasattr(current_widget, 'is_connected'):
                return current_widget.is_connected()
        return False

    def connect_tab_changed_signal(self, slot: Callable[[int], None]) -> None:
        """
        탭 변경 시그널을 외부 슬롯에 연결합니다.

        Args:
            slot (Callable): 연결할 슬롯.
        """
        self._port_tab_panel.currentChanged.connect(slot)

    def get_port_tabs_count(self) -> int:
        """현재 열려있는 포트 탭의 개수를 반환합니다."""
        return self._port_tab_panel.count()

    def get_port_panel_at(self, index: int) -> Optional[PortPanel]:
        """
        인덱스에 해당하는 포트 패널을 반환합니다.

        Args:
            index (int): 탭 인덱스.

        Returns:
            Optional[PortPanel]: 포트 패널 객체.
        """
        widget = self._port_tab_panel.widget(index)
        if isinstance(widget, PortPanel):
            return widget
        return None

    def get_port_panels(self) -> List[PortPanel]:
        """
        현재 존재하는 모든 포트 패널을 반환합니다.

        Presenter가 탭 개수/인덱스 구조를 알지 않고, 개별 PortPanel의 시그널 계약만
        연결할 수 있도록 컬렉션 형태의 Facade를 제공합니다.
        """
        panels: List[PortPanel] = []
        for index in range(self._port_tab_panel.count()):
            panel = self.get_port_panel_at(index)
            if panel:
                panels.append(panel)
        return panels

    def get_current_port_panel(self) -> Optional[PortPanel]:
        """
        현재 활성화된 포트 패널을 반환합니다.

        Returns:
            Optional[PortPanel]: 현재 포트 패널 객체.
        """
        widget = self._port_tab_panel.currentWidget()
        if isinstance(widget, PortPanel):
            return widget
        return None

    def get_current_port_name(self) -> str:
        """
        현재 활성 포트의 이름을 반환합니다.

        Returns:
            str: 포트 이름. (없으면 빈 문자열)
        """
        panel = self.get_current_port_panel()
        if panel and hasattr(panel, 'get_port_name'):
            return panel.get_port_name()
        return ""

    def set_port_list_for_all(self, port_list: List[PortInfo]) -> None:
        """
        모든 포트 패널의 선택 가능한 포트 목록을 갱신합니다.

        Presenter는 탭 개수나 인덱스를 순회하지 않고 스캔 결과만 전달합니다.
        """
        for panel in self.get_port_panels():
            panel.set_port_list(port_list)

    def set_port_connection_state(self, port_name: str, connected: bool) -> None:
        """
        지정한 포트를 사용하는 패널의 연결 표시 상태를 갱신합니다.

        Args:
            port_name (str): 상태를 갱신할 포트 이름.
            connected (bool): 연결 여부.
        """
        for panel in self.get_port_panels():
            if panel.get_port_name() == port_name:
                panel.set_connected(connected)
                break

    def log_system_message(self, event: SystemLogEvent) -> None:
        """
        시스템 로그에 메시지를 추가합니다.

        Args:
            event (SystemLogEvent): 시스템 로그 이벤트 DTO.
        """
        self._system_log_widget.append_log(event)

    def show_error_message(self, title: str, message: str) -> None:
        """
        사용자에게 오류 메시지를 비재진입 방식으로 표시합니다.

        WHY:
            - Presenter가 QMessageBox/QWidget parent 같은 QtWidgets 구현 세부사항을
              알지 않도록 View 경계 안에 모달 표시 책임을 둡니다.
            - 포트 워커 정리 도중 즉시 모달을 열면 중첩 이벤트 루프가 실행되어
              정리 중인 객체가 파괴될 수 있으므로(S-082), 현재 호출 스택이
              종료된 뒤 다이얼로그를 표시합니다.

        Args:
            title (str): 다이얼로그 제목.
            message (str): 사용자에게 표시할 오류 상세 메시지.
        """
        QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))

    def set_system_log_color_rules(self, rules: List[ColorRule]) -> None:
        """
        시스템 로그 위젯에 색상 규칙을 설정합니다.

        Args:
            rules (List[ColorRule]): 색상 규칙 리스트.
        """
        self._system_log_widget.set_color_rules(rules)

    def show_save_log_dialog(self) -> str:
        """
        시스템 로그 저장 파일 다이얼로그를 표시합니다 (Presenter가 호출, S-052).

        PortPanel.show_save_log_dialog()과 동일한 Facade 패턴 — Presenter는
        SystemLogWidget 내부 구조를 몰라도 파일 경로를 얻을 수 있다.

        Returns:
            str: 선택된 파일 경로 (취소 시 빈 문자열).
        """
        return self._system_log_widget.show_save_log_dialog()

    def set_logging_active(self, active: bool) -> None:
        """
        시스템 로그 REC 상태를 설정합니다 (Presenter가 호출, S-052).

        Args:
            active (bool): 로깅 활성화 여부.
        """
        self._system_log_widget.set_logging_active(active)

    def trigger_current_port_log_save(self) -> None:
        """
        현재 활성 탭의 로그 저장을 트리거합니다.
        """
        panel = self.get_current_port_panel()
        panel.trigger_log_save()

    def clear_current_port_log(self) -> None:
        """
        현재 활성 탭의 로그를 지웁니다.
        """
        panel = self.get_current_port_panel()
        if panel:
            panel.clear_data_log()

    # -------------------------------------------------------------------------
    # 포트 및 탭 제어 인터페이스
    # -------------------------------------------------------------------------

    def add_new_port_tab(self) -> None:
        """새로운 포트 탭을 추가합니다."""
        self._port_tab_panel.add_new_port_tab()

    def add_new_tab(self, port: str) -> None:
        """
        특정 포트로 새로운 탭을 추가합니다 (복원용).
        """
        # 탭 위젯 생성 (PortPanel 가정)
        tab = PortPanel(port)

        # 개별 탭의 연결 상태 변경 시그널을 핸들러에 연결
        if hasattr(tab, 'connection_changed'):
             tab.connection_changed.connect(self._on_port_connection_changed)

        # 탭 추가
        self._port_tab_panel.addTab(tab, port)

        # 새 탭으로 포커스 이동 (이때 _on_tab_changed가 호출됨)
        self._port_tab_panel.setCurrentWidget(tab)

    def open_current_port(self) -> None:
        """
        현재 활성화된 탭의 포트 연결을 엽니다.
        """
        current_widget = self.get_current_port_panel()
        if current_widget:
            if not current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_port(self) -> None:
        """
        현재 활성화된 탭의 포트 연결을 닫습니다.
        """
        current_widget = self.get_current_port_panel()
        if current_widget:
            if current_widget.is_connected():
                current_widget.toggle_connection()

    def close_current_tab(self) -> None:
        """
        현재 활성화된 탭을 닫습니다 (플러스 탭 제외).
        """
        current_index = self._port_tab_panel.currentIndex()
        # 마지막 탭(플러스 탭)은 닫을 수 없음
        if current_index == self._port_tab_panel.count() - 1:
            return

        if current_index >= 0:
            self._port_tab_panel.close_port_tab(current_index)

    # -------------------------------------------------------------------------
    # 데이터 처리 인터페이스
    # -------------------------------------------------------------------------

    def append_data_to_current_port(self, data: bytes) -> None:
        """
        현재 활성화된 포트 탭의 로그창에 데이터(Local Echo 등)를 추가합니다.

        Args:
            data (bytes): 추가할 데이터.
        """
        current_widget = self.get_current_port_panel()
        if current_widget:
            current_widget.append_log_data(data)

    def append_rx_data(self, batch: LogDataBatch) -> None:
        """
        수신된 데이터를 특정 포트 탭에 추가합니다.

        Logic:
            - DTO를 PortTabPanel로 전달하여 적절한 탭을 찾아 라우팅합니다.

        Args:
            batch (LogDataBatch): 로그 데이터 배치 DTO.
        """
        self._port_tab_panel.append_rx_data(batch)

    # -------------------------------------------------------------------------
    # 내부 시그널 핸들러
    # -------------------------------------------------------------------------

    def _on_port_tab_added(self, panel: PortPanel) -> None:
        """
        새 탭이 추가되었을 때 호출되는 핸들러입니다.
        해당 탭의 연결 상태 변경 시그널을 모니터링하여 UI 동기화를 수행합니다.

        Args:
            panel (PortPanel): 추가된 포트 패널.
        """
        # PortPanel의 Facade Signal을 통해 연결 상태 변경 감지
        panel.connection_changed.connect(self._on_port_connection_changed)

    def _on_tab_changed(self, index: int) -> None:
        """
        탭이 변경되었을 때 호출됩니다.
        변경된 탭의 상태에 맞춰 컨트롤 활성화 상태를 갱신합니다.

        Args:
            index (int): 변경된 탭 인덱스.
        """
        self._sync_manual_control_state()

    def _on_port_connection_changed(self, connected: bool) -> None:
        """
        특정 포트의 연결 상태가 변경되었을 때 호출됩니다.

        Logic:
            - 시그널을 보낸 탭이 현재 활성 탭인지 확인
            - 활성 탭인 경우 ManualControl 활성화/비활성화 상태 동기화

        Args:
            connected (bool): 연결 여부.
        """
        self._sync_manual_control_state()

    def _sync_manual_control_state(self) -> None:
        """
        현재 활성 탭의 연결 상태를 기반으로 ManualControlPanel의 활성화 상태를 동기화합니다.
        """
        current_widget = self.get_current_port_panel()

        if current_widget:
            is_connected = current_widget.is_connected()
            self._manual_control_panel.set_controls_enabled(is_connected)
        else:
            # 탭이 없거나, '+' 탭 등인 경우 비활성화
            self._manual_control_panel.set_controls_enabled(False)

    # -------------------------------------------------------------------------
    # 상태 저장 및 복원 (Persistence)
    # -------------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """
        현재 섹션 내 모든 하위 위젯의 상태를 수집하여 반환합니다.

        Returns:
            Dict[str, Any]: 통합된 상태 데이터.
        """
        manual_state = self._manual_control_panel.get_state()
        port_states = []
        count = self._port_tab_panel.count()

        for i in range(count):
            # 마지막 탭(+) 제외
            if i == count - 1:
                continue
            widget = self._port_tab_panel.widget(i)
            if isinstance(widget, PortPanel):
                port_states.append(widget.get_state())

        return {
            "manual_control_panel": manual_state,
            "ports": port_states
        }

    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        저장된 상태 데이터를 UI에 복원합니다.

        Logic:
            - ManualControl 상태 복원
            - 기존 탭들을 모두 제거 (초기화)
            - 저장된 포트 상태 수만큼 탭을 새로 생성하고 상태 복원

        Args:
            state (Dict[str, Any]): 복원할 상태 데이터.
        """
        # 1. ManualControl 상태 복원
        manual_state = state.get("manual_control_panel", {})
        if manual_state:
            self._manual_control_panel.apply_state(manual_state)

        # 2. Port Tabs 상태 복원
        port_states = state.get("ports", [])

        # 탭 조작 중 시그널 발생 방지
        self._port_tab_panel.blockSignals(True)
        try:
            # 기존 탭 제거 (플러스 탭 제외하고 역순으로 제거)
            count = self._port_tab_panel.count()
            # 마지막 탭(count-1)은 +탭이므로 제외하고 그 앞부터 0번까지 역순 제거
            for i in range(count - 2, -1, -1):
                self._port_tab_panel.removeTab(i)

            # 저장된 상태가 없으면 기본 탭 하나 추가
            if not port_states:
                self._port_tab_panel.add_new_port_tab()
                return

            # 상태 복원 및 탭 생성
            for port_state in port_states:
                panel = self._port_tab_panel.add_new_port_tab()
                panel.apply_state(port_state)

        finally:
            self._port_tab_panel.blockSignals(False)

            # 복원 완료 후 현재 탭 상태 동기화 (첫 번째 탭 기준)
            if self._port_tab_panel.count() > 1:
                self._port_tab_panel.setCurrentIndex(0)
                self._sync_manual_control_state()