from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray

from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection
from view.tools.theme_manager import ThemeManager
from view.tools.lang_manager import lang_manager
from view.dialogs.font_settings_dialog import FontSettingsDialog
from view.dialogs.about_dialog import AboutDialog
from view.dialogs.preferences_dialog import PreferencesDialog
from core.settings_manager import SettingsManager
from view.sections.main_menu_bar import MainMenuBar
from view.sections.main_status_bar import MainStatusBar
from view.widgets.main_toolbar import MainToolBar
from view.panels.port_panel import PortPanel

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우 클래스입니다.
    MainLeftSection(포트/제어)과 MainRightSection(커맨드/인스펙터)을 포함하며,
    메뉴바, 상태바 및 전역 설정을 관리합니다.
    """

    setting_save_requested = pyqtSignal(dict)

    def __init__(self, app_config=None) -> None:
        """
        MainWindow를 초기화하고 UI 및 설정을 로드합니다.

        Args:
            app_config: AppConfig 인스턴스. None이면 기본 경로 사용 (하위 호환성)
        """
        super().__init__()

        # AppConfig 저장
        self.app_config = app_config

        # 설정 관리자 초기화 (AppConfig 전달)
        self.settings = SettingsManager(app_config)

        # 테마 관리자 초기화 (AppConfig 전달)
        self.theme_manager = ThemeManager(app_config)

        # 언어 관리자 초기화 및 설정에서 언어 로드 (AppConfig 전달)
        # Note: lang_manager는 싱글톤이므로 첫 초기화 시에만 app_config 전달
        if app_config is not None:
            from view.tools.lang_manager import LangManager
            LangManager(app_config)

        lang = self.settings.get('settings.language', 'en')
        lang_manager.set_language(lang)
        lang_manager.language_changed.connect(self.on_language_changed)

        self.setWindowTitle(f"{lang_manager.get_text('main_title')} v1.0")
        self.resize(1400, 900)

        # 우측 패널 숨김 전 왼쪽 패널 너비 저장용
        self._saved_left_width = None

        self.init_ui()

        # 메뉴바 초기화 (위젯 사용)
        self.menu_bar = MainMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_signals()

        # 폰트 설정 복원 -> QApplication 폰트 적용 -> 테마 적용 순서 유지

        # 1. 설정에서 폰트 복원
        settings_dict = self.settings.get_all_settings()
        self.theme_manager.restore_fonts_from_settings(settings_dict)

        # 2. 애플리케이션에 가변폭 폰트 적용 (QApplication의 기본 폰트 설정)
        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)

        # 3. 설정에서 테마 적용 (폰트 스타일을 포함한 QSS 적용)
        theme = self.settings.get('settings.theme', 'dark')
        self.switch_theme(theme)

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

        # 툴바 설정
        self.main_toolbar = MainToolBar(self)
        self.addToolBar(Qt.TopToolBarArea, self.main_toolbar)

        # 스플리터 구성 (좌: 포트/제어, 우: 커맨드/인스펙터)
        self.splitter = QSplitter(Qt.Horizontal)

        self.left_section = MainLeftSection()
        self.right_section = MainRightSection()

        self.splitter.addWidget(self.left_section)
        self.splitter.addWidget(self.right_section)

        # 툴바 시그널 연결 (left_section 초기화 후)
        self._connect_toolbar_signals()

        # 스플리터 상태 복원
        splitter_state = self.settings.get('ui.splitter_state')
        if splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(splitter_state.encode()))
        else:
            self.splitter.setStretchFactor(0, 1) # 좌측 패널 비율
            self.splitter.setStretchFactor(1, 1) # 우측 패널 비율

        # 우측 패널 가시성 복원
        right_panel_visible = self.settings.get('settings.right_panel_visible', True)
        self.right_section.setVisible(right_panel_visible)

        main_layout.addWidget(self.splitter)

        # 전역 상태바 설정 (위젯 사용)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    def _connect_menu_signals(self) -> None:
        """메뉴바 시그널을 슬롯에 연결합니다."""
        self.menu_bar.new_tab_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.theme_changed.connect(self.switch_theme)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(lambda lang: lang_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.open_preferences_dialog)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

        # New signals
        self.menu_bar.open_port_requested.connect(self.left_section.open_current_port)
        self.menu_bar.close_tab_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.save_log_requested.connect(self.save_log)
        self.menu_bar.toggle_right_panel_requested.connect(self.toggle_right_panel)

    def save_log(self) -> None:
        """로그 저장 기능을 수행합니다."""
        if hasattr(self, 'left_section'):
            self.left_section.manual_control.manual_control_widget.on_save_manual_log_clicked()

    def _connect_toolbar_signals(self) -> None:
        """툴바 시그널을 슬롯에 연결합니다."""
        self.main_toolbar.open_requested.connect(self.left_section.open_current_port)
        self.main_toolbar.close_requested.connect(self.left_section.close_current_port)
        self.main_toolbar.clear_requested.connect(self.clear_log)
        self.main_toolbar.save_log_requested.connect(self.save_log)
        self.main_toolbar.settings_requested.connect(self.open_preferences_dialog)

    def clear_log(self) -> None:
        """현재 활성화된 탭의 로그를 지웁니다."""
        if hasattr(self, 'left_section'):
             current_index = self.left_section.port_tabs.currentIndex()
             current_widget = self.left_section.port_tabs.widget(current_index)
             if isinstance(current_widget, PortPanel):
                 current_widget.received_area.on_clear_recv_log_clicked()

    def switch_theme(self, theme_name: str) -> None:
        """
        애플리케이션 테마를 전환합니다.

        Args:
            theme_name (str): 전환할 테마 이름 ("dark" 또는 "light").
        """
        self.theme_manager.apply_theme(QApplication.instance(), theme_name)

        # 테마 설정을 저장
        if hasattr(self, 'settings'):
            self.settings.set('settings.theme', theme_name)

        # 메뉴바의 테마 체크 표시 업데이트
        if hasattr(self, 'menu_bar'):
            self.menu_bar.set_current_theme(theme_name)

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
                self.settings.set(f'settings.{key}', value)

            # 애플리케이션에 가변폭 폰트 적용
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            self.global_status_bar.show_message("Font settings updated", 2000)

    def open_preferences_dialog(self) -> None:
        """Preferences 다이얼로그를 엽니다."""
        current_settings = self.settings.get_all_settings()
        dialog = PreferencesDialog(self, current_settings)
        dialog.settings_changed.connect(self.on_settings_change_requested)
        dialog.exec_()


    def open_about_dialog(self) -> None:
        """About 다이얼로그를 엽니다."""
        dialog = AboutDialog(self)
        dialog.exec_()

    def on_settings_change_requested(self, settings: dict) -> None:
        """Preferences 설정 저장을 요청합니다."""
        self.setting_save_requested.emit(settings)

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
        self.setWindowTitle(f"{lang_manager.get_text('main_title')} v1.0")

        # 상태바 업데이트
        self.global_status_bar.retranslate_ui()

        # 메뉴 재생성
        self.menu_bar.retranslate_ui()

        # 설정에 언어 저장
        self.settings.set('settings.language', lang_code)

    def toggle_right_panel(self, visible: bool) -> None:
        """우측 패널의 가시성을 토글하고 윈도우 크기를 조정합니다."""
        if visible == self.right_section.isVisible():
            return

        current_width = self.width()
        handle_width = self.splitter.handleWidth()

        if visible:
            # 보이기: 윈도우 폭 증가
            target_right_width = 400 # 기본값

            # 저장된 왼쪽 패널 너비가 있으면 사용, 없으면 현재 너비 사용
            if self._saved_left_width is not None:
                left_width = self._saved_left_width
            else:
                left_width = self.left_section.width()

            self.resize(current_width + target_right_width + handle_width, self.height())
            self.right_section.setVisible(True)

            # 스플리터 크기 설정: 왼쪽 패널 크기 유지, 오른쪽 패널 크기 설정
            self.splitter.setSizes([left_width, target_right_width])

            # 복원 후 저장된 값 초기화
            self._saved_left_width = None

        else:
            # 숨기기: 윈도우 폭 감소
            # 현재 왼쪽 패널 너비를 저장
            self._saved_left_width = self.left_section.width()

            right_width = self.right_section.width()
            self.right_section.setVisible(False)
            self.resize(current_width - right_width - handle_width, self.height())

    def closeEvent(self, event) -> None:
        """
        윈도우 종료 이벤트를 처리합니다.
        윈도우 상태와 설정을 저장하고 애플리케이션을 종료합니다.

        Args:
            event (QCloseEvent): 종료 이벤트 객체.
        """
        # 윈도우 상태 저장
        self._save_window_state()

        # 스플리터 상태 저장
        self.settings.set('ui.splitter_state', self.splitter.saveState().toBase64().data().decode())

        # 우측 패널 가시성 저장
        self.settings.set('settings.right_panel_visible', self.right_section.isVisible())

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
