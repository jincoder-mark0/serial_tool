"""
메인 윈도우 모듈

애플리케이션의 최상위 뷰를 정의합니다.

## WHY
* 전체 UI 레이아웃 구성 및 관리
* Presenter와의 인터페이스(Signal/Slot) 제공
* 전역 설정 및 리소스 초기화

## WHAT
* 섹션(Section) 배치 및 스플리터 관리
* 메뉴바, 상태바 관리
* Presenter용 공개 API 제공
* 경고 메시지창 표시 기능

## HOW
* QMainWindow 상속
* MVP 패턴을 위한 시그널 노출
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QShortcut, QMessageBox
)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray

from view.sections import (
    MainLeftSection, MainRightSection, MainStatusBar, MainMenuBar
)
from view.dialogs import (
    FontSettingsDialog, AboutDialog, PreferencesDialog, FileTransferDialog
)
from view.managers.theme_manager import ThemeManager
from view.managers.language_manager import language_manager
from common.constants import ConfigKeys
from common.dtos import FontConfig, ManualCommand, MainWindowState, PreferencesState

class MainWindow(QMainWindow):
    """
    메인 윈도우 클래스

    Presenter가 UI 내부 구조를 알 필요 없이 조작할 수 있도록
    필요한 인터페이스를 프로퍼티와 메서드로 제공합니다.
    """

    # Presenter 전달용 시그널
    close_requested = pyqtSignal()
    settings_save_requested = pyqtSignal(object) # PreferencesState
    preferences_requested = pyqtSignal()

    # FontConfig DTO 전달을 위해 object로 변경
    font_settings_changed = pyqtSignal(object)

    # 단축키 시그널
    shortcut_connect_requested = pyqtSignal()
    shortcut_disconnect_requested = pyqtSignal()
    shortcut_clear_requested = pyqtSignal()

    # 파일 전송 시그널
    file_transfer_dialog_opened = pyqtSignal(object)

    # 하위 컴포넌트 시그널 중계
    send_requested = pyqtSignal(object)
    port_tab_added = pyqtSignal(object)

    def __init__(self) -> None:
        """
        MainWindow 초기화

        MVP 원칙에 따라 Model/Core(SettingsManager)를 직접 생성하지 않습니다.
        초기 상태 복원은 Presenter가 restore_state()를 호출하여 수행합니다.
        """
        super().__init__()

        # ThemeManager는 View Helper로서 사용 (싱글톤)
        self.theme_manager = ThemeManager()

        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")
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

        # 단축키 초기화
        self.init_shortcuts()

        # 언어 변경 시그널 연결
        language_manager.language_changed.connect(self.on_language_changed)

    def init_ui(self) -> None:
        """UI 레이아웃 및 컴포넌트 초기화"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 스플리터 구성 (좌: 포트/제어, 우: 커맨드/인스펙터)
        self.splitter = QSplitter(Qt.Horizontal)

        self.left_section = MainLeftSection()
        self.right_section = MainRightSection()

        self.splitter.addWidget(self.left_section)
        self.splitter.addWidget(self.right_section)

        # 기본 비율 설정
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # 왼쪽 패널이 완전히 사라지는 것을 방지 (Collapsible False)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)

        # 시그널 체이닝 (하위 -> 상위)
        self.left_section.send_requested.connect(self.send_requested.emit)
        self.left_section.port_tab_added.connect(self.port_tab_added.emit)

        main_layout.addWidget(self.splitter)

        # 전역 상태바 설정 (위젯 사용)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    # --------------------------------------------------------
    # State Management (MVP Support)
    # --------------------------------------------------------
    def apply_state(self, state: MainWindowState, font_config: FontConfig) -> None:
        """
        Presenter로부터 전달받은 상태 DTO를 UI에 적용합니다.

        Logic:
            - 폰트, 테마 적용
            - 윈도우 크기 및 위치 복원
            - 패널 및 스플리터 상태 복원
            - 하위 섹션 상태 복원

        Args:
            state (MainWindowState): 메인 윈도우 상태 DTO
            font_config (FontConfig): 폰트 설정 DTO (별도 분리 가능)
        """
        # 1. 폰트 적용
        self.theme_manager.set_proportional_font(font_config.prop_family, font_config.prop_size)
        self.theme_manager.set_fixed_font(font_config.fixed_family, font_config.fixed_size)

        prop_font = self.theme_manager.get_proportional_font()
        QApplication.instance().setFont(prop_font)

        # 2. 윈도우 지오메트리
        self.resize(state.width, state.height)
        if state.x is not None and state.y is not None:
            self.move(state.x, state.y)

        # 3. 우측 패널 표시 상태
        self.menu_bar.set_right_section_checked(state.right_panel_visible)
        self.right_section.setVisible(state.right_panel_visible)
        self._saved_right_width = state.saved_right_width

        # 4. 스플리터 상태
        if state.splitter_state:
            try:
                self.splitter.restoreState(QByteArray.fromBase64(state.splitter_state.encode()))
            except Exception:
                pass
        else:
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 1)

        # 5. 하위 섹션 상태 복원
        # Sub-panel 상태는 딕셔너리로 전달됨 (DTO 내부 field)
        self.left_section.load_state(state.left_section_state)
        self.right_section.load_state(state.right_section_state)

    def get_window_state(self) -> MainWindowState:
        """
        현재 윈도우 상태를 DTO로 반환

        Returns:
            MainWindowState: 윈도우 및 하위 위젯 상태 DTO
        """
        state = MainWindowState()

        # 1. 윈도우 기본 설정
        state.width = self.width()
        state.height = self.height()
        state.x = self.x()
        state.y = self.y()
        state.splitter_state = self.splitter.saveState().toBase64().data().decode()
        state.right_panel_visible = self.right_section.isVisible()

        if self.right_section.isVisible():
            state.saved_right_width = self.right_section.width()
        else:
            state.saved_right_width = getattr(self, '_saved_right_width', None)

        # 2. 하위 섹션 상태 (딕셔너리로 수집)
        state.left_section_state = self.left_section.save_state()
        state.right_section_state = self.right_section.save_state()

        return state

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
        return self.left_section.port_tab_panel.count()

    def get_port_tab_widget(self, index: int) -> QWidget:
        """
        인덱스에 해당하는 포트 탭 위젯 반환

        Args:
            index (int): 탭 인덱스

        Returns:
            QWidget: 포트 패널 위젯
        """
        return self.left_section.port_tab_panel.widget(index)

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

    def show_alert_message(self, title: str, message: str) -> None:
        """
        경고(Alert) 다이얼로그를 표시합니다.

        Args:
            title (str): 다이얼로그 제목
            message (str): 표시할 내용
        """
        QMessageBox.warning(self, title, message)

    def manual_save_log(self) -> None:
        """로그 저장 다이얼로그 호출"""
        current_index = self.left_section.port_tab_panel.currentIndex()
        current_widget = self.left_section.port_tab_panel.widget(current_index)
        if hasattr(current_widget, 'data_log_widget'):
            current_widget.data_log_widget.on_data_log_logging_toggled(True)

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
        self.shortcut_connect = QShortcut(QKeySequence("F2"), self)
        self.shortcut_connect.activated.connect(self.shortcut_connect_requested.emit)

        self.shortcut_disconnect = QShortcut(QKeySequence("F3"), self)
        self.shortcut_disconnect.activated.connect(self.shortcut_disconnect_requested.emit)

        self.shortcut_clear = QShortcut(QKeySequence("F5"), self)
        self.shortcut_clear.activated.connect(self.shortcut_clear_requested.emit)

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
        self.menu_bar.language_changed.connect(lambda lang: language_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.preferences_requested.emit)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

        self.menu_bar.port_open_requested.connect(self.left_section.open_current_port)
        self.menu_bar.tab_close_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.data_log_save_requested.connect(self.manual_save_log)
        self.menu_bar.toggle_right_section_requested.connect(self.toggle_right_section)
        self.menu_bar.file_transfer_requested.connect(self.open_file_transfer_dialog)

    def clear_log(self) -> None:
        """현재 활성 탭의 로그 삭제"""
        if hasattr(self, 'left_section'):
            current_index = self.left_section.port_tab_panel.currentIndex()
            current_widget = self.left_section.port_tab_panel.widget(current_index)
            if current_widget and hasattr(current_widget, 'data_log_widget'):
                current_widget.data_log_widget.on_clear_data_log_clicked()

    def switch_theme(self, theme_name: str) -> None:
        """
        테마 전환

        Args:
            theme_name (str): 테마 이름
        """
        self.theme_manager.apply_theme(QApplication.instance(), theme_name)
        # 설정 저장은 Presenter에서 담당 (settings_changed 시그널 등 사용 시)
        # 하지만 메뉴를 통한 즉시 변경은 여기서 UI 업데이트만 수행하고
        # 저장은 MainPresenter의 on_settings_change_requested 등에서 처리하거나
        # 별도 시그널을 보내야 함. MVP 원칙상 View는 저장하지 않음.

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
            # 폰트 설정 가져오기
            font_config = self.theme_manager.get_font_settings()
            self.font_settings_changed.emit(font_config)

            # 애플리케이션에 가변폭 폰트 적용 (UI 즉시 반영)
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            self.show_status_message("Font settings updated", 2000)

    def open_preferences_dialog(self, state: PreferencesState) -> None:
        """
        설정 다이얼로그 열기 (DTO 주입)

        Args:
            state (PreferencesState): 설정 상태
        """
        dialog = PreferencesDialog(self, state)
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

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        """
        설정 변경 요청 처리

        Args:
            new_state (PreferencesState): 변경된 설정 상태
        """
        self.settings_save_requested.emit(new_state)

    def on_language_changed(self, language_code: str) -> None:
        """
        언어 변경 핸들러

        Args:
            language_code (str): 언어 코드
        """
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")

        # 상태바 업데이트
        self.global_status_bar.retranslate_ui()

        # 메뉴 재생성
        self.menu_bar.retranslate_ui()
        # 설정 저장은 Presenter에게 시그널로 요청해야 하나,
        # 언어 변경은 즉시성을 위해 LanguageManager가 Signal을 보냄.
        # 영속성을 위해 Presenter에 알림 필요 (settings_save_requested 사용 가능)

    def toggle_right_section(self, visible: bool) -> None:
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
                target_right_width = max(int(self.width() * 0.3), 300)

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
            self._saved_right_width = self.right_section.width()

            # 왼쪽 패널의 현재 너비를 기준으로 윈도우 크기 재조정
            # 중앙 위젯의 좌우 마진을 동적으로 계산
            margins = self.centralWidget().layout().contentsMargins()
            total_margin = margins.left() + margins.right()

            new_window_width = self.left_section.width() + total_margin
            self.right_section.setVisible(False)
            self.resize(new_window_width, self.height())
