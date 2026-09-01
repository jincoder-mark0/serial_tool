"""
메인 윈도우 모듈

애플리케이션의 최상위 뷰(View)를 정의합니다.

## WHY
* 전체 UI 레이아웃의 구성 및 관리 책임
* Presenter와의 통신을 위한 단일 진입점(Interface) 제공
* 전역 설정(테마, 언어, 폰트) 및 리소스 초기화의 시각적 반영

## WHAT
* 좌/우 섹션(Section) 배치 및 스플리터(Splitter) 관리
* 메뉴바(MenuBar), 상태바(StatusBar) 관리
* Presenter용 공개 API 제공 (Facade Properties & Methods)
* DTO 기반 상태 관리 (MVP 패턴 준수)
* 다이얼로그(설정, 정보, 파일전송) 호출 관리

## HOW
* QMainWindow를 상속받아 기본 프레임 구성
* MVP 패턴을 위해 비즈니스 로직 없이 시그널(Signal)과 슬롯(Slot)으로 동작
* 하위 위젯 직접 접근을 막기 위해 Property와 Wrapper 메서드 제공
"""
from typing import Optional, Callable

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QShortcut, QMessageBox
)
from PyQt5.QtGui import QKeySequence, QCloseEvent
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QTimer

from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection
from view.sections.main_status_bar import MainStatusBar
from view.sections.main_menu_bar import MainMenuBar

from view.dialogs.font_settings_dialog import FontSettingsDialog
from view.dialogs.about_dialog import AboutDialog
from view.dialogs.preferences_dialog import PreferencesDialog
from view.dialogs.file_transfer_dialog import FileTransferDialog
from common.constants import LAYOUT_MARGIN_DEFAULT, LAYOUT_SPACING_DEFAULT

from view.managers.theme_manager import theme_manager
from view.managers.language_manager import language_manager
from view.managers.color_manager import color_manager

from common.dtos import (
    FontConfig, MainWindowState, PreferencesState,
    PortStatistics, LogDataBatch, SystemLogEvent
)


class MainWindow(QMainWindow):
    """
    메인 윈도우 클래스

    Presenter가 UI 내부 구조를 상세히 알 필요 없이 조작할 수 있도록
    필요한 인터페이스를 프로퍼티와 메서드로 추상화하여 제공합니다.
    """

    close_requested = pyqtSignal()
    settings_save_requested = pyqtSignal(object)
    preferences_requested = pyqtSignal()
    font_settings_changed = pyqtSignal(object)
    theme_change_requested = pyqtSignal(str)
    language_change_requested = pyqtSignal(str)
    shortcut_connect_requested = pyqtSignal()
    shortcut_disconnect_requested = pyqtSignal()
    shortcut_clear_requested = pyqtSignal()
    file_transfer_dialog_opened = pyqtSignal(object, str)
    send_requested = pyqtSignal(object)
    port_tab_added = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        self.language_manager = language_manager
        self.color_manager = color_manager
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")
        self.resize(1400, 900)
        self._saved_left_width: Optional[int] = None
        self._saved_window_width: Optional[int] = None
        self._right_section_width: Optional[int] = None
        self.init_ui()
        self.menu_bar = MainMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_signals()
        self.init_shortcuts()
        self.language_manager.language_changed.connect(self.on_language_changed)

    def init_ui(self) -> None:
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
            LAYOUT_MARGIN_DEFAULT,
        )
        main_layout.setSpacing(LAYOUT_SPACING_DEFAULT)
        self.splitter = QSplitter(Qt.Horizontal)
        self.left_section = MainLeftSection()
        self.right_section = MainRightSection()
        self.splitter.addWidget(self.left_section)
        self.splitter.addWidget(self.right_section)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.left_section.send_requested.connect(self.send_requested.emit)
        self.left_section.port_tab_added.connect(self.port_tab_added.emit)
        main_layout.addWidget(self.splitter)
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    def apply_state(self, state: MainWindowState, font_config: FontConfig) -> None:
        if font_config:
            self.theme_manager.set_proportional_font(
                font_config.prop_family, font_config.prop_size, apply_now=False
            )
            self.theme_manager.set_fixed_font(
                font_config.fixed_family, font_config.fixed_size, apply_now=False
            )
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)
            self.theme_manager.apply_theme(self.theme_manager.get_current_theme())

        if state:
            if state.width > 0 and state.height > 0:
                self.resize(state.width, state.height)
            if state.x is not None and state.y is not None:
                self.move(state.x, state.y)
            self.menu_bar.set_right_section_checked(state.right_panel_visible)
            self.right_section.setVisible(state.right_panel_visible)
            self._right_section_width = state.right_section_width
            if state.splitter_state:
                try:
                    self.splitter.restoreState(
                        QByteArray.fromBase64(state.splitter_state.encode())
                    )
                except Exception:
                    pass
            else:
                self.splitter.setStretchFactor(0, 1)
                self.splitter.setStretchFactor(1, 1)
            self.left_section.apply_state(state.left_section_state)
            self.right_section.apply_state(state.right_section_state)

    def apply_proportional_font_size(self, size: int) -> None:
        """현재 proportional font family를 유지하며 크기를 즉시 적용합니다."""
        family, _ = self.theme_manager.get_proportional_font_info()
        self.theme_manager.set_proportional_font(family, size)

    def get_window_state(self) -> MainWindowState:
        state = MainWindowState()
        state.width = self.width()
        state.height = self.height()
        state.x = self.x()
        state.y = self.y()
        state.splitter_state = self.splitter.saveState().toBase64().data().decode()
        state.right_panel_visible = self.right_section.isVisible()
        if self.right_section.isVisible():
            state.right_section_width = self.right_section.width()
        else:
            state.right_section_width = getattr(self, '_right_section_width', None)
        state.left_section_state = self.left_section.get_state()
        state.right_section_state = self.right_section.get_state()
        return state

    @property
    def port_view(self) -> MainLeftSection:
        return self.left_section

    @property
    def macro_view(self):
        return self.right_section.macro_panel

    @property
    def packet_view(self):
        return self.right_section.packet_panel

    @property
    def manual_control_view(self):
        return self.left_section.manual_control_panel

    def is_current_port_connected(self) -> bool:
        if hasattr(self.left_section, 'is_current_port_connected'):
            return self.left_section.is_current_port_connected()
        return False

    def connect_port_tab_changed(self, slot: Callable[[int], None]) -> None:
        if hasattr(self.left_section, 'connect_tab_changed_signal'):
            self.left_section.connect_tab_changed_signal(slot)

    def get_port_tabs_count(self) -> int:
        return self.left_section.get_port_tabs_count()

    def get_port_tab_widget(self, index: int) -> QWidget:
        return self.left_section.get_port_panel_at(index)

    def log_system_message(self, event: SystemLogEvent) -> None:
        self.left_section.log_system_message(event)

    def update_status_bar_stats(self, stats: PortStatistics) -> None:
        self.global_status_bar.update_statistics(stats)

    def update_status_bar_time(self, time_str: str) -> None:
        self.global_status_bar.update_time(time_str)

    def update_status_bar_port(self, port_name: str, connected: bool) -> None:
        self.global_status_bar.update_port_status(port_name, connected)

    def show_status_message(self, message: str, timeout: int = 0) -> None:
        self.global_status_bar.show_message(message, timeout)

    def show_alert_message(self, title: str, message: str) -> None:
        QTimer.singleShot(0, lambda: QMessageBox.warning(self, title, message))

    def manual_save_log(self) -> None:
        self.left_section.trigger_current_port_log_save()

    def append_local_echo_data(self, data: bytes) -> None:
        self.left_section.append_data_to_current_port(data)

    def append_rx_data(self, batch: LogDataBatch) -> None:
        self.left_section.append_rx_data(batch)

    def init_shortcuts(self) -> None:
        self.shortcut_connect = QShortcut(QKeySequence("F2"), self)
        self.shortcut_connect.activated.connect(self.shortcut_connect_requested.emit)
        self.shortcut_disconnect = QShortcut(QKeySequence("F3"), self)
        self.shortcut_disconnect.activated.connect(self.shortcut_disconnect_requested.emit)
        self.shortcut_clear = QShortcut(QKeySequence("F5"), self)
        self.shortcut_clear.activated.connect(self.shortcut_clear_requested.emit)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.close_requested.emit()
        event.accept()

    def _connect_menu_signals(self) -> None:
        self.menu_bar.tab_new_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.connect_requested.connect(self.shortcut_connect_requested.emit)
        self.menu_bar.tab_close_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.data_log_save_requested.connect(self.manual_save_log)
        self.menu_bar.theme_changed.connect(self.theme_change_requested.emit)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(self.language_change_requested.emit)
        self.menu_bar.preferences_requested.connect(self.preferences_requested.emit)
        self.menu_bar.toggle_right_section_requested.connect(self.toggle_right_section)
        self.menu_bar.file_transfer_requested.connect(self.open_file_transfer_dialog)
        self.menu_bar.about_requested.connect(self.open_about_dialog)

    def clear_log(self) -> None:
        self.left_section.clear_current_port_log()

    def switch_theme(self, theme_name: str) -> None:
        self.theme_manager.apply_theme(theme_name)
        self.color_manager.apply_theme(theme_name)
        if hasattr(self.left_section, 'port_tab_panel') and self.left_section.port_tab_panel:
            self.left_section.port_tab_panel.update_plus_tab_icon()
        if hasattr(self, 'menu_bar'):
            self.menu_bar.set_current_theme(theme_name)
        if hasattr(self.left_section, 'set_system_log_color_rules'):
            self.left_section.set_system_log_color_rules(self.color_manager.rules)
        msg = f"Theme changed to {theme_name.capitalize()}"
        self.show_status_message(msg, 2000)

    def open_font_settings_dialog(self) -> None:
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            font_config = self.theme_manager.get_font_settings()
            self.font_settings_changed.emit(font_config)
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)
            self.show_status_message("Font settings updated", 2000)

    def open_preferences_dialog(self, state: PreferencesState) -> None:
        dialog = PreferencesDialog(self, state)
        dialog.settings_changed.connect(self.on_settings_change_requested)
        dialog.exec_()

    def open_about_dialog(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec_()

    def open_file_transfer_dialog(self) -> None:
        target_port = self.left_section.get_current_port_name()
        dialog = FileTransferDialog(self)
        self.file_transfer_dialog_opened.emit(dialog, target_port)
        dialog.exec_()

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        self.settings_save_requested.emit(new_state)

    def on_language_changed(self, language_code: Optional[str] = None) -> None:
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")
        if hasattr(self, 'global_status_bar'):
            self.global_status_bar.retranslate_ui()
        if hasattr(self, 'menu_bar'):
            self.menu_bar.retranslate_ui()

    def _refresh_layout_constraints(self) -> None:
        """숨김/표시 직후 창의 레이아웃 최소 크기를 즉시 재계산합니다.

        WHY:
            Qt의 레이아웃 무효화는 지연된다. `right_section.setVisible(False)` 직후에는
            splitter와 상위 레이아웃이 아직 우측 섹션의 최소 폭
            (`CONTROL_MIN_WIDTH_RIGHT_SECTION`)을 품고 있어, 창의 최소 폭이 줄어들지
            않은 상태다. 그 시점의 `resize()`는 **옛 최소 폭에 클램프되어 무시**된다.

            결과가 사용자가 본 증상이다 — 패널을 숨겨도 창 크기는 그대로고, 대신
            좌측 섹션이 빈자리를 차지하며 넓어져 내부 컴포넌트 크기가 바뀐다.
            실측(offscreen): 창 3838 유지, 좌측 3244 -> 3828.

        HOW:
            바뀐 위젯에서 창까지 레이아웃 사슬을 아래에서 위로 무효화하고 즉시
            activate한다. 사슬 중 하나라도 빠지면 캐시된 최소 크기가 남아 클램프가
            그대로 일어난다 — splitter만, 또는 최상위 레이아웃만 갱신해서는 듣지 않는다.
        """
        self.splitter.updateGeometry()
        for layout in (self.centralWidget().layout(), self.layout()):
            if layout is not None:
                layout.invalidate()
                layout.activate()

    def toggle_right_section(self, visible: bool) -> None:
        if self.isMaximized():
            self.right_section.setVisible(visible)
            self.menu_bar.set_right_section_checked(visible)
            return

        current_width = self.width()
        handle_width = self.splitter.handleWidth()
        self.setUpdatesEnabled(False)
        try:
            if visible:
                if self._right_section_width is not None:
                    target_right_width = self._right_section_width
                else:
                    target_right_width = max(int(self.width() * 0.3), 300)
                if self._saved_left_width is not None:
                    left_width = self._saved_left_width
                else:
                    left_width = self.left_section.width()
                if self._saved_window_width is not None:
                    self.resize(self._saved_window_width, self.height())
                else:
                    self.resize(
                        current_width + target_right_width + handle_width,
                        self.height(),
                    )
                self.right_section.setVisible(True)
                self.splitter.setSizes([left_width, target_right_width])
                self._saved_left_width = None
                self._saved_window_width = None
                self._right_section_width = None
            else:
                self._right_section_width = self.right_section.width()
                self._saved_left_width = self.left_section.width()
                self._saved_window_width = self.width()
                margins = self.centralWidget().layout().contentsMargins()
                total_margin = margins.left() + margins.right()
                new_window_width = self.left_section.width() + total_margin
                self.right_section.setVisible(False)
                self._refresh_layout_constraints()
                self.resize(new_window_width, self.height())
            self.menu_bar.set_right_section_checked(visible)
        finally:
            self.setUpdatesEnabled(True)
