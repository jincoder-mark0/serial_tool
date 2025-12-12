"""
메인 윈도우 모듈

애플리케이션의 최상위 뷰를 정의합니다.

## WHY
* 전체 UI 레이아웃 구성 및 관리
* Presenter와의 인터페이스(Signal/Slot) 제공
* 전역 설정 및 리소스 초기화

## WHAT
* 섹션(Section) 배치 및 스플리터 관리
* 메뉴바, 툴바, 상태바 관리
* Presenter용 공개 API 제공

## HOW
* QMainWindow 상속
* MVP 패턴을 위한 시그널 노출
* SettingsManager를 통한 상태 복원
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QShortcut
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray

from view.sections import (
    MainLeftSection, MainRightSection, MainStatusBar, MainMenuBar, MainToolBar
)
from view.dialogs import (
    FontSettingsDialog, AboutDialog, PreferencesDialog, FileTransferDialog
)
from view.managers.theme_manager import ThemeManager
from view.managers.lang_manager import lang_manager, LangManager
from view.managers.color_manager import ColorManager
from core.settings_manager import SettingsManager
from constants import ConfigKeys

class MainWindow(QMainWindow):
    """
    메인 윈도우 클래스

    Presenter가 UI 내부 구조를 알 필요 없이 조작할 수 있도록
    필요한 인터페이스를 프로퍼티와 메서드로 제공합니다.
    """

    # Presenter 전달용 시그널 (UI 이벤트 -> 비즈니스 로직 요청)
    close_requested = pyqtSignal()
    settings_save_requested = pyqtSignal(dict)

    font_settings_changed = pyqtSignal(dict)

    # 단축키 시그널
    shortcut_connect_requested = pyqtSignal()
    shortcut_disconnect_requested = pyqtSignal()
    shortcut_clear_requested = pyqtSignal()

    # 파일 전송 시그널 (다이얼로그 인스턴스 전달)
    file_transfer_dialog_opened = pyqtSignal(object)

    # 하위 컴포넌트 시그널 중계 (Signal Chaining)
    manual_cmd_send_requested = pyqtSignal(str, bool, bool, bool, bool)
    port_tab_added = pyqtSignal(object)

    def __init__(self, resource_path=None) -> None:
        """
        MainWindow 초기화

        Args:
            resource_path: 리소스 경로 객체
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
        lang = self.settings.get(ConfigKeys.LANGUAGE, 'en')
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

        # 단축키 초기화
        self.init_shortcuts()

    def init_ui(self) -> None:
        """UI 레이아웃 및 컴포넌트 초기화"""
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

        # 시그널 체이닝 (하위 -> 상위)
        self.left_section.manual_cmd_send_requested.connect(self.manual_cmd_send_requested.emit)
        self.left_section.port_tab_added.connect(self.port_tab_added.emit)

        self._connect_toolbar_signals()

        main_layout.addWidget(self.splitter)

        # 전역 상태바 설정 (위젯 사용)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    # --------------------------------------------------------
    # Presenter Interface (View 인터페이스)
    # --------------------------------------------------------
    @property
    def port_view(self):
        """PortPresenter용 뷰 인터페이스 반환"""
        return self.left_section

    @property
    def macro_view(self):
        """MacroPresenter용 뷰 인터페이스 반환"""
        return self.right_section.macro_panel

    def get_port_tabs_count(self) -> int:
        """현재 포트 탭 개수 반환"""
        return self.left_section.port_tabs.count()

    def get_port_tab_widget(self, index: int) -> QWidget:
        """
        인덱스에 해당하는 포트 탭 위젯 반환

        Args:
            index (int): 탭 인덱스

        Returns:
            QWidget: 포트 패널 위젯
        """
        return self.left_section.port_tabs.widget(index)

    def log_system_message(self, message: str, level: str = "INFO") -> None:
        """
        시스템 로그 기록

        Args:
            message (str): 메시지 내용
            level (str): 로그 레벨
        """
        self.left_section.system_log_widget.log(message, level)

    def update_status_bar_stats(self, rx_bytes: int, tx_bytes: int) -> None:
        """상태바 통계 업데이트"""
        self.global_status_bar.update_rx_speed(rx_bytes)
        self.global_status_bar.update_tx_speed(tx_bytes)

    def update_status_bar_time(self, time_str: str) -> None:
        """상태바 시간 업데이트"""
        self.global_status_bar.update_time(time_str)

    def update_status_bar_port(self, port_name: str, connected: bool) -> None:
        """상태바 포트 상태 업데이트"""
        self.global_status_bar.update_port_status(port_name, connected)

    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """상태바 메시지 표시"""
        self.global_status_bar.show_message(message, timeout)

    def manual_save_log(self) -> None:
        """로그 저장 다이얼로그 호출"""
        self.left_section.manual_ctrl.manual_ctrl_widget.on_save_manual_log_clicked()

    def append_local_echo_data(self, data: bytes) -> None:
        """
        Local Echo 데이터를 현재 활성화된 포트 탭에 추가합니다.

        Args:
            data (bytes): 표시할 송신 데이터
        """
        self.left_section.append_data_to_current_port(data)

    # --------------------------------------------------------
    # 내부 로직 (Internal Logic)
    # --------------------------------------------------------

    def init_shortcuts(self) -> None:
        """전역 단축키를 초기화합니다."""
        # F2: 연결 (Connect)
        self.shortcut_connect = QShortcut(QKeySequence("F2"), self)
        self.shortcut_connect.activated.connect(self.shortcut_connect_requested.emit)

        # F3: 연결 해제 (Disconnect)
        self.shortcut_disconnect = QShortcut(QKeySequence("F3"), self)
        self.shortcut_disconnect.activated.connect(self.shortcut_disconnect_requested.emit)

        # F5: 로그 지우기 (Clear Log)
        self.shortcut_clear = QShortcut(QKeySequence("F5"), self)
        self.shortcut_clear.activated.connect(self.shortcut_clear_requested.emit)

    def _apply_initial_settings(self) -> None:
        """
        초기 설정 적용

        Logic:
            - 폰트 설정 복원
            - 애플리케이션 폰트 적용
            - 테마 적용
            - 패널 및 스플리터 상태 복원
        """
        # 폰트 복원

        # 1. 설정에서 폰트 복원
        settings_dict = self.settings.get_all_settings()
        self.theme_manager.restore_fonts_from_settings(settings_dict)

        # 2. 애플리케이션에 가변폭 폰트 적용 (QApplication의 기본 폰트 설정)
        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)

        # 3. 설정에서 테마 적용 (폰트 스타일을 포함한 QSS 적용)
        theme = self.settings.get(ConfigKeys.THEME, 'dark')
        self.switch_theme(theme)

        # 4. 설정에서 오른쪽 패널 표시 복원
        right_panel_visible = self.settings.get(ConfigKeys.RIGHT_PANEL_VISIBLE, True)
        self.menu_bar.set_right_panel_checked(right_panel_visible)
        self.right_section.setVisible(right_panel_visible)

        # 5. 설정에서 스플리터 상태 복원
        splitter_state = self.settings.get(ConfigKeys.SPLITTER_STATE)
        if splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(splitter_state.encode()))
        else:
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 1)

    def _load_window_state(self) -> None:
        """
        윈도우 및 하위 위젯 상태 복원

        Logic:
            - 윈도우 크기 및 위치 복원
            - LeftSection 상태 복원
            - RightSection 상태 복원
        """
        # 1. 윈도우 지오메트리 복원
        width = self.settings.get(ConfigKeys.WINDOW_WIDTH, 1400)
        height = self.settings.get(ConfigKeys.WINDOW_HEIGHT, 900)
        self.resize(width, height)

        x = self.settings.get(ConfigKeys.WINDOW_X)
        y = self.settings.get(ConfigKeys.WINDOW_Y)
        if x is not None and y is not None:
            self.move(x, y)

        # 2. Left Section 상태 복원 (설정 파일 구조에 맞춰 데이터 매핑)
        left_section_state = {
            "manual_ctrl": self.settings.get(ConfigKeys.MANUAL_CTRL_STATE, {}),
            "ports": self.settings.get(ConfigKeys.PORTS_TABS_STATE, [])
        }
        self.left_section.load_state(left_section_state)

        # 3. Right Section 상태 복원
        right_section_state = {
            "macro_panel": {
                "commands": self.settings.get(ConfigKeys.MACRO_COMMANDS, []),
                "control_state": self.settings.get(ConfigKeys.MACRO_CONTROL_STATE, {})
            }
        }
        self.right_section.load_state(right_section_state)

    def get_window_state(self) -> dict:
        """
        현재 윈도우 상태 반환

        Returns:
            dict: 윈도우 및 하위 위젯 상태
        """
        state = {}

        # 1. 윈도우 기본 설정
        state[ConfigKeys.WINDOW_WIDTH] = self.width()
        state[ConfigKeys.WINDOW_HEIGHT] = self.height()
        state[ConfigKeys.WINDOW_X] = self.x()
        state[ConfigKeys.WINDOW_Y] = self.y()
        state[ConfigKeys.SPLITTER_STATE] = self.splitter.saveState().toBase64().data().decode()
        state[ConfigKeys.RIGHT_PANEL_VISIBLE] = self.right_section.isVisible()

        # 2. Left Section 상태
        left_state = self.left_section.save_state()
        if 'manual_ctrl' in left_state:
            state[ConfigKeys.MANUAL_CTRL_STATE] = left_state['manual_ctrl']
        if 'ports' in left_state:
            state[ConfigKeys.PORTS_TABS_STATE] = left_state['ports']

        # 3. Right Section 상태
        right_state = self.right_section.save_state()
        if 'macro_panel' in right_state:
            macro_data = right_state['macro_panel']
            state[ConfigKeys.MACRO_COMMANDS] = macro_data.get('commands', [])
            state[ConfigKeys.MACRO_CONTROL_STATE] = macro_data.get('control_state', {})

        return state

    def closeEvent(self, event) -> None:
        """
        종료 이벤트를 처리합니다.
        Presenter에게 종료 요청을 알리고 이벤트를 수락합니다.
        """
        self.close_requested.emit()
        event.accept()

    def _connect_menu_signals(self) -> None:
        """메뉴바 시그널 연결"""
        self.menu_bar.tab_new_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.theme_changed.connect(self.switch_theme)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(lambda lang: lang_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.open_preferences_dialog)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

        self.menu_bar.port_open_requested.connect(self.left_section.open_current_port)
        self.menu_bar.tab_close_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.data_log_save_requested.connect(self.manual_save_log)
        self.menu_bar.toggle_right_panel_requested.connect(self.toggle_right_panel)
        self.menu_bar.file_transfer_requested.connect(self.open_file_transfer_dialog)

    def _connect_toolbar_signals(self) -> None:
        """툴바 시그널 연결"""
        self.main_toolbar.open_requested.connect(self.left_section.open_current_port)
        self.main_toolbar.close_requested.connect(self.left_section.close_current_port)
        self.main_toolbar.clear_requested.connect(self.clear_log)
        self.main_toolbar.data_log_save_requested.connect(self.manual_save_log)
        self.main_toolbar.settings_requested.connect(self.open_preferences_dialog)

    def clear_log(self) -> None:
        """현재 활성 탭의 로그 삭제"""
        if hasattr(self, 'left_section'):
            current_index = self.left_section.port_tabs.currentIndex()
            current_widget = self.left_section.port_tabs.widget(current_index)
            if current_widget and hasattr(current_widget, 'received_area_widget'):
                current_widget.received_area_widget.on_clear_rx_log_clicked()

    def switch_theme(self, theme_name: str) -> None:
        """
        테마 전환

        Args:
            theme_name (str): 테마 이름
        """
        self.theme_manager.apply_theme(QApplication.instance(), theme_name)

        # 테마 설정을 저장
        if hasattr(self, 'settings'):
            self.settings.set(ConfigKeys.THEME, theme_name)

        # 메뉴바의 테마 체크 표시 업데이트
        if hasattr(self, 'menu_bar'):
            self.menu_bar.set_current_theme(theme_name)

        msg = f"Theme changed to {theme_name.capitalize()}"
        self.show_status_message(msg, 2000)

    def open_font_settings_dialog(self) -> None:
        """
        폰트 설정 대화상자를 엽니다.

        Logic:
            - FontSettingsDialog 실행
            - 다이얼로그에서 변경된 내용(ThemeManager 상태)을 가져옴
            - Presenter에 저장 요청 (font_settings_changed 시그널 emit)
            - UI 업데이트
        """
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            # 폰트 설정 가져오기 (ThemeManager는 이미 다이얼로그에 의해 업데이트됨)
            font_settings = self.theme_manager.get_font_settings()

            # Presenter로 변경 사항 전달 (저장 요청)
            # MVP: View는 데이터를 전달만 하고 저장은 Presenter가 담당
            self.font_settings_changed.emit(font_settings)

            # 애플리케이션에 가변폭 폰트 적용 (UI 즉시 반영)
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            self.show_status_message("Font settings updated", 2000)

    def open_preferences_dialog(self) -> None:
        """설정 다이얼로그 열기"""
        current_settings = self.settings.get_all_settings()
        dialog = PreferencesDialog(self, current_settings)
        dialog.settings_changed.connect(self.on_settings_change_requested)
        dialog.exec_()

    def open_about_dialog(self) -> None:
        """정보 다이얼로그 열기"""
        dialog = AboutDialog(self)
        dialog.exec_()

    def open_file_transfer_dialog(self) -> None:
        """파일 전송 대화상자를 엽니다."""
        # 모달리스(Modeless) 다이얼로그로 열어서 메인 윈도우 조작 가능하게 함 (선택 사항)
        # 여기서는 Modal로 열되, Presenter가 제어할 수 있도록 함
        dialog = FileTransferDialog(self)

        # Presenter에 다이얼로그 인스턴스 전달하여 로직 연결
        self.file_transfer_dialog_opened.emit(dialog)

        dialog.exec_()

    def on_settings_change_requested(self, settings: dict) -> None:
        """설정 변경 요청 처리"""
        self.settings_save_requested.emit(settings)

    def on_language_changed(self, lang_code: str) -> None:
        """
        언어 변경 핸들러

        Args:
            lang_code (str): 언어 코드
        """
        self.setWindowTitle(f"{lang_manager.get_text('main_title')} v1.0")

        # 상태바 업데이트
        self.global_status_bar.retranslate_ui()

        # 메뉴 재생성
        self.menu_bar.retranslate_ui()

        # 설정에 언어 저장
        self.settings.set(ConfigKeys.LANGUAGE, lang_code)

    def toggle_right_panel(self, visible: bool) -> None:
        """우측 패널 가시성 토글"""
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
