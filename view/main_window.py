from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication
)
from PyQt5.QtCore import Qt

from view.sections.left_section import LeftSection
from view.sections.right_section import RightSection
from view.theme_manager import ThemeManager
from view.language_manager import language_manager
from view.dialogs.font_settings_dialog import FontSettingsDialog
from view.dialogs.about_dialog import AboutDialog
from view.dialogs.preferences_dialog import PreferencesDialog
from core.settings_manager import SettingsManager
from view.widgets.main_menu_bar import MainMenuBar
from view.widgets.main_status_bar import MainStatusBar

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우 클래스입니다.
    LeftSection(포트/제어)과 RightSection(커맨드/인스펙터)을 포함하며,
    메뉴바, 상태바 및 전역 설정을 관리합니다.
    """

    def __init__(self) -> None:
        """MainWindow를 초기화하고 UI 및 설정을 로드합니다."""
        super().__init__()

        # 설정 관리자 초기화
        self.settings = SettingsManager()

        # 테마 관리자 초기화 (인스턴스 기반)
        self.theme_manager = ThemeManager()

        # 언어 관리자 초기화 및 설정에서 언어 로드
        lang = self.settings.get('global.language', 'en')
        language_manager.set_language(lang)
        language_manager.language_changed.connect(self.on_language_changed)

        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")
        self.resize(1400, 900)

        self.init_ui()

        # 메뉴바 초기화 (위젯 사용)
        self.menu_bar = MainMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_signals()

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

        # 포트 탭 상태 복원
        port_states = self.settings.get('ports.tabs', [])
        if hasattr(self, 'left_section'):
            self.left_section.load_state(port_states)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 스플리터 구성 (좌: 포트/제어, 우: 커맨드/인스펙터)
        splitter = QSplitter(Qt.Horizontal)

        self.left_section = LeftSection()
        self.right_section = RightSection()

        splitter.addWidget(self.left_section)
        splitter.addWidget(self.right_section)
        splitter.setStretchFactor(0, 1) # 좌측 패널 비율
        splitter.setStretchFactor(1, 1) # 우측 패널 비율

        main_layout.addWidget(splitter)

        # 전역 상태바 설정 (위젯 사용)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    def _connect_menu_signals(self) -> None:
        """메뉴바 시그널을 슬롯에 연결합니다."""
        self.menu_bar.new_tab_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.theme_changed.connect(self.switch_theme)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(lambda lang: language_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.open_preferences_dialog)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

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
            self.global_status_bar.show_message("Theme changed to Dark", 2000)
        else:
            self.global_status_bar.show_message("Theme changed to Light", 2000)

    def open_font_settings_dialog(self) -> None:
        """듀얼 폰트 설정 대화상자를 엽니다."""
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            # 폰트 설정 저장
            font_settings = self.theme_manager.get_font_settings()
            for key, value in font_settings.items():
                self.settings.set(f'ui.{key}', value)

            # 애플리케이션에 가변폭 폰트 적용
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            self.global_status_bar.show_message("Font settings updated", 2000)

    def open_preferences_dialog(self) -> None:
        """Preferences 다이얼로그를 엽니다."""
        current_settings = self.settings.get_all_settings()
        dialog = PreferencesDialog(self, current_settings)
        dialog.settings_changed.connect(self.apply_preferences)
        dialog.exec_()

    def apply_preferences(self, new_settings: dict) -> None:
        """
        Preferences 다이얼로그에서 변경된 설정을 적용합니다.

        Args:
            new_settings (dict): 변경된 설정 딕셔너리.
        """
        # 설정을 논리적 그룹별로 저장
        settings_map = {
            # UI/Theme settings
            'menu_theme': 'global.theme',
            'menu_language': 'global.language',
            'font_size': 'ui.font_size',
            'max_log_lines': 'ui.log_max_lines',

            # Serial settings
            'default_baudrate': 'serial.default_baudrate',
            'scan_interval': 'serial.scan_interval',

            # Command settings
            'command_prefix': 'command.prefix',
            'command_suffix': 'command.suffix',

            # Logging settings
            'log_path': 'logging.path',
        }

        for key, value in new_settings.items():
            setting_path = settings_map.get(key, f'global.{key}')  # Fallback to global
            self.settings.set(setting_path, value)

        # 테마 변경
        if 'menu_theme' in new_settings:
            self.switch_theme(new_settings['menu_theme'])

        # 언어 변경
        if 'menu_language' in new_settings:
            lang_code = 'ko' if new_settings['menu_language'] == 'Korean' else 'en'
            language_manager.set_language(lang_code)

        self.global_status_bar.show_message("Settings updated", 2000)

    def open_about_dialog(self) -> None:
        """About 다이얼로그를 엽니다."""
        dialog = AboutDialog(self)
        dialog.exec_()


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

    def on_language_changed(self, lang_code: str) -> None:
        """
        언어 변경 시 호출되는 슬롯입니다.
        윈도우 제목과 메뉴 텍스트를 업데이트합니다.

        Args:
            lang_code (str): 변경된 언어 코드 (예: 'en', 'ko').
        """
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")

        # 상태바 업데이트
        self.global_status_bar.retranslate_ui()

        # 메뉴 재생성
        self.menu_bar.retranslate_ui()

        # 설정에 언어 저장
        self.settings.set('global.language', lang_code)

    def closeEvent(self, event) -> None:
        """
        윈도우 종료 이벤트를 처리합니다.
        윈도우 상태와 설정을 저장하고 애플리케이션을 종료합니다.

        Args:
            event (QCloseEvent): 종료 이벤트 객체.
        """
        # 윈도우 상태 저장
        self._save_window_state()

        # 패널 상태 저장
        if hasattr(self, 'right_section'):
            self.right_section.save_state()

        if hasattr(self, 'left_section'):
            port_states = self.left_section.save_state()
            self.settings.set('ports.tabs', port_states)

        # 설정 파일 저장
        self.settings.save_settings()

        # 종료 이벤트 수락
        event.accept()
