"""
매크로 패널 모듈

매크로 리스트(List)와 제어(Control) 위젯을 통합하여 관리합니다.

## WHY
* 매크로 관련 기능을 하나의 패널로 그룹화
* 하위 위젯 간의 레이아웃 관리 및 시그널 중계
* Presenter에 단일화된 뷰 인터페이스 제공

## WHAT
* MacroListWidget과 MacroControlWidget 배치
* 파일 저장/로드 및 실행 제어(시작/정지/일시정지) 시그널 정의
* 상태 저장/복원 인터페이스
* 하위 위젯의 브로드캐스트 상태 변경 알림 중계

## HOW
* QVBoxLayout 사용
* 하위 위젯의 이벤트를 상위로 전달(Bubbling)하거나 직접 처리
* DTO를 사용하여 데이터 구조화
"""
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal

from view.widgets.macro_list import MacroListWidget
from view.widgets.macro_control import MacroControlWidget
from view.managers.language_manager import language_manager
from common.dtos import MacroScriptData, MacroRepeatOption, MacroExecutionRequest

class MacroPanel(QWidget):
    """
    매크로 관리 및 실행 패널 클래스

    MVP 패턴에 따라 UI 로직만 처리하며,
    파일 저장/로드 등의 비즈니스 로직은 시그널을 통해 Presenter로 위임합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 매크로 실행 제어 시그널
    repeat_start_requested = pyqtSignal(object)  # MacroExecutionRequest DTO
    repeat_stop_requested = pyqtSignal()
    repeat_pause_requested = pyqtSignal()

    state_changed = pyqtSignal()  # 데이터 변경 알림

    # 파일 저장/로드 요청 시그널 (DTO 사용)
    script_save_requested = pyqtSignal(object) # MacroScriptData
    script_load_requested = pyqtSignal(str)    # file_path

    # 브로드캐스트 상태 변경 시그널 (MainPresenter의 전송 버튼 활성화 로직용)
    broadcast_changed = pyqtSignal(bool)
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)
        self.macro_control: Optional[MacroControlWidget] = None
        self.macro_list: Optional[MacroListWidget] = None
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
        self.macro_list = MacroListWidget()
        self.macro_control = MacroControlWidget()

        # ---------------------------------------------------------------------
        # Signal Connections (Widget -> Panel)
        # ---------------------------------------------------------------------
        # 제어 위젯 시그널 연결 (Control Widget -> Panel Signal -> Presenter)
        self.macro_control.macro_repeat_start_requested.connect(self.on_repeat_start_requested)
        self.macro_control.macro_repeat_stop_requested.connect(self.on_repeat_stop_requested)

        # 일시정지 시그널 연결 (직접 중계)
        self.macro_control.macro_repeat_pause_requested.connect(self.repeat_pause_requested.emit)

        # 저장/로드 버튼 클릭 시 파일 다이얼로그 호출 핸들러 연결
        self.macro_control.script_save_requested.connect(self.on_save_clicked)
        self.macro_control.script_load_requested.connect(self.on_load_clicked)

        # 데이터 변경 알림 연결
        self.macro_list.macro_list_changed.connect(self.state_changed.emit)

        # 브로드캐스트 상태 변경 중계
        self.macro_control.broadcast_changed.connect(self.broadcast_changed.emit)
        
        # 레이아웃을 초기화
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.macro_list)
        layout.addWidget(self.macro_control)

        self.setLayout(layout)

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

    def apply_state(self, state: Dict[str, Any]) -> None:
        """
        외부에서 전달받은 상태 딕셔너리를 UI에 적용합니다.

        Args:
            state (Dict[str, Any]): 저장된 패널 상태 데이터.
        """
        self._loading = True
        try:
            # 커맨드 리스트 로드
            commands = state.get("commands", [])
            if commands:
                self.macro_list.apply_state(commands)

            # 컨트롤 설정 로드
            control_state = state.get("control_state", {})
            if control_state:
                self.macro_control.apply_state(control_state)
        finally:
            self._loading = False

    def get_state(self) -> Dict[str, Any]:
        """
        현재 패널의 상태를 딕셔너리로 반환합니다.

        Returns:
            Dict[str, Any]: 현재 패널 상태 데이터.
        """
        return {
            "commands": self.macro_list.get_state(),
            "control_state": self.macro_control.get_state()
        }

    def on_repeat_start_requested(self, option: MacroRepeatOption) -> None:
        """
        Repeat Start 버튼 클릭 핸들러 (Widget -> Panel)

        Logic:
            - MacroList에서 선택된 항목의 인덱스를 가져옴
            - 선택된 항목이 있다면 ExecutionRequest DTO를 생성하여 Presenter로 전달
            - UI 상태를 '실행 중(반복 모드)'으로 변경
            - 선택된 항목이 없다면 사용자에게 경고 메시지 표시

        Args:
            option (MacroRepeatOption): 매크로 반복 옵션 DTO
        """
        indices = self.macro_list.get_selected_indices()
        if indices:
            # 선택된 인덱스와 옵션 DTO를 함께 전달
            request = MacroExecutionRequest(indices=indices, option=option)
            self.repeat_start_requested.emit(request)

            # 즉시 실행 상태로 전환 (Presenter 응답 전 시각적 피드백)
            # is_repeat=True를 전달하여 Stop/Pause 버튼 활성화
            self.macro_control.set_running_state(True, is_repeat=True)
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

    def set_running_state(self, running: bool, is_repeat: bool = False) -> None:
        """
        실행 상태를 UI에 반영합니다.

        Args:
            running (bool): 실행 중 여부.
            is_repeat (bool): 반복 모드인지 여부 (단일 실행과 구분).
                              True일 경우 Stop/Pause 버튼을 활성화합니다.
        """
        self.macro_control.set_running_state(running, is_repeat)