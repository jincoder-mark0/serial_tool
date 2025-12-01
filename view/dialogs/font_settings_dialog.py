from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFontComboBox, QSpinBox, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class FontSettingsDialog(QDialog):
    """
    듀얼 폰트 설정 대화상자
    Proportional Font와 Fixed Font를 개별적으로 설정할 수 있습니다.
    """
    
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        
        self.setWindowTitle("Font Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.init_ui()
        self.load_current_fonts()
    
    def init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Proportional Font Group
        prop_group = QGroupBox("Proportional Font (UI Elements)")
        prop_group.setToolTip("Used for menus, labels, buttons, and other UI elements")
        prop_layout = QVBoxLayout(prop_group)
        
        # Proportional font controls
        prop_controls = QHBoxLayout()
        prop_controls.addWidget(QLabel("Font:"))
        self.prop_font_combo = QFontComboBox()
        self.prop_font_combo.setFontFilters(QFontComboBox.ScalableFonts)
        self.prop_font_combo.currentFontChanged.connect(self.update_prop_preview)
        prop_controls.addWidget(self.prop_font_combo, 1)
        
        prop_controls.addWidget(QLabel("Size:"))
        self.prop_size_spin = QSpinBox()
        self.prop_size_spin.setRange(6, 16)
        self.prop_size_spin.setValue(9)
        self.prop_size_spin.setSuffix(" pt")
        self.prop_size_spin.valueChanged.connect(self.update_prop_preview)
        prop_controls.addWidget(self.prop_size_spin)
        
        prop_layout.addLayout(prop_controls)
        
        # Proportional font preview
        self.prop_preview = QTextEdit()
        self.prop_preview.setReadOnly(True)
        self.prop_preview.setMaximumHeight(80)
        self.prop_preview.setText("The quick brown fox jumps over the lazy dog.\n빠른 갈색 여우가 게으른 개를 뛰어넘습니다.")
        prop_layout.addWidget(QLabel("Preview:"))
        prop_layout.addWidget(self.prop_preview)
        
        layout.addWidget(prop_group)
        
        # Fixed Font Group
        fixed_group = QGroupBox("Fixed Font (Text Data)")
        fixed_group.setToolTip("Used for TextEdit, LineEdit, CommandList, and other text data")
        fixed_layout = QVBoxLayout(fixed_group)
        
        # Fixed font controls
        fixed_controls = QHBoxLayout()
        fixed_controls.addWidget(QLabel("Font:"))
        self.fixed_font_combo = QFontComboBox()
        self.fixed_font_combo.setFontFilters(QFontComboBox.MonospacedFonts)
        self.fixed_font_combo.currentFontChanged.connect(self.update_fixed_preview)
        fixed_controls.addWidget(self.fixed_font_combo, 1)
        
        fixed_controls.addWidget(QLabel("Size:"))
        self.fixed_size_spin = QSpinBox()
        self.fixed_size_spin.setRange(6, 16)
        self.fixed_size_spin.setValue(9)
        self.fixed_size_spin.setSuffix(" pt")
        self.fixed_size_spin.valueChanged.connect(self.update_fixed_preview)
        fixed_controls.addWidget(self.fixed_size_spin)
        
        fixed_layout.addLayout(fixed_controls)
        
        # Fixed font preview
        self.fixed_preview = QTextEdit()
        self.fixed_preview.setReadOnly(True)
        self.fixed_preview.setMaximumHeight(80)
        self.fixed_preview.setText("AT+CMD=OK\\r\\n0123456789ABCDEF\\r\\nMonospace Text Display")
        fixed_layout.addWidget(QLabel("Preview:"))
        fixed_layout.addWidget(self.fixed_preview)
        
        layout.addWidget(fixed_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setToolTip("Reset fonts to platform defaults")
        reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_button)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_changes)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def load_current_fonts(self):
        """현재 폰트 설정을 로드합니다."""
        # Load proportional font
        prop_family, prop_size = self.theme_manager.get_proportional_font_info()
        self.prop_font_combo.setCurrentFont(QFont(prop_family))
        self.prop_size_spin.setValue(prop_size)
        
        # Load fixed font
        fixed_family, fixed_size = self.theme_manager.get_fixed_font_info()
        self.fixed_font_combo.setCurrentFont(QFont(fixed_family))
        self.fixed_size_spin.setValue(fixed_size)
        
        # Update previews explicitly with loaded values
        # (Combo box signals might not trigger if value is same as default or during init)
        self._update_prop_preview_with_font(QFont(prop_family, prop_size))
        self._update_fixed_preview_with_font(QFont(fixed_family, fixed_size))
    
    def update_prop_preview(self):
        """Proportional 폰트 프리뷰를 업데이트합니다 (Signal Slot)."""
        font = QFont(self.prop_font_combo.currentFont().family(), self.prop_size_spin.value())
        self._update_prop_preview_with_font(font)

    def _update_prop_preview_with_font(self, font: QFont):
        """Proportional 폰트 프리뷰 실제 업데이트 로직"""
        self.prop_preview.setFont(font)
    
    def update_fixed_preview(self):
        """Fixed 폰트 프리뷰를 업데이트합니다 (Signal Slot)."""
        font = QFont(self.fixed_font_combo.currentFont().family(), self.fixed_size_spin.value())
        self._update_fixed_preview_with_font(font)

    def _update_fixed_preview_with_font(self, font: QFont):
        """Fixed 폰트 프리뷰 실제 업데이트 로직"""
        font.setStyleHint(QFont.Monospace)
        self.fixed_preview.setFont(font)
    
    def reset_to_defaults(self):
        """플랫폼 기본 폰트로 리셋합니다."""
        import platform
        system = platform.system()
        
        # Proportional defaults
        if system == "Windows":
            self.prop_font_combo.setCurrentFont(QFont("Segoe UI"))
            self.prop_size_spin.setValue(9)
        elif system == "Linux":
            self.prop_font_combo.setCurrentFont(QFont("Ubuntu"))
            self.prop_size_spin.setValue(9)
        else:  # macOS
            self.prop_font_combo.setCurrentFont(QFont("SF Pro Text"))
            self.prop_size_spin.setValue(9)
        
        # Fixed defaults
        if system == "Windows":
            self.fixed_font_combo.setCurrentFont(QFont("Consolas"))
            self.fixed_size_spin.setValue(9)
        elif system == "Linux":
            self.fixed_font_combo.setCurrentFont(QFont("Monospace"))
            self.fixed_size_spin.setValue(9)
        else:  # macOS
            self.fixed_font_combo.setCurrentFont(QFont("Menlo"))
            self.fixed_size_spin.setValue(9)
        
        self.update_prop_preview()
        self.update_fixed_preview()
    
    def accept_changes(self):
        """변경 사항을 적용하고 대화상자를 닫습니다."""
        # Apply proportional font
        prop_family = self.prop_font_combo.currentFont().family()
        prop_size = self.prop_size_spin.value()
        self.theme_manager.set_proportional_font(prop_family, prop_size)
        
        # Apply fixed font
        fixed_family = self.fixed_font_combo.currentFont().family()
        fixed_size = self.fixed_size_spin.value()
        self.theme_manager.set_fixed_font(fixed_family, fixed_size)
        
        self.accept()
