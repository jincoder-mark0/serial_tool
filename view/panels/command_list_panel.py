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
        
        # 시그널 연결
        self.command_control.run_single_requested.connect(self.on_run_single_requested)
        self.command_control.stop_requested.connect(self.stop_requested.emit)
        self.command_control.start_auto_requested.connect(self.on_start_auto_requested)
        self.command_control.stop_auto_requested.connect(self.stop_requested.emit) # Stop signal is same for now
        
        layout.addWidget(self.command_list)
        layout.addWidget(self.command_control)
        
        self.setLayout(layout)
        
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
