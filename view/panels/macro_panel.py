from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
import commentjson
from typing import Optional, Dict, Any

from view.widgets.macro_list import MacroListWidget
from view.widgets.macro_ctrl import MacroCtrlWidget
from view.managers.lang_manager import lang_manager
from core.logger import logger

class MacroPanel(QWidget):
    """
    MacroListWidget과 MacroCtrlWidget을 조합하여
    커맨드 리스트 관리 및 실행 기능을 제공하는 패널 클래스입니다.
    """

    repeat_start_requested = pyqtSignal(list)  # indices
    repeat_stop_requested = pyqtSignal()
    state_changed = pyqtSignal()  # 데이터 변경 알림 시그널

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        MacroPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.marco_ctrl = None
        self.macro_list = None
        self._loading = False
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.macro_list = MacroListWidget()
        self.marco_ctrl = MacroCtrlWidget()

        # 시그널 연결
        self.marco_ctrl.macro_repeat_start_requested.connect(self.on_repeat_start_requested)
        self.marco_ctrl.macro_repeat_stop_requested.connect(self.on_repeat_stop_requested)

        self.marco_ctrl.script_save_requested.connect(self.save_script_to_file)
        self.marco_ctrl.script_load_requested.connect(self.load_script_from_file)

        # 데이터 변경 시 상위(Presenter/MainWindow)에 알림
        self.macro_list.macro_list_changed.connect(self.state_changed.emit)
        # 필요한 경우 Control 위젯의 변경 사항도 연결 가능

        layout.addWidget(self.macro_list)
        layout.addWidget(self.marco_ctrl)

        self.setLayout(layout)

        # 초기 데이터 로드 (위젯 생성 후)
        # self.load_state()

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
                self.marco_ctrl.load_state(control_state)
        finally:
            self._loading = False

    def save_state(self) -> Dict[str, Any]:
        """
        현재 패널의 상태를 딕셔너리로 반환합니다.
        파일에 직접 저장하지 않습니다.

        Returns:
            Dict[str, Any]: 현재 패널 상태 데이터.
        """
        return {
            "commands": self.macro_list.save_state(),
            "control_state": self.marco_ctrl.save_state()
        }

    def on_repeat_start_requested(self, delay: int, max_runs: int) -> None:
        """
        Repeat Start 버튼 클릭 핸들러입니다.

        Args:
            delay (int): 실행 간 지연 시간(ms).
            max_runs (int): 최대 실행 횟수.
        """
        indices = self.macro_list.get_selected_indices()
        if indices:
            # Note: delay와 max_runs 파라미터는 현재 시그널에 포함되지 않음
            # Presenter에서 MacroCtrlWidget의 상태를 직접 읽어서 사용해야 함
            self.repeat_start_requested.emit(indices)
            self.marco_ctrl.set_running_state(True, is_auto=True)

    def on_repeat_stop_requested(self) -> None:
        """
        Repeat Stop 버튼 클릭 핸들러입니다.
        """
        self.repeat_stop_requested.emit()

    def set_running_state(self, running: bool) -> None:
        """
        실행 상태를 UI에 반영합니다.

        Args:
            running (bool): 실행 중 여부.
        """
        # Note: 현재는 단순히 running 상태만 전달
        # 향후 is_repeat 파라미터를 추가하여 Repeat/Pause 버튼 상태를 구분할 수 있음
        self.marco_ctrl.set_running_state(running)

    def save_script_to_file(self) -> None:
        """현재 커맨드 리스트와 설정을 JSON 파일로 내보냅니다."""
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getSaveFileName(
            self,
            lang_manager.get_text("macro_list_dialog_title_save"),
            "",
            filter_str
        )

        if not path:
            return

        data = self.save_state()

        try:
            with open(path, 'w', encoding='utf-8') as f:
                commentjson.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save script: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save script: {str(e)}")

    def load_script_from_file(self) -> None:
        """JSON 파일에서 커맨드 리스트와 설정을 불러옵니다."""
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang_manager.get_text("macro_list_dialog_title_open"),
            "",
            filter_str
        )

        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = commentjson.load(f)

            # 파일에서 로드한 데이터를 UI에 적용
            self.load_state(data)

        except Exception as e:
            logger.error(f"Failed to load script: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load script: {str(e)}")
