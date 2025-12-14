"""
매크로 패널 모듈

MacroListWidget과 MacroControlWidget을 조합하여
커맨드 리스트 관리 및 실행 기능을 제공하는 패널 클래스입니다.

## WHY
* 매크로 리스트 관리와 실행 제어 UI를 하나의 패널로 통합
* View 계층으로서 사용자 입력을 시그널로 변환하여 Presenter에 전달
* MVP 패턴 준수를 위해 비즈니스 로직(파일 I/O 등) 제거

## WHAT
* 매크로 리스트 및 제어 위젯 레이아웃 구성
* 사용자 액션(저장/로드/실행)에 대한 시그널 정의
* Presenter로부터 요청받은 상태 업데이트 및 메시지 표시

## HOW
* QVBoxLayout으로 상/하위 위젯 배치
* PyQt 시그널을 통해 Presenter와 통신
* save_state/load_state로 데이터 직렬화 지원
* DTO를 사용하여 데이터 전송
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
from typing import Optional, Dict, Any

from view.widgets.macro_list import MacroListWidget
from view.widgets.macro_control import MacroControlWidget
from view.managers.language_manager import language_manager
from common.dtos import MacroScriptData, MacroRepeatOption

class MacroPanel(QWidget):
    """
    매크로 관리 및 실행 패널 클래스

    MVP 패턴에 따라 UI 로직만 처리하며,
    파일 저장/로드 등의 비즈니스 로직은 시그널을 통해 Presenter로 위임합니다.
    """

    # 매크로 실행 제어 시그널
    repeat_start_requested = pyqtSignal(list, object)  # indices, MacroRepeatOption DTO
    repeat_stop_requested = pyqtSignal()
    state_changed = pyqtSignal()  # 데이터 변경 알림

    # 파일 저장/로드 요청 시그널 (DTO 사용)
    script_save_requested = pyqtSignal(object) # MacroScriptData
    script_load_requested = pyqtSignal(str)    # filepath

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroPanel 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯.
        """
        super().__init__(parent)
        self.marco_control = None
        self.macro_list = None
        self._loading = False
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.macro_list = MacroListWidget()
        self.marco_control = MacroControlWidget()

        # 제어 위젯 시그널 연결
        self.marco_control.macro_repeat_start_requested.connect(self.on_repeat_start_requested)
        self.marco_control.macro_repeat_stop_requested.connect(self.on_repeat_stop_requested)

        # 저장/로드 버튼 클릭 시 파일 다이얼로그 호출 핸들러 연결
        self.marco_control.script_save_requested.connect(self.on_save_clicked)
        self.marco_control.script_load_requested.connect(self.on_load_clicked)

        # 데이터 변경 알림 연결
        self.macro_list.macro_list_changed.connect(self.state_changed.emit)

        layout.addWidget(self.macro_list)
        layout.addWidget(self.marco_control)

        self.setLayout(layout)

    def on_save_clicked(self) -> None:
        """
        저장 버튼 클릭 핸들러

        Logic:
            1. 파일 저장 다이얼로그 표시
            2. 사용자가 경로 선택 시 현재 상태(save_state) 수집
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
            data = self.save_state()
            # DTO 생성
            script_data = MacroScriptData(filepath=path, data=data)
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

    def load_state(self, state: Dict[str, Any]) -> None:
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
                self.macro_list.load_state(commands)

            # 컨트롤 설정 로드
            control_state = state.get("control_state", {})
            if control_state:
                self.marco_control.load_state(control_state)
        finally:
            self._loading = False

    def save_state(self) -> Dict[str, Any]:
        """
        현재 패널의 상태를 딕셔너리로 반환합니다.

        Returns:
            Dict[str, Any]: 현재 패널 상태 데이터.
        """
        return {
            "commands": self.macro_list.save_state(),
            "control_state": self.marco_control.save_state()
        }

    def on_repeat_start_requested(self, option: MacroRepeatOption) -> None:
        """
        Repeat Start 버튼 클릭 핸들러 (Widget -> Panel)

        Args:
            option (MacroRepeatOption): 매크로 반복 옵션 DTO
        """
        indices = self.macro_list.get_selected_indices()
        if indices:
            # 선택된 인덱스와 옵션 DTO를 함께 전달
            self.repeat_start_requested.emit(indices, option)
            self.marco_control.set_running_state(True, is_repeat=True)

    def on_repeat_stop_requested(self) -> None:
        """
        Repeat Stop 버튼 클릭 핸들러
        """
        self.repeat_stop_requested.emit()

    def set_running_state(self, running: bool) -> None:
        """
        실행 상태를 UI에 반영합니다.

        Args:
            running (bool): 실행 중 여부
        """
        # [Note] 현재는 단순히 running 상태만 전달
        # 향후 is_repeat 파라미터를 추가하여 Repeat/Pause 버튼 상태를 구분할 수 있음
        self.marco_control.set_running_state(running)
