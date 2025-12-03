from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QCheckBox, 
    QLabel, QLineEdit, QSpinBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import pyqtSignal, Qt
from typing import Optional
from view.language_manager import language_manager

class CommandControlWidget(QWidget):
    """
    Command List 실행을 제어하는 위젯 클래스입니다.
    실행(Run), 정지(Stop), 자동 실행(Auto Run), 스크립트 저장/로드 기능을 제공합니다.
    """
    
    # 시그널 정의
    run_single_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    start_auto_requested = pyqtSignal(int, int) # delay_ms, max_runs
    stop_auto_requested = pyqtSignal()
    
    save_script_requested = pyqtSignal()
    load_script_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        CommandControlWidget을 초기화합니다.
        
        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.init_ui()
        
        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 1. 상단 행: 스크립트 제어 및 접두사/접미사 (Top Row)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_script_btn = QPushButton(language_manager.get_text("save_script"))
        self.save_script_btn.setToolTip(language_manager.get_text("save_script_tooltip"))
        self.save_script_btn.clicked.connect(self.save_script_requested.emit)
        
        self.load_script_btn = QPushButton(language_manager.get_text("load_script"))
        self.load_script_btn.setToolTip(language_manager.get_text("load_script_tooltip"))
        self.load_script_btn.clicked.connect(self.load_script_requested.emit)
        
        # 접두사 / 접미사 입력 (Prefix / Suffix Inputs)
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Prefix")
        self.prefix_input.setFixedWidth(60)
        self.prefix_input.setToolTip(language_manager.get_text("prefix_tooltip"))
        self.prefix_input.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("Suffix")
        self.suffix_input.setFixedWidth(60)
        self.suffix_input.setToolTip(language_manager.get_text("suffix_tooltip"))
        self.suffix_input.setProperty("class", "fixed-font")  # 고정폭 폰트 적용
        
        self.prefix_label = QLabel(language_manager.get_text("prefix_label"))
        self.suffix_label = QLabel(language_manager.get_text("suffix_label"))
        
        top_layout.addWidget(self.prefix_label)
        top_layout.addWidget(self.prefix_input)
        top_layout.addWidget(self.suffix_label)
        top_layout.addWidget(self.suffix_input)
        top_layout.addStretch()
        top_layout.addWidget(self.save_script_btn)
        top_layout.addWidget(self.load_script_btn)
        
        # 2. 자동 실행 설정 그룹 (Auto Run Settings Group)
        self.auto_group = QGroupBox(language_manager.get_text("execution_control"))
        auto_layout = QGridLayout()
        auto_layout.setContentsMargins(2, 2, 2, 2)
        auto_layout.setSpacing(5)
        
        # Row 0: 단일 실행 및 정지
        self.run_btn = QPushButton(language_manager.get_text("run_once"))
        self.run_btn.setToolTip(language_manager.get_text("run_once_tooltip"))
        self.run_btn.clicked.connect(self.run_single_requested.emit)
        
        self.stop_btn = QPushButton(language_manager.get_text("stop_run"))
        self.stop_btn.setToolTip(language_manager.get_text("stop_run_tooltip"))
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "danger") # 빨간색 스타일
        
        auto_layout.addWidget(self.run_btn, 0, 0, 1, 2)
        auto_layout.addWidget(self.stop_btn, 0, 2, 1, 2)
        
        # Row 1: 자동 실행 설정
        self.delay_label = QLabel(language_manager.get_text("delay_ms"))
        auto_layout.addWidget(self.delay_label, 1, 0)
        self.global_delay_input = QLineEdit("1000")
        self.global_delay_input.setFixedWidth(50)
        self.global_delay_input.setAlignment(Qt.AlignRight)
        auto_layout.addWidget(self.global_delay_input, 1, 1)
        
        self.max_runs_label = QLabel(language_manager.get_text("max_runs_label"))
        auto_layout.addWidget(self.max_runs_label, 1, 2)
        self.auto_run_max_spin = QSpinBox()
        self.auto_run_max_spin.setRange(0, 9999)
        self.auto_run_max_spin.setValue(0)
        self.auto_run_max_spin.setToolTip(language_manager.get_text("max_runs_tooltip"))
        auto_layout.addWidget(self.auto_run_max_spin, 1, 3)
        
        # Row 2: 자동 실행 제어
        self.auto_run_btn = QPushButton(language_manager.get_text("start_auto_run"))
        self.auto_run_btn.setProperty("class", "accent") # 초록색 스타일
        self.auto_run_btn.clicked.connect(self.on_start_auto)
        
        self.stop_auto_btn = QPushButton(language_manager.get_text("stop_auto_run"))
        self.stop_auto_btn.clicked.connect(self.stop_auto_requested.emit)
        self.stop_auto_btn.setEnabled(False)
        
        self.auto_run_count_label = QLabel("0 / ∞")
        self.auto_run_count_label.setAlignment(Qt.AlignCenter)
        
        auto_layout.addWidget(self.auto_run_btn, 2, 0, 1, 2)
        auto_layout.addWidget(self.stop_auto_btn, 2, 2)
        auto_layout.addWidget(self.auto_run_count_label, 2, 3)
        
        self.auto_group.setLayout(auto_layout)
        
        layout.addLayout(top_layout)
        layout.addWidget(self.auto_group)
        
        self.setLayout(layout)
        
        # 초기 상태: 연결 전까지 비활성화
        self.set_controls_enabled(False)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.save_script_btn.setText(language_manager.get_text("save_script"))
        self.save_script_btn.setToolTip(language_manager.get_text("save_script_tooltip"))
        
        self.load_script_btn.setText(language_manager.get_text("load_script"))
        self.load_script_btn.setToolTip(language_manager.get_text("load_script_tooltip"))
        
        self.prefix_input.setToolTip(language_manager.get_text("prefix_tooltip"))
        self.suffix_input.setToolTip(language_manager.get_text("suffix_tooltip"))
        
        self.prefix_label.setText(language_manager.get_text("prefix_label"))
        self.suffix_label.setText(language_manager.get_text("suffix_label"))
        
        self.auto_group.setTitle(language_manager.get_text("execution_control"))
        
        self.run_btn.setText(language_manager.get_text("run_once"))
        self.run_btn.setToolTip(language_manager.get_text("run_once_tooltip"))
        
        self.stop_btn.setText(language_manager.get_text("stop_run"))
        self.stop_btn.setToolTip(language_manager.get_text("stop_run_tooltip"))
        
        self.delay_label.setText(language_manager.get_text("delay_ms"))
        self.max_runs_label.setText(language_manager.get_text("max_runs_label"))
        self.auto_run_max_spin.setToolTip(language_manager.get_text("max_runs_tooltip"))
        
        self.auto_run_btn.setText(language_manager.get_text("start_auto_run"))
        self.stop_auto_btn.setText(language_manager.get_text("stop_auto_run"))

    def on_start_auto(self) -> None:
        """자동 실행 시작 버튼 핸들러"""
        try:
            delay = int(self.global_delay_input.text())
        except ValueError:
            delay = 1000
        max_runs = self.auto_run_max_spin.value()
        self.start_auto_requested.emit(delay, max_runs)
        
    def set_running_state(self, running: bool, is_auto: bool = False) -> None:
        """
        실행 상태에 따라 버튼 활성화/비활성화를 설정합니다.
        
        Args:
            running (bool): 실행 중 여부.
            is_auto (bool): 자동 실행 모드 여부.
        """
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
        """
        자동 실행 카운트를 업데이트합니다.
        
        Args:
            current (int): 현재 실행 횟수.
            total (int): 총 실행 횟수 (0이면 무한).
        """
        total_str = "∞" if total == 0 else str(total)
        self.auto_run_count_label.setText(f"{current} / {total_str}")

    def set_controls_enabled(self, enabled: bool) -> None:
        """
        포트 연결 상태에 따라 제어 버튼을 활성화/비활성화합니다.
        
        Args:
            enabled (bool): 활성화 여부.
        """
        self.run_btn.setEnabled(enabled)
        self.auto_run_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(False) # Stop은 실행 중에만 활성화
        self.stop_auto_btn.setEnabled(False)
        
        self.save_script_btn.setEnabled(True)
        self.load_script_btn.setEnabled(True)
