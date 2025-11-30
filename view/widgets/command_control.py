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
    select_all_toggled = pyqtSignal(bool)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 1. Top Row: Select All, Script Controls
        top_layout = QHBoxLayout()
        
        self.select_all_check = QCheckBox("Select All")
        self.select_all_check.setToolTip("Select/Deselect all steps")
        self.select_all_check.toggled.connect(self.select_all_toggled.emit)
        
        self.save_script_btn = QPushButton("Save Script")
        self.save_script_btn.setToolTip("Save current command list to JSON")
        self.save_script_btn.clicked.connect(self.save_script_requested.emit)
        
        self.load_script_btn = QPushButton("Load Script")
        self.load_script_btn.setToolTip("Load command list from JSON")
        self.load_script_btn.clicked.connect(self.load_script_requested.emit)
        
        top_layout.addWidget(self.select_all_check)
        top_layout.addStretch()
        top_layout.addWidget(self.save_script_btn)
        top_layout.addWidget(self.load_script_btn)
        
        # 2. Auto Run Settings Group
        auto_group = QGroupBox("Execution Control")
        auto_layout = QGridLayout()
        auto_layout.setContentsMargins(5, 5, 5, 5)
        
        # Row 0: Single Run
        self.run_btn = QPushButton("Run Selected (Once)")
        self.run_btn.setToolTip("Execute selected commands once (F5)")
        self.run_btn.setStyleSheet("font-weight: bold;")
        self.run_btn.clicked.connect(self.run_single_requested.emit)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setToolTip("Stop execution (Esc)")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setEnabled(False)
        
        auto_layout.addWidget(self.run_btn, 0, 0, 1, 2)
        auto_layout.addWidget(self.stop_btn, 0, 2, 1, 2)
        
        # Row 1: Auto Run Settings
        auto_layout.addWidget(QLabel("Global Delay (ms):"), 1, 0)
        self.global_delay_input = QLineEdit("1000")
        self.global_delay_input.setFixedWidth(60)
        self.global_delay_input.setAlignment(Qt.AlignRight)
        self.global_delay_input.setToolTip("Delay between cycles in Auto Run")
        auto_layout.addWidget(self.global_delay_input, 1, 1)
        
        auto_layout.addWidget(QLabel("Max Runs (0=∞):"), 1, 2)
        self.auto_run_max_spin = QSpinBox()
        self.auto_run_max_spin.setRange(0, 9999)
        self.auto_run_max_spin.setValue(0)
        self.auto_run_max_spin.setToolTip("Maximum number of cycles (0 for infinite)")
        auto_layout.addWidget(self.auto_run_max_spin, 1, 3)
        
        # Row 2: Auto Run Controls & Status
        self.auto_run_btn = QPushButton("Start Auto Run")
        self.auto_run_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.auto_run_btn.clicked.connect(self.on_start_auto)
        
        self.stop_auto_btn = QPushButton("Stop Auto")
        self.stop_auto_btn.clicked.connect(self.stop_auto_requested.emit)
        self.stop_auto_btn.setEnabled(False)
        
        self.auto_run_count_label = QLabel("Count: 0 / ∞")
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
        self.auto_run_count_label.setText(f"Count: {current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """포트 연결 상태에 따라 제어 버튼 활성화/비활성화"""
        self.run_btn.setEnabled(enabled)
        self.auto_run_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(False) # Stop은 실행 중에만 활성화
        self.stop_auto_btn.setEnabled(False)
        
        # Script Save/Load는 항상 활성화 (요청사항)
        self.save_script_btn.setEnabled(True)
        self.load_script_btn.setEnabled(True)
