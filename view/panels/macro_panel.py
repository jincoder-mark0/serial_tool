"""
매크로 패널 모듈

매크로 리스트(List)와 제어(Control) 위젯을 통합하여 관리하는 컨테이너 패널입니다.
Presenter와 하위 위젯 사이의 인터페이스(Facade) 역할을 수행합니다.

## WHY
* 매크로 관련 기능(목록 관리, 실행 제어)을 하나의 논리적 단위로 그룹화
* 하위 위젯 간의 레이아웃 관리 및 시그널 중계 책임
* Presenter가 구체적인 위젯 구현을 알지 못하게 하여 결합도 감소 (LoD 준수)

## WHAT
* MacroListWidget과 MacroControlWidget 배치
* 파일 저장/로드 및 실행 제어(시작/정지/일시정지) 시그널 정의
* 상태 저장/복원 및 UI 제어를 위한 Facade 메서드 제공

## HOW
* QVBoxLayout을 사용하여 상단(List)과 하단(Control) 배치
* 하위 위젯의 이벤트를 상위로 전달(Bubbling)하거나 로직을 거쳐 재발신
* DTO(MacroScriptData, MacroExecutionRequest)를 사용하여 데이터 구조화
"""
from typing import Optional, Dict, Any, List

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal

from view.widgets.macro_list import MacroListWidget
from view.widgets.macro_control import MacroControlWidget
from view.managers.language_manager import language_manager
from common.dtos import (
    MacroScriptData,
    MacroRepeatOption,
    MacroExecutionRequest,
    MacroEntry
)


class MacroPanel(QWidget):
    """
    매크로 관리 및 실행 패널 클래스

    MacroListWidget과 MacroControlWidget을 감싸고 있으며,
    Presenter와의 통신을 위한 시그널 및 상태 조회 인터페이스(Facade)를 정의합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 매크로 실행 제어 시그널
    repeat_start_requested = pyqtSignal(object)  # MacroExecutionRequest DTO
    repeat_stop_requested = pyqtSignal()
    repeat_pause_requested = pyqtSignal()

    # 데이터 변경 알림 (저장되지 않은 변경사항 추적용)
    state_changed = pyqtSignal()

    # 파일 저장/로드 요청 시그널 (DTO 사용)
    script_save_requested = pyqtSignal(object) # MacroScriptData
    script_load_requested = pyqtSignal(str)    # file_path

    # 브로드캐스트 상태 변경 시그널 (MainPresenter의 전송 버튼 활성화 로직용)
    broadcast_changed = pyqtSignal(bool)

    # 리스트의 개별 전송 버튼 클릭 시그널 중계
    send_row_requested = pyqtSignal(int, object) # (row_index, MacroEntry)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)

        # 내부 위젯 (캡슐화를 위해 protected 변수 사용)
        self._macro_control: Optional[MacroControlWidget] = None
        self._macro_list: Optional[MacroListWidget] = None

        self._loading = False

        self.init_ui()

    def init_ui(self) -> None:
        """
        UI 컴포넌트 및 레이아웃을 초기화합니다.

        Logic:
            - List 및 Control 위젯 생성
            - 각 위젯의 시그널을 패널 시그널로 연결 (중계)
            - 레이아웃 배치
        """
        self._macro_list = MacroListWidget()
        self._macro_control = MacroControlWidget()

        # ---------------------------------------------------------------------
        # Signal Connections (Widget -> Panel)
        # ---------------------------------------------------------------------
        # 1. 실행 제어 시그널 연결
        self._macro_control.macro_repeat_start_requested.connect(self.on_repeat_start_requested)
        self._macro_control.macro_repeat_stop_requested.connect(self.on_repeat_stop_requested)
        # 일시정지는 별도 로직 없이 바로 중계
        self._macro_control.macro_repeat_pause_requested.connect(self.repeat_pause_requested.emit)

        # 2. 파일 관리 시그널 연결 (다이얼로그 호출 핸들러 연결)
        self._macro_control.script_save_requested.connect(self.on_save_clicked)
        self._macro_control.script_load_requested.connect(self.on_load_clicked)

        # 3. 데이터 변경 알림 연결
        self._macro_list.macro_list_changed.connect(self.state_changed.emit)

        # 4. 브로드캐스트 상태 변경 중계 (Relay)
        self._macro_control.broadcast_changed.connect(self.broadcast_changed.emit)

        # 5. 리스트 개별 전송 중계
        self._macro_list.send_row_requested.connect(self.send_row_requested.emit)

        # ---------------------------------------------------------------------
        # Layout Setup
        # ---------------------------------------------------------------------
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 리스트가 가능한 많은 공간을 차지하도록 배치
        layout.addWidget(self._macro_list, stretch=1)
        layout.addWidget(self._macro_control, stretch=0)

        self.setLayout(layout)

    # -------------------------------------------------------------------------
    # Facade Interfaces (Presenter용 Getter/Setter)
    # -------------------------------------------------------------------------
    def set_controls_enabled(self, enabled: bool) -> None:
        """
        패널 내 모든 컨트롤의 활성화 상태를 설정합니다.

        Args:
            enabled (bool): 활성화 여부.
        """
        # 하위 위젯들에게 활성화 상태 전파
        self._macro_control.set_controls_enabled(enabled)
        self._macro_list.set_send_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        """
        브로드캐스트 체크박스 상태를 반환합니다.

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        # 하위 위젯의 인터페이스 호출
        if self._macro_control:
            return self._macro_control.is_broadcast_enabled()
        return False

    def get_macro_entries(self) -> List[MacroEntry]:
        """
        현재 리스트에 있는 모든 매크로 항목을 반환합니다.

        Returns:
            List[MacroEntry]: 매크로 항목 리스트.
        """
        return self._macro_list.get_macro_entries()

    def set_current_row(self, row: int) -> None:
        """
        실행 중인 행을 하이라이트하고 스크롤합니다.

        Args:
            row (int): 행 인덱스. -1이면 초기화.
        """
        self._macro_list.set_current_row(row)

    def set_running_state(self, running: bool, is_repeat: bool = False) -> None:
        """
        실행 상태를 UI에 반영합니다. (버튼 활성화/비활성화 등)

        Args:
            running (bool): 실행 중 여부.
            is_repeat (bool): 반복 모드인지 여부.
        """
        self._macro_control.set_running_state(running, is_repeat)

    def update_auto_count(self, current: int, total: int) -> None:
        """
        반복 실행 카운트를 업데이트합니다.

        Args:
            current (int): 현재 반복 횟수.
            total (int): 전체 반복 횟수.
        """
        self._macro_control.update_auto_count(current, total)

    # -------------------------------------------------------------------------
    # Internal Handlers & Logic
    # -------------------------------------------------------------------------
    def on_save_clicked(self) -> None:
        """
        저장 버튼 클릭 핸들러

        Logic:
            1. 파일 저장 다이얼로그 표시
            2. 사용자가 경로 선택 시 현재 상태(get_state) 수집
            3. DTO 생성 후 Presenter에 전달
        """
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getSaveFileName(
            self,
            language_manager.get_text("macro_panel_dialog_title_save"),
            "",
            filter_str
        )

        if path:
            data = self.get_state()
            # DTO 생성
            script_data = MacroScriptData(file_path=path, data=data)
            self.script_save_requested.emit(script_data)

    def on_load_clicked(self) -> None:
        """
        로드 버튼 클릭 핸들러

        Logic:
            1. 파일 열기 다이얼로그 표시
            2. 사용자가 경로 선택 시 Presenter에 로드 요청 시그널(경로) 전달
        """
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self,
            language_manager.get_text("macro_panel_dialog_title_open"),
            "",
            filter_str
        )

        if path:
            self.script_load_requested.emit(path)

    def show_error(self, title: str, message: str) -> None:
        """
        에러 메시지 박스 표시 (Presenter에서 호출)

        Args:
            title (str): 메시지 박스 제목
            message (str): 에러 내용
        """
        QMessageBox.critical(self, title, message)

    def show_info(self, title: str, message: str) -> None:
        """
        정보 메시지 박스 표시 (Presenter에서 호출)

        Args:
            title (str): 메시지 박스 제목
            message (str): 정보 내용
        """
        QMessageBox.information(self, title, message)

    def on_repeat_start_requested(self, option: MacroRepeatOption) -> None:
        """
        Repeat Start 버튼 클릭 핸들러 (Widget -> Panel)

        Logic:
            - MacroList에서 선택된 항목의 인덱스를 가져옴
            - 선택된 항목이 있다면 ExecutionRequest DTO를 생성하여 Presenter로 전달
            - UI 상태를 '실행 중(반복 모드)'으로 변경
            - 선택된 항목이 없으면 경고 메시지 표시

        Args:
            option (MacroRepeatOption): 매크로 반복 옵션 DTO.
        """
        indices = self._macro_list.get_selected_indices()
        if indices:
            # 선택된 인덱스와 옵션 DTO를 함께 전달
            request = MacroExecutionRequest(indices=indices, option=option)
            self.repeat_start_requested.emit(request)

            # 즉시 실행 상태로 전환 (Presenter 응답 전 시각적 피드백)
            # is_repeat=True를 전달하여 Stop/Pause 버튼 활성화
            self._macro_control.set_running_state(True, is_repeat=True)
        else:
            # 선택된 항목이 없으면 경고 메시지 표시
            QMessageBox.warning(
                self,
                "No Commands Selected",
                "Please select at least one command to run."
            )

    def on_repeat_stop_requested(self) -> None:
        """
        Repeat Stop 버튼 클릭 핸들러
        """
        self.repeat_stop_requested.emit()

    # -------------------------------------------------------------------------
    # State Persistence
    # -------------------------------------------------------------------------
    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        외부에서 전달받은 상태 딕셔너리를 UI에 적용합니다. (복원)

        Args:
            state (Dict[str, Any]): 저장된 패널 상태 데이터.
        """
        self._loading = True
        try:
            # 커맨드 리스트 로드
            commands = state.get("commands", [])
            if commands:
                self._macro_list.apply_state(commands)

            # 컨트롤 설정 로드
            control_state = state.get("control_state", {})
            if control_state:
                self._macro_control.apply_state(control_state)
        finally:
            self._loading = False

    def get_state(self) -> Dict[str, Any]:
        """
        현재 패널의 상태를 딕셔너리로 반환합니다. (저장)

        Returns:
            Dict[str, Any]: 현재 패널 상태 데이터.
        """
        return {
            "commands": self._macro_list.get_state(),
            "control_state": self._macro_control.get_state()
        }