from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QFontComboBox, QSpinBox, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import platform
from view.language_manager import language_manager

class FontSettingsDialog(QDialog):
    """
    듀얼 폰트 설정 대화상자입니다.
    가변폭(Proportional) 폰트와 고정폭(Fixed) 폰트를 개별적으로 설정할 수 있습니다.
    """

    def __init__(self, theme_manager, parent=None):
        """
        FontSettingsDialog를 초기화합니다.

        Args:
            theme_manager (ThemeManager): 테마 및 폰트 관리를 위한 ThemeManager 인스턴스.
            parent (QWidget, optional): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.theme_manager = theme_manager

        self.setWindowTitle(language_manager.get_text("title_font_settings"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        self.init_ui()
        self.load_current_fonts()

    def init_ui(self):
        """UI 컴포넌트를 초기화하고 레이아웃을 구성합니다."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 가변폭 폰트 그룹 (Proportional Font Group)
        self.prop_group = QGroupBox(language_manager.get_text("prop_font_group"))
        self.prop_group.setToolTip(language_manager.get_text("prop_font_tooltip"))
        prop_layout = QVBoxLayout(self.prop_group)

        # 가변폭 폰트 컨트롤
        prop_controls = QHBoxLayout()
        self.prop_font_label = QLabel(language_manager.get_text("font_label"))
        prop_controls.addWidget(self.prop_font_label)
        self.prop_font_combo = QFontComboBox()
        self.prop_font_combo.setFontFilters(QFontComboBox.ScalableFonts)
        self.prop_font_combo.currentFontChanged.connect(self.update_prop_preview)
        prop_controls.addWidget(self.prop_font_combo, 1)

        self.prop_size_label = QLabel(language_manager.get_text("size_label"))
        prop_controls.addWidget(self.prop_size_label)
        self.prop_size_spin = QSpinBox()
        self.prop_size_spin.setRange(6, 16)
        self.prop_size_spin.setValue(9)
        self.prop_size_spin.setSuffix(" pt")
        self.prop_size_spin.valueChanged.connect(self.update_prop_preview)
        prop_controls.addWidget(self.prop_size_spin)

        prop_layout.addLayout(prop_controls)

        # 가변폭 폰트 미리보기
        self.prop_preview = QTextEdit()
        self.prop_preview.setReadOnly(True)
        self.prop_preview.setMaximumHeight(80)
        self.prop_preview.setText("The quick brown fox jumps over the lazy dog.\n빠른 갈색 여우가 게으른 개를 뛰어넘습니다.")
        self.prop_preview_label = QLabel(language_manager.get_text("preview_label"))
        prop_layout.addWidget(self.prop_preview_label)
        prop_layout.addWidget(self.prop_preview)

        layout.addWidget(self.prop_group)

        # 고정폭 폰트 그룹 (Fixed Font Group)
        self.fixed_group = QGroupBox(language_manager.get_text("fixed_font_group"))
        self.fixed_group.setToolTip(language_manager.get_text("fixed_font_tooltip"))
        fixed_layout = QVBoxLayout(self.fixed_group)

        # 고정폭 폰트 컨트롤
        fixed_controls = QHBoxLayout()
        self.fixed_font_label = QLabel(language_manager.get_text("font_label"))
        fixed_controls.addWidget(self.fixed_font_label)
        self.fixed_font_combo = QFontComboBox()
        self.fixed_font_combo.setFontFilters(QFontComboBox.MonospacedFonts)
        self.fixed_font_combo.currentFontChanged.connect(self.update_fixed_preview)
        fixed_controls.addWidget(self.fixed_font_combo, 1)

        self.fixed_size_label = QLabel(language_manager.get_text("size_label"))
        fixed_controls.addWidget(self.fixed_size_label)
        self.fixed_size_spin = QSpinBox()
        self.fixed_size_spin.setRange(6, 16)
        self.fixed_size_spin.setValue(9)
        self.fixed_size_spin.setSuffix(" pt")
        self.fixed_size_spin.valueChanged.connect(self.update_fixed_preview)
        fixed_controls.addWidget(self.fixed_size_spin)

        fixed_layout.addLayout(fixed_controls)

        # 고정폭 폰트 미리보기
        self.fixed_preview = QTextEdit()
        self.fixed_preview.setReadOnly(True)
        self.fixed_preview.setMaximumHeight(80)
        self.fixed_preview.setText("AT+CMD=OK\\r\\n0123456789ABCDEF\\r\\nMonospace Text Display")
        self.fixed_preview_label = QLabel(language_manager.get_text("preview_label"))
        fixed_layout.addWidget(self.fixed_preview_label)
        fixed_layout.addWidget(self.fixed_preview)

        layout.addWidget(self.fixed_group)

        # 버튼 영역
        button_layout = QHBoxLayout()

        self.reset_button = QPushButton(language_manager.get_text("reset_defaults"))
        self.reset_button.setToolTip(language_manager.get_text("reset_defaults_tooltip"))
        self.reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.reset_button)

        button_layout.addStretch()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.button_box.accepted.connect(self.accept_changes)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_changes)
        button_layout.addWidget(self.button_box)

        layout.addLayout(button_layout)

    def showEvent(self, event):
        """
        다이얼로그가 표시될 때 호출됩니다. 프리뷰를 현재 설정으로 초기화합니다.

        Args:
            event (QShowEvent): 표시 이벤트.
        """
        super().showEvent(event)
        # 프리뷰를 현재 설정으로 강제 업데이트
        self.load_current_fonts()

    def load_current_fonts(self):
        """ThemeManager에서 현재 폰트 설정을 로드하여 UI에 반영합니다."""
        # 가변폭 폰트 로드
        prop_family, prop_size = self.theme_manager.get_proportional_font_info()
        self.prop_font_combo.setCurrentFont(QFont(prop_family))
        self.prop_size_spin.setValue(prop_size)

        # 고정폭 폰트 로드
        fixed_family, fixed_size = self.theme_manager.get_fixed_font_info()
        self.fixed_font_combo.setCurrentFont(QFont(fixed_family))
        self.fixed_size_spin.setValue(fixed_size)

        # 로드된 값으로 프리뷰 명시적 업데이트
        # (콤보박스 시그널은 값이 같거나 초기화 중일 때 발생하지 않을 수 있음)
        self._update_prop_preview_with_font(QFont(prop_family, prop_size))
        self._update_fixed_preview_with_font(QFont(fixed_family, fixed_size))

    def update_prop_preview(self):
        """가변폭 폰트 프리뷰를 업데이트합니다 (Signal Slot)."""
        font = QFont(self.prop_font_combo.currentFont().family(), self.prop_size_spin.value())
        self._update_prop_preview_with_font(font)

    def _update_prop_preview_with_font(self, font: QFont):
        """
        가변폭 폰트 프리뷰를 실제 업데이트하는 내부 메서드입니다.

        Args:
            font (QFont): 적용할 폰트 객체.
        """
        self.prop_preview.setFont(font)

    def update_fixed_preview(self):
        """고정폭 폰트 프리뷰를 업데이트합니다 (Signal Slot)."""
        font = QFont(self.fixed_font_combo.currentFont().family(), self.fixed_size_spin.value())
        self._update_fixed_preview_with_font(font)

    def _update_fixed_preview_with_font(self, font: QFont):
        """
        고정폭 폰트 프리뷰를 실제 업데이트하는 내부 메서드입니다.

        Args:
            font (QFont): 적용할 폰트 객체.
        """
        font.setStyleHint(QFont.Monospace)
        self.fixed_preview.setFont(font)

    def reset_to_defaults(self):
        """폰트 설정을 플랫폼별 기본값으로 리셋합니다."""
        system = platform.system()

        # 가변폭 폰트 기본값
        if system == "Windows":
            self.prop_font_combo.setCurrentFont(QFont("Segoe UI"))
            self.prop_size_spin.setValue(9)
        elif system == "Linux":
            self.prop_font_combo.setCurrentFont(QFont("Ubuntu"))
            self.prop_size_spin.setValue(9)
        else:  # macOS
            self.prop_font_combo.setCurrentFont(QFont("SF Pro Text"))
            self.prop_size_spin.setValue(9)

        # 고정폭 폰트 기본값
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

    def apply_changes(self):
        """변경 사항을 ThemeManager에 적용합니다 (다이얼로그는 유지)."""
        # 가변폭 폰트 적용
        prop_family = self.prop_font_combo.currentFont().family()
        prop_size = self.prop_size_spin.value()
        self.theme_manager.set_proportional_font(prop_family, prop_size)

        # 고정폭 폰트 적용
        fixed_family = self.fixed_font_combo.currentFont().family()
        fixed_size = self.fixed_size_spin.value()
        self.theme_manager.set_fixed_font(fixed_family, fixed_size)

    def accept_changes(self):
        """변경 사항을 적용하고 대화상자를 닫습니다."""
        self.apply_changes()
        self.accept()
