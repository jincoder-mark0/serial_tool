from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QAction, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt

from view.panels.left_panel import LeftPanel
from view.panels.right_panel import RightPanel
from view.theme_manager import ThemeManager
from core.settings_manager import SettingsManager

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우 클래스입니다.
    LeftPanel(포트/제어)과 RightPanel(커맨드/인스펙터)을 포함하며,
    메뉴바, 상태바 및 전역 설정을 관리합니다.
    """
    
    def __init__(self) -> None:
        """MainWindow를 초기화하고 UI 및 설정을 로드합니다."""
        super().__init__()
        
        # 설정 관리자 초기화
        self.settings = SettingsManager()
        
        # 테마 관리자 초기화 (인스턴스 기반)
        self.theme_manager = ThemeManager()
        
        self.setWindowTitle("SerialTool v1.0")
        self.resize(1400, 900)
        
        self.init_ui()
        self.init_menu()
        
        # 설정에서 테마 적용
        theme = self.settings.get('global.theme', 'dark')
        self.switch_theme(theme)
        
        # 설정에서 폰트 복원
        settings_dict = self.settings.get_all_settings()
        self.theme_manager.restore_fonts_from_settings(settings_dict)
        
        # 애플리케이션에 가변폭 폰트 적용
        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)
        
        # 저장된 윈도우 상태(크기, 위치) 로드
        self._load_window_state()
        
    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 스플리터 구성 (좌: 포트/제어, 우: 커맨드/인스펙터)
        splitter = QSplitter(Qt.Horizontal)
        
        self.left_panel = LeftPanel()
        self.right_panel = RightPanel()
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 1) # 좌측 패널 비율
        splitter.setStretchFactor(1, 1) # 우측 패널 비율
        
        main_layout.addWidget(splitter)
        
        # 전역 상태바 설정
        self.global_status_bar = QStatusBar()
        self.setStatusBar(self.global_status_bar)
        self.global_status_bar.showMessage("Ready")

    def init_menu(self) -> None:
        """메뉴바를 초기화하고 액션을 설정합니다."""
        menubar = self.menuBar()
        
        # 파일 메뉴 (File Menu)
        file_menu = menubar.addMenu("File")
        
        new_tab_action = QAction("New Port Tab", self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip("새 시리얼 포트 탭을 엽니다.")
        # LeftPanel의 add_new_port_tab 호출
        new_tab_action.triggered.connect(self.left_panel.add_new_port_tab)
        file_menu.addAction(new_tab_action)
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip("애플리케이션을 종료합니다.")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 보기 메뉴 (View Menu)
        view_menu = menubar.addMenu("View")
        
        # 테마 서브메뉴
        theme_menu = view_menu.addMenu("Theme")
        
        dark_action = QAction("Dark", self)
        dark_action.triggered.connect(lambda: self.switch_theme("dark"))
        theme_menu.addAction(dark_action)
        
        light_action = QAction("Light", self)
        light_action.triggered.connect(lambda: self.switch_theme("light"))
        theme_menu.addAction(light_action)
        
        # 폰트 설정 액션
        font_settings_action = QAction("Font Settings...", self)
        font_settings_action.setShortcut("Ctrl+Shift+F")
        font_settings_action.setToolTip("가변폭 및 고정폭 폰트를 설정합니다.")
        font_settings_action.triggered.connect(self.open_font_settings_dialog)
        view_menu.addAction(font_settings_action)
        
        # 도구 메뉴 (Tools Menu)
        tools_menu = menubar.addMenu("Tools")
        
        # 도움말 메뉴 (Help Menu)
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        help_menu.addAction(about_action)

    def switch_theme(self, theme_name: str) -> None:
        """
        애플리케이션 테마를 전환합니다.
        
        Args:
            theme_name (str): 전환할 테마 이름 ("dark" 또는 "light").
        """
        self.theme_manager.apply_theme(QApplication.instance(), theme_name)
        
        # 테마 설정을 저장
        if hasattr(self, 'settings'):
            self.settings.set('global.theme', theme_name)
        
        if theme_name == "dark":
            self.global_status_bar.showMessage("Theme changed to Dark", 2000)
        else:
            self.global_status_bar.showMessage("Theme changed to Light", 2000)

    def open_font_settings_dialog(self) -> None:
        """듀얼 폰트 설정 대화상자를 엽니다."""
        from view.dialogs.font_settings_dialog import FontSettingsDialog
        
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            # 폰트 설정 저장
            font_settings = self.theme_manager.get_font_settings()
            for key, value in font_settings.items():
                self.settings.set(f'ui.{key}', value)
            
            # 애플리케이션에 가변폭 폰트 적용
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)
            
            self.global_status_bar.showMessage("Font settings updated", 2000)

    
    def _load_window_state(self) -> None:
        """
        저장된 윈도우 상태(크기, 위치)를 로드하여 적용합니다.
        """
        # 윈도우 크기 로드
        width = self.settings.get('ui.window_width', 1400)
        height = self.settings.get('ui.window_height', 900)
        self.resize(width, height)
        
        # 윈도우 위치 로드 (옵션)
        x = self.settings.get('ui.window_x')
        y = self.settings.get('ui.window_y')
        if x is not None and y is not None:
            self.move(x, y)
    
    def _save_window_state(self) -> None:
        """
        현재 윈도우 상태(크기, 위치)를 설정에 저장합니다.
        """
        self.settings.set('ui.window_width', self.width())
        self.settings.set('ui.window_height', self.height())
        self.settings.set('ui.window_x', self.x())
        self.settings.set('ui.window_y', self.y())
    
    def closeEvent(self, event) -> None:
        """
        윈도우 종료 이벤트를 처리합니다.
        윈도우 상태와 설정을 저장하고 애플리케이션을 종료합니다.
        
        Args:
            event (QCloseEvent): 종료 이벤트 객체.
        """
        # 윈도우 상태 저장
        self._save_window_state()
        
        # 설정 파일 저장
        self.settings.save_settings()
        
        # 종료 이벤트 수락
        event.accept()
