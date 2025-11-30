from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, 
    QLabel, QLineEdit, QSpinBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional

class CommandControlWidget(QWidget):
    """
    Command List 실행을 제어하는 위젯입니다.
    Run, Stop, Auto Run, Script Load/Save 기능을 제공합니다.
    """
    
    # Signals
    run_single_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    start_auto_requested = pyqtSignal(int, int) # delay_ms, max_runs
    stop_auto_requested = pyqtSignal()
    
    save_script_requested = pyqtSignal()
    load_script_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 1. Top Row: Script Controls
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_script_btn = QPushButton("Save")
        self.save_script_btn.setToolTip("Save current command list to JSON")
        self.save_script_btn.clicked.connect(self.save_script_requested.emit)
        
        self.load_script_btn = QPushButton("Load")
        self.load_script_btn.setToolTip("Load command list from JSON")
        self.load_script_btn.clicked.connect(self.load_script_requested.emit)
        
        # Prefix / Suffix Inputs
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Prefix")
        self.prefix_input.setFixedWidth(60)
        self.prefix_input.setToolTip("Global command prefix")
        
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("Suffix")
        self.suffix_input.setFixedWidth(60)
        self.suffix_input.setToolTip("Global command suffix")
        
        top_layout.addWidget(QLabel("Pre:"))
        top_layout.addWidget(self.prefix_input)
        top_layout.addWidget(QLabel("Suf:"))
        top_layout.addWidget(self.suffix_input)
        top_layout.addStretch()
        top_layout.addWidget(self.save_script_btn)
        top_layout.addWidget(self.load_script_btn)
        
        # 2. Auto Run Settings Group
        auto_group = QGroupBox("Execution Control")
        auto_layout = QGridLayout()
        auto_layout.setContentsMargins(2, 2, 2, 2)
        auto_layout.setSpacing(5)
        
        # Row 0: Single Run & Stop
        self.run_btn = QPushButton("Run Once (F5)")
        self.run_btn.setToolTip("Execute selected commands once")
        self.run_btn.clicked.connect(self.run_single_requested.emit)
        
        self.stop_btn = QPushButton("Stop (Esc)")
        self.stop_btn.setToolTip("Stop execution")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "danger") # Red style
        
        auto_layout.addWidget(self.run_btn, 0, 0, 1, 2)
        auto_layout.addWidget(self.stop_btn, 0, 2, 1, 2)
        
        # Row 1: Auto Run Settings
        auto_layout.addWidget(QLabel("Delay(ms):"), 1, 0)
        self.global_delay_input = QLineEdit("1000")
        self.global_delay_input.setFixedWidth(50)
        self.global_delay_input.setAlignment(Qt.AlignRight)
        auto_layout.addWidget(self.global_delay_input, 1, 1)
        
        auto_layout.addWidget(QLabel("Max Runs:"), 1, 2)
        self.auto_run_max_spin = QSpinBox()
        self.auto_run_max_spin.setRange(0, 9999)
        self.auto_run_max_spin.setValue(0)
        self.auto_run_max_spin.setToolTip("0 for infinite")
        auto_layout.addWidget(self.auto_run_max_spin, 1, 3)
        
        # Row 2: Auto Run Controls
        self.auto_run_btn = QPushButton("Start Auto Run")
        self.auto_run_btn.setProperty("class", "accent") # Green style
        self.auto_run_btn.clicked.connect(self.on_start_auto)
        
        self.stop_auto_btn = QPushButton("Stop Auto")
        self.stop_auto_btn.clicked.connect(self.stop_auto_requested.emit)
        self.stop_auto_btn.setEnabled(False)
        
        self.auto_run_count_label = QLabel("0 / ∞")
        self.auto_run_count_label.setAlignment(Qt.AlignCenter)
        
        auto_layout.addWidget(self.auto_run_btn, 2, 0, 1, 2)
        auto_layout.addWidget(self.stop_auto_btn, 2, 2)
        auto_layout.addWidget(self.auto_run_count_label, 2, 3)
        
        auto_group.setLayout(auto_layout)
        
        layout.addLayout(top_layout)
        layout.addWidget(auto_group)
        
        self.setLayout(layout)
        
        # Initial State: Disabled until connected
        self.set_controls_enabled(False)
        
    def on_start_auto(self) -> None:
        try:
            delay = int(self.global_delay_input.text())
        except ValueError:
            delay = 1000
        max_runs = self.auto_run_max_spin.value()
        self.start_auto_requested.emit(delay, max_runs)
        
    def set_running_state(self, running: bool, is_auto: bool = False) -> None:
        """실행 상태에 따라 버튼 활성화/비활성화"""
        if running:
            self.run_btn.setEnabled(False)
            self.auto_run_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            if is_auto:
                self.stop_auto_btn.setEnabled(True)
        else:
            self.run_btn.setEnabled(True)
            self.auto_run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.stop_auto_btn.setEnabled(False)

    def update_auto_count(self, current: int, total: int) -> None:
        total_str = "∞" if total == 0 else str(total)
        self.auto_run_count_label.setText(f"{current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """포트 연결 상태에 따라 제어 버튼 활성화/비활성화"""
        self.run_btn.setEnabled(enabled)
        self.auto_run_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(False) # Stop은 실행 중에만 활성화
        self.stop_auto_btn.setEnabled(False)
        
        self.save_script_btn.setEnabled(True)
        self.load_script_btn.setEnabled(True)
