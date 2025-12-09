from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSignal
import commentjson
from typing import Optional

from view.widgets.command_list import CommandListWidget
from view.widgets.command_control import CommandControlWidget
from view.language_manager import language_manager

class CommandListPanel(QWidget):
    """
    CommandListWidget과 CommandControlWidget을 조합하여
    커맨드 리스트 관리 및 실행 기능을 제공하는 패널 클래스입니다.
    """

    run_requested = pyqtSignal(list) # indices
    stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        CommandListPanel을 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.settings = None
        self.cmd_ctrl = None
        self.cmd_list = None
        self._loading = False
        self.init_ui()

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.cmd_list = CommandListWidget()
        self.cmd_ctrl = CommandControlWidget()

        # 설정 관리자 (Settings Manager)
        from core.settings_manager import SettingsManager
        self.settings = SettingsManager()

        # 시그널 연결
        self.cmd_ctrl.cmd_run_once_requested.connect(self.on_run_once_requested)
        self.cmd_ctrl.cmd_stop_run_requested.connect(self.stop_requested.emit)
        self.cmd_ctrl.cmd_repeat_start_requested.connect(self.on_repeat_start_requested)
        self.cmd_ctrl.cmd_repeat_stop_requested.connect(self.stop_requested.emit) # Stop signal is same for now

        self.cmd_ctrl.script_save_requested.connect(self.save_script_to_file)
        self.cmd_ctrl.script_load_requested.connect(self.load_script_from_file)

        # 데이터 변경 시 자동 저장
        self.cmd_list.cmd_list_changed.connect(self.save_state)

        # CommandControl의 입력 필드 변경 시에도 저장 (textChanged, valueChanged 등)
        self.cmd_ctrl.repeat_delay_input.textChanged.connect(self.save_state)
        self.cmd_ctrl.repeat_count_spin.valueChanged.connect(self.save_state)

        layout.addWidget(self.cmd_list)
        layout.addWidget(self.cmd_ctrl)

        self.setLayout(layout)

        # 초기 데이터 로드 (위젯 생성 후)
        self.load_state()

    def load_state(self) -> None:
        """설정에서 상태를 로드합니다."""
        self._loading = True
        try:
            # 커맨드 리스트 로드
            commands = self.settings.get("cmd_list.commands", [])
            if commands:
                self.cmd_list.load_state(commands)

            # 컨트롤 설정 로드
            control_state = self.settings.get("cmd_list.control_state", {})
            if control_state:
                self.cmd_ctrl.load_state(control_state)
        finally:
            self._loading = False

    def save_state(self) -> None:
        """현재 상태를 설정에 저장합니다."""
        if self._loading:
            return

        # 커맨드 리스트 저장
        commands = self.cmd_list.save_state()
        self.settings.set("cmd_list.commands", commands)

        # 컨트롤 설정 저장
        control_state = self.cmd_ctrl.save_state()
        self.settings.set("cmd_list.control_state", control_state)

        self.settings.save_settings()

    def on_run_once_requested(self) -> None:
        """Run(Single) 버튼 클릭 핸들러입니다."""
        indices = self.cmd_list.get_selected_indices()
        if indices:
            self.run_requested.emit(indices)
            self.cmd_ctrl.set_running_state(True, is_auto=False)

    def on_repeat_start_requested(self, delay: int, max_runs: int) -> None:
        """
        Auto Run 버튼 클릭 핸들러입니다.

        Args:
            delay (int): 실행 간 지연 시간(ms).
            max_runs (int): 최대 실행 횟수.
        """
        indices = self.cmd_list.get_selected_indices()
        if indices:
            # TODO: 자동 실행 파라미터를 시그널이나 별도 메서드로 전달해야 함
            self.run_requested.emit(indices)
            self.cmd_ctrl.set_running_state(True, is_auto=True)

    def set_running_state(self, running: bool) -> None:
        """
        실행 상태를 전파합니다.

        Args:
            running (bool): 실행 중 여부.
        """
        # TODO: UI를 올바르게 업데이트하려면 자동 실행 여부를 알아야 함
        # 현재는 단순히 비실행 상태로 초기화
        self.cmd_ctrl.set_running_state(running)

    def save_script_to_file(self) -> None:
        """현재 커맨드 리스트와 설정을 파일로 저장합니다."""
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getSaveFileName(self, language_manager.get_text("cmd_list_dialog_title_save"), "", filter_str)

        if not path:
            return

        data = {
            "commands": self.cmd_list.save_state(),
            "control_state": self.cmd_ctrl.save_state()
        }

        try:
            with open(path, 'w', encoding='utf-8') as f:
                commentjson.dump(data, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save script: {str(e)}")

    def load_script_from_file(self) -> None:
        """파일에서 커맨드 리스트와 설정을 로드합니다."""
        filter_str = "JSON Files (*.json);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, language_manager.get_text("cmd_list_dialog_title_open"), "", filter_str)

        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = commentjson.load(f)

            if "commands" in data:
                self.cmd_list.load_state(data["commands"])

            if "control_state" in data:
                self.cmd_ctrl.load_state(data["control_state"])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load script: {str(e)}")
