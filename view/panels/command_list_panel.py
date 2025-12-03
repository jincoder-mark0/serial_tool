from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional, List

from view.widgets.command_list import CommandListWidget
from view.widgets.command_control import CommandControlWidget

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
        self.init_ui()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.command_list = CommandListWidget()
        self.command_control = CommandControlWidget()
        
        # 설정 관리자 (Settings Manager)
        from core.settings_manager import SettingsManager
        self.settings = SettingsManager()
        
        # 시그널 연결
        self.command_control.run_single_requested.connect(self.on_run_single_requested)
        self.command_control.stop_requested.connect(self.stop_requested.emit)
        self.command_control.start_auto_requested.connect(self.on_start_auto_requested)
        self.command_control.stop_auto_requested.connect(self.stop_requested.emit) # Stop signal is same for now
        
        # 데이터 변경 시 자동 저장
        self.command_list.command_list_changed.connect(self.save_state)
        
        # CommandControl의 입력 필드 변경 시에도 저장 (textChanged, valueChanged 등)
        self.command_control.prefix_input.textChanged.connect(self.save_state)
        self.command_control.suffix_input.textChanged.connect(self.save_state)
        self.command_control.global_delay_input.textChanged.connect(self.save_state)
        self.command_control.auto_run_max_spin.valueChanged.connect(self.save_state)
        
        layout.addWidget(self.command_list)
        layout.addWidget(self.command_control)
        
        self.setLayout(layout)
        
        # 초기 데이터 로드 (위젯 생성 후)
        self.load_state()
        
    def load_state(self) -> None:
        """설정에서 상태를 로드합니다."""
        # 커맨드 리스트 로드
        commands = self.settings.get("command_list.commands", [])
        if commands:
            self.command_list.load_state(commands)
            
        # 컨트롤 설정 로드
        control_state = self.settings.get("command_list.control_state", {})
        if control_state:
            self.command_control.load_state(control_state)
            
    def save_state(self) -> None:
        """현재 상태를 설정에 저장합니다."""
        # 커맨드 리스트 저장
        commands = self.command_list.save_state()
        self.settings.set("command_list.commands", commands)
        
        # 컨트롤 설정 저장
        control_state = self.command_control.save_state()
        self.settings.set("command_list.control_state", control_state)
        
        self.settings.save_settings()
        
    def on_run_single_requested(self) -> None:
        """Run(Single) 버튼 클릭 핸들러입니다."""
        indices = self.command_list.get_selected_indices()
        if indices:
            self.run_requested.emit(indices)
            self.command_control.set_running_state(True, is_auto=False)
            
    def on_start_auto_requested(self, delay: int, max_runs: int) -> None:
        """
        Auto Run 버튼 클릭 핸들러입니다.
        
        Args:
            delay (int): 실행 간 지연 시간(ms).
            max_runs (int): 최대 실행 횟수.
        """
        indices = self.command_list.get_selected_indices()
        if indices:
            # TODO: 자동 실행 파라미터를 시그널이나 별도 메서드로 전달해야 함
            self.run_requested.emit(indices) 
            self.command_control.set_running_state(True, is_auto=True)
            
    def set_running_state(self, running: bool) -> None:
        """
        실행 상태를 전파합니다.
        
        Args:
            running (bool): 실행 중 여부.
        """
        # TODO: UI를 올바르게 업데이트하려면 자동 실행 여부를 알아야 함
        # 현재는 단순히 비실행 상태로 초기화
        self.command_control.set_running_state(running)
