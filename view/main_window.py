from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray

from view.sections import (
    MainLeftSection,
    MainRightSection,
    MainStatusBar,
    MainMenuBar,
    MainToolBar
)
from view.dialogs import (
    FontSettingsDialog,
    AboutDialog,
    PreferencesDialog
)
from view.managers.theme_manager import ThemeManager
from view.managers.lang_manager import lang_manager, LangManager
from view.managers.color_manager import ColorManager
from core.settings_manager import SettingsManager

class MainWindow(QMainWindow):
    """
    애플리케이션의 메인 윈도우 클래스입니다.
    MainLeftSection(포트/제어)과 MainRightSection(커맨드/인스펙터)을 포함하며,
    설정의 로드 및 저장을 조율합니다.
    """

    close_requested = pyqtSignal()
    settings_save_requested = pyqtSignal(dict)

    def __init__(self, resource_path=None) -> None:
        """
        MainWindow를 초기화하고 UI 및 설정을 로드합니다.

        Args:
            resource_path: ResourcePath 인스턴스.
        """
        super().__init__()

        # 설정 및 매니저 초기화
        self.resource_path = resource_path

        self.settings = SettingsManager(resource_path)
        self.theme_manager = ThemeManager(resource_path)

        # 싱글톤이므로 첫 초기화 시에만 resource_path 전달
        if resource_path is not None:
            LangManager(resource_path)
            ColorManager(resource_path)

        # 초기 언어 설정
        lang = self.settings.get('settings.language', 'en')
        lang_manager.set_language(lang)
        lang_manager.language_changed.connect(self.on_language_changed)

        self.setWindowTitle(f"{lang_manager.get_text('main_title')} v1.0")
        self.resize(1400, 900)

        # 우측 패널 숨김 전 왼쪽 패널 너비 저장용
        self._saved_left_width = None
        self._saved_right_width = None

        # UI 초기화
        self.init_ui()

        # 메뉴바 초기화
        self.menu_bar = MainMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_signals()

        # 초기 스타일 및 설정 적용
        self._apply_initial_settings()

        # 윈도우 상태 및 각 섹션의 데이터 복원
        self._load_window_state()

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
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # 툴바 시그널 연결 (left_section 초기화 후)
        self._connect_toolbar_signals()

        main_layout.addWidget(self.splitter)

        # 전역 상태바 설정 (위젯 사용)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    def _apply_initial_settings(self) -> None:
        """초기 폰트, 테마, UI 상태를 적용합니다."""
        # 폰트 복원

        # 1. 설정에서 폰트 복원
        settings_dict = self.settings.get_all_settings()
        self.theme_manager.restore_fonts_from_settings(settings_dict)

        # 2. 애플리케이션에 가변폭 폰트 적용 (QApplication의 기본 폰트 설정)
        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)

        # 3. 설정에서 테마 적용 (폰트 스타일을 포함한 QSS 적용)
        theme = self.settings.get('settings.theme', 'dark')
        self.switch_theme(theme)

        # 4. 설정에서 오른쪽 패널 표시 복원
        right_panel_visible = self.settings.get('settings.right_panel_visible', True)
        self.menu_bar.set_right_panel_checked(right_panel_visible)
        self.right_section.setVisible(right_panel_visible)

        # 5. 설정에서 스플리터 상태 복원
        splitter_state = self.settings.get('ui.splitter_state')
        if splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(splitter_state.encode()))
        else:
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 1)

    def _load_window_state(self) -> None:
        """
        저장된 윈도우 상태 및 각 섹션의 데이터를 로드하여 주입합니다.
        """
        # 1. 윈도우 지오메트리
        width = self.settings.get('ui.window_width', 1400)
        height = self.settings.get('ui.window_height', 900)
        self.resize(width, height)

        x = self.settings.get('ui.window_x')
        y = self.settings.get('ui.window_y')
        if x is not None and y is not None:
            self.move(x, y)

        # 2. Left Section 상태 복원 (설정 파일 구조에 맞춰 데이터 매핑)
        left_section_state = {
            "manual_ctrl": self.settings.get("manual_ctrl", {}),
            "ports": self.settings.get("ports.tabs", [])
        }
        self.left_section.load_state(left_section_state)

        # 3. Right Section 상태 복원
        right_section_state = {
            "macro_panel": {
                "commands": self.settings.get("macro_list.commands", []),
                "control_state": self.settings.get("macro_list.control_state", {})
            }
        }
        self.right_section.load_state(right_section_state)

    def get_window_state(self) -> dict:
        """
        현재 윈도우의 모든 상태를 수집하여 반환합니다.

        Returns:
            dict: 윈도우 상태 딕셔너리
        """
        state = {}

        # 1. 윈도우 기본 설정
        state['ui.window_width'] = self.width()
        state['ui.window_height'] = self.height()
        state['ui.window_x'] = self.x()
        state['ui.window_y'] = self.y()
        state['ui.splitter_state'] = self.splitter.saveState().toBase64().data().decode()
        state['settings.right_panel_visible'] = self.right_section.isVisible()

        # 2. Left Section 상태
        left_state = self.left_section.save_state()
        if 'manual_ctrl' in left_state:
            state['manual_ctrl'] = left_state['manual_ctrl']
        if 'ports' in left_state:
            state['ports.tabs'] = left_state['ports']

        # 3. Right Section 상태
        right_state = self.right_section.save_state()
        if 'macro_panel' in right_state:
            macro_data = right_state['macro_panel']
            state['macro_list.commands'] = macro_data.get('commands', [])
            state['macro_list.control_state'] = macro_data.get('control_state', {})

        return state

    def closeEvent(self, event) -> None:
        """
        종료 이벤트를 처리합니다.
        Presenter에게 종료 요청을 알리고 이벤트를 수락합니다.
        """
        self.close_requested.emit()
        event.accept()


    def _connect_menu_signals(self) -> None:
        """메뉴바 시그널을 슬롯에 연결합니다."""
        self.menu_bar.tab_new_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.theme_changed.connect(self.switch_theme)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(lambda lang: lang_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.open_preferences_dialog)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

        self.menu_bar.port_open_requested.connect(self.left_section.open_current_port)
        self.menu_bar.tab_close_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.log_save_requested.connect(self.save_log)
        self.menu_bar.toggle_right_panel_requested.connect(self.toggle_right_panel)

    def _connect_toolbar_signals(self) -> None:
        """툴바 시그널을 슬롯에 연결합니다."""
        self.main_toolbar.open_requested.connect(self.left_section.open_current_port)
        self.main_toolbar.close_requested.connect(self.left_section.close_current_port)
        self.main_toolbar.clear_requested.connect(self.clear_log)
        self.main_toolbar.log_save_requested.connect(self.save_log)
        self.main_toolbar.settings_requested.connect(self.open_preferences_dialog)

    def save_log(self) -> None:
        """로그 저장 기능을 수행합니다."""
        if hasattr(self, 'left_section'):
            self.left_section.manual_ctrl.manual_ctrl_widget.on_save_manual_log_clicked()

    def clear_log(self) -> None:
        """현재 활성화된 탭의 로그를 지웁니다."""
        if hasattr(self, 'left_section'):
            current_index = self.left_section.port_tabs.currentIndex()
            current_widget = self.left_section.port_tabs.widget(current_index)
            if current_widget and hasattr(current_widget, 'received_area_widget'):
                current_widget.received_area_widget.on_clear_rx_log_clicked()

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

        msg = f"Theme changed to {theme_name.capitalize()}"
        self.global_status_bar.show_message(msg, 2000)

    def open_font_settings_dialog(self) -> None:
        """폰트 설정 대화상자를 엽니다."""
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
        """설정 대화상자를 엽니다."""
        current_settings = self.settings.get_all_settings()
        dialog = PreferencesDialog(self, current_settings)
        dialog.settings_changed.connect(self.on_settings_change_requested)
        dialog.exec_()

    def open_about_dialog(self) -> None:
        """정보 대화상자를 엽니다."""
        dialog = AboutDialog(self)
        dialog.exec_()

    def on_settings_change_requested(self, settings: dict) -> None:
        """설정 변경 요청을 Presenter로 전달합니다."""
        self.settings_save_requested.emit(settings)

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
        """우측 패널의 가시성을 토글합니다."""
        if visible == self.right_section.isVisible():
            return

        current_width = self.width()
        handle_width = self.splitter.handleWidth()

        if visible:
            # 보이기: 윈도우 폭 증가
            # 저장된 오른쪽 패널 너비가 있으면 사용, 없으면 기본값 400
            if hasattr(self, '_saved_right_width') and self._saved_right_width is not None:
                target_right_width = self._saved_right_width
            else:
                target_right_width = 400

            # 현재 왼쪽 패널 너비 사용 (사용자가 조절했을 수 있으므로 저장된 값보다 현재 값 우선)
            left_width = self.left_section.width()

            self.resize(current_width + target_right_width + handle_width, self.height())
            self.right_section.setVisible(True)

            # 스플리터 크기 설정: 왼쪽 패널 크기 유지, 오른쪽 패널 크기 설정
            self.splitter.setSizes([left_width, target_right_width])

            # 복원 후 저장된 값 초기화
            self._saved_left_width = None
            self._saved_right_width = None

        else:
            # 숨기기: 윈도우 폭 감소
            # 현재 패널 너비 저장
            self._saved_left_width = self.left_section.width()
            self._saved_right_width = self.right_section.width()

            # 왼쪽 패널의 현재 너비를 기준으로 윈도우 크기 재조정
            # 중앙 위젯의 좌우 마진을 동적으로 계산
            margins = self.centralWidget().layout().contentsMargins()
            total_margin = margins.left() + margins.right()
            new_window_width = self._saved_left_width + total_margin

            self.right_section.setVisible(False)
            self.resize(new_window_width, self.height())
