from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal
from typing import Optional, List

from view.widgets.command_list import CommandListWidget
from view.widgets.command_control import CommandControlWidget

class CommandListPanel(QWidget):
    """
    CommandListWidget과 CommandControlWidget을 조합하여
    커맨드 리스트 관리 및 실행 기능을 제공하는 패널입니다.
    """
    
    run_requested = pyqtSignal(list) # indices
    stop_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.command_list = CommandListWidget()
        self.command_control = CommandControlWidget()
        
        # Connect signals
        self.command_control.run_single_requested.connect(self.on_run_single_requested)
        self.command_control.stop_requested.connect(self.stop_requested.emit)
        self.command_control.start_auto_requested.connect(self.on_start_auto_requested)
        self.command_control.stop_auto_requested.connect(self.stop_requested.emit) # Stop signal is same for now
        
        layout.addWidget(self.command_list)
        layout.addWidget(self.command_control)
        
        self.setLayout(layout)
        
    def on_run_single_requested(self) -> None:
        """Run(Single) 버튼 클릭 시"""
        indices = self.command_list.get_selected_indices()
        if indices:
            self.run_requested.emit(indices)
            self.command_control.set_running_state(True, is_auto=False)
            
    def on_start_auto_requested(self, delay: int, max_runs: int) -> None:
        """Auto Run 버튼 클릭 시"""
        indices = self.command_list.get_selected_indices()
        if indices:
            # TODO: Pass auto run params via signal or separate method
            self.run_requested.emit(indices) 
            self.command_control.set_running_state(True, is_auto=True)
            
    def set_running_state(self, running: bool) -> None:
        """실행 상태 전파"""
        # TODO: Need to know if it was auto run or not to update UI correctly
        # For now, just reset to non-running state
        self.command_control.set_running_state(running)
