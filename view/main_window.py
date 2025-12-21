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
* Presenter용 공개 API 제공 및 DTO 기반 상태 관리 (MVP 패턴 준수)
* 다이얼로그(설정, 정보, 파일전송) 호출 관리

## HOW
* QMainWindow를 상속받아 기본 프레임 구성
* MVP 패턴을 위해 비즈니스 로직 없이 시그널(Signal)과 슬롯(Slot)으로 동작
* apply_state/get_window_state 메서드를 통해 상태 데이터 교환
"""
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QShortcut, QMessageBox
)
from PyQt5.QtGui import QKeySequence, QCloseEvent
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray

from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection
from view.sections.main_status_bar import MainStatusBar
from view.sections.main_menu_bar import MainMenuBar

from view.dialogs.font_settings_dialog import FontSettingsDialog
from view.dialogs.about_dialog import AboutDialog
from view.dialogs.preferences_dialog import PreferencesDialog
from view.dialogs.file_transfer_dialog import FileTransferDialog

from view.managers.theme_manager import theme_manager
from view.managers.language_manager import language_manager

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

    # -------------------------------------------------------------------------
    # Signals (Presenter 통신용)
    # -------------------------------------------------------------------------
    # 종료 및 설정 저장 요청
    close_requested = pyqtSignal()
    settings_save_requested = pyqtSignal(object)  # PreferencesState DTO 전달
    preferences_requested = pyqtSignal()

    # 폰트 설정 변경 (FontConfig DTO 전달)
    font_settings_changed = pyqtSignal(object)

    # 전역 단축키 시그널
    shortcut_connect_requested = pyqtSignal()
    shortcut_disconnect_requested = pyqtSignal()
    shortcut_clear_requested = pyqtSignal()

    # 파일 전송 다이얼로그 오픈 알림 (Presenter 연결용)
    file_transfer_dialog_opened = pyqtSignal(object)

    # 하위 컴포넌트 시그널 중계 (Bubbling)
    send_requested = pyqtSignal(object)      # ManualCommand DTO
    port_tab_added = pyqtSignal(object)      # PortPanel Widget

    def __init__(self) -> None:
        """
        MainWindow를 초기화합니다.

        MVP 원칙에 따라 Model/Core(SettingsManager)를 직접 생성하지 않습니다.
        초기 상태 복원은 Presenter가 apply_state()를 호출하여 수행합니다.
        """
        super().__init__()

        # ThemeManager는 View Helper로서 사용 (싱글톤 인스턴스)
        self.theme_manager = theme_manager
        self.language_manager = language_manager

        # 기본 타이틀 및 크기 설정
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")
        self.resize(1400, 900)

        # 우측 패널 숨김/복원 시 왼쪽 패널 너비 저장용 변수
        self._saved_left_width: Optional[int] = None
        self._right_section_width: Optional[int] = None

        # UI 초기화
        self.init_ui()

        # 메뉴바 초기화
        self.menu_bar = MainMenuBar(self)
        self.setMenuBar(self.menu_bar)
        self._connect_menu_signals()

        # 단축키 초기화
        self.init_shortcuts()

        # 언어 변경 시그널 연결 (동적 번역)
        self.language_manager.language_changed.connect(self.on_language_changed)

    def init_ui(self) -> None:
        """
        UI 레이아웃 및 주요 컴포넌트를 초기화합니다.

        Logic:
            1. 중앙 위젯 및 메인 레이아웃 생성
            2. 좌(포트/제어)/우(매크로/분석) 섹션 생성
            3. QSplitter를 사용하여 섹션 배치 및 비율 설정
            4. 하위 섹션의 시그널을 MainWindow 시그널로 연결 (Chaining)
            5. 전역 상태바 설정
        """
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

        # 기본 비율 설정 (1:1)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        # 왼쪽 패널이 완전히 사라지는 것을 방지 (Collapsible False)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)

        # 시그널 체이닝 (하위 -> 상위)
        self.left_section.send_requested.connect(self.send_requested.emit)
        self.left_section.port_tab_added.connect(self.port_tab_added.emit)

        main_layout.addWidget(self.splitter)

        # 전역 상태바 설정
        self.global_status_bar = MainStatusBar()
        self.setStatusBar(self.global_status_bar)

    # --------------------------------------------------------
    # State Management (MVP Support)
    # --------------------------------------------------------
    def apply_state(self, state: MainWindowState, font_config: FontConfig) -> None:
        """
        Presenter로부터 전달받은 상태 DTO를 UI에 적용합니다.

        Logic:
            1. 폰트 및 테마 적용
            2. 윈도우 크기 및 위치 복원
            3. 우측 패널 표시 여부 및 스플리터 상태 복원
            4. 하위 섹션(Left/Right)에 상태 복원 위임

        Args:
            state (MainWindowState): 메인 윈도우 상태 DTO.
            font_config (FontConfig): 폰트 설정 DTO.
        """
        # 1. 폰트 적용 (ThemeManager 위임)
        if font_config:
            self.theme_manager.set_proportional_font(font_config.prop_family, font_config.prop_size, apply_now=False)
            self.theme_manager.set_fixed_font(font_config.fixed_family, font_config.fixed_size, apply_now=False)

            # 애플리케이션 전체 폰트 적용 (Proportional Font 기준)
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            # 확실하게 적용하기 위해 현재 테마로 1회 갱신:
            self.theme_manager.apply_theme(self.theme_manager.get_current_theme())

        # 2. 윈도우 지오메트리 복원
        if state:
            if state.width > 0 and state.height > 0:
                self.resize(state.width, state.height)
            if state.x is not None and state.y is not None:
                self.move(state.x, state.y)

            # 3. 우측 패널 표시 상태 복원
            self.menu_bar.set_right_section_checked(state.right_panel_visible)
            self.right_section.setVisible(state.right_panel_visible)
            self._right_section_width = state.right_section_width

            # 4. 스플리터 상태 복원
            if state.splitter_state:
                try:
                    self.splitter.restoreState(QByteArray.fromBase64(state.splitter_state.encode()))
                except Exception:
                    pass
            else:
                # 기본 비율 설정
                self.splitter.setStretchFactor(0, 1)
                self.splitter.setStretchFactor(1, 1)

            # 5. 하위 섹션 상태 복원
            self.left_section.apply_state(state.left_section_state)
            self.right_section.apply_state(state.right_section_state)

    def get_window_state(self) -> MainWindowState:
        """
        현재 윈도우 및 하위 UI의 상태를 DTO로 반환합니다.
        (설정 저장을 위해 Presenter가 호출)

        Returns:
            MainWindowState: 윈도우 및 하위 위젯 상태 DTO.
        """
        state = MainWindowState()

        # 1. 윈도우 기본 정보 수집
        state.width = self.width()
        state.height = self.height()
        state.x = self.x()
        state.y = self.y()
        state.splitter_state = self.splitter.saveState().toBase64().data().decode()
        state.right_panel_visible = self.right_section.isVisible()

        # 우측 패널 너비 저장 (보일 때만 갱신)
        if self.right_section.isVisible():
            state.right_section_width = self.right_section.width()
        else:
            state.right_section_width = getattr(self, '_right_section_width', None)

        # 2. 하위 섹션 상태 수집 (Recursive)
        state.left_section_state = self.left_section.get_state()
        state.right_section_state = self.right_section.get_state()

        return state

    # --------------------------------------------------------
    # Presenter Interface (View 인터페이스)
    # --------------------------------------------------------
    @property
    def port_view(self):
        """PortPresenter용 뷰 인터페이스 반환."""
        return self.left_section

    @property
    def macro_view(self):
        """MacroPresenter용 뷰 인터페이스 반환."""
        return self.right_section.macro_panel

    def get_port_tabs_count(self) -> int:
        """현재 열려있는 포트 탭의 개수를 반환합니다."""
        return self.left_section.port_tab_panel.count()

    def get_port_tab_widget(self, index: int) -> QWidget:
        """
        인덱스에 해당하는 포트 탭 위젯을 반환합니다.

        Args:
            index (int): 탭 인덱스.

        Returns:
            QWidget: 포트 패널 위젯.
        """
        return self.left_section.port_tab_panel.widget(index)

    def log_system_message(self, event: SystemLogEvent) -> None:
        """
        시스템 로그 위젯에 메시지를 추가합니다.

        Args:
            event (SystemLogEvent): 시스템 로그 이벤트 DTO.
        """
        self.left_section.system_log_widget.append_log(event)

    def update_status_bar_stats(self, stats: PortStatistics) -> None:
        """
        상태바의 통계(RX/TX/Error) 정보를 업데이트합니다.

        Args:
            stats (PortStatistics): 통계 정보 DTO.
        """
        self.global_status_bar.update_statistics(stats)

    def update_status_bar_time(self, time_str: str) -> None:
        """
        상태바의 현재 시간을 업데이트합니다.

        Args:
            time_str (str): 포맷팅된 시간 문자열.
        """
        self.global_status_bar.update_time(time_str)

    def update_status_bar_port(self, port_name: str, connected: bool) -> None:
        """
        상태바의 포트 연결 상태 표시를 업데이트합니다.

        Args:
            port_name (str): 포트 이름.
            connected (bool): 연결 여부.
        """
        self.global_status_bar.update_port_status(port_name, connected)

    def show_status_message(self, message: str, timeout: int = 0) -> None:
        """
        상태바에 임시 메시지를 표시합니다.

        Args:
            message (str): 표시할 메시지.
            timeout (int): 표시 시간(ms). 0이면 계속 표시.
        """
        self.global_status_bar.show_message(message, timeout)

    def show_alert_message(self, title: str, message: str) -> None:
        """
        경고(Alert) 메시지 박스를 표시합니다.

        Args:
            title (str): 다이얼로그 제목.
            message (str): 표시할 내용.
        """
        QMessageBox.warning(self, title, message)

    def manual_save_log(self) -> None:
        """
        현재 활성 탭의 로그 저장 다이얼로그를 호출합니다.
        (메뉴바의 'Save Log' 액션 핸들러)
        """
        current_index = self.left_section.port_tab_panel.currentIndex()
        current_widget = self.left_section.port_tab_panel.widget(current_index)
        if hasattr(current_widget, 'data_log_widget'):
            # DataLogWidget의 로깅 토글 슬롯을 강제로 호출하여 저장 로직 수행
            current_widget.data_log_widget.on_data_log_logging_toggled(True)

    def append_local_echo_data(self, data: bytes) -> None:
        """
        Local Echo 데이터를 현재 활성화된 포트 탭에 추가합니다.
        (송신 데이터를 수신창에 표시)

        Args:
            data (bytes): 표시할 송신 데이터.
        """
        self.left_section.append_data_to_current_port(data)

    def append_rx_data(self, batch: LogDataBatch) -> None:
        """
        수신된 데이터를 해당 포트의 로그 뷰어에 추가합니다.
        (Fast Path를 통한 UI 업데이트)

        Logic:
            - DTO를 LeftSection으로 전달 (포트 탭 관리 책임 위임)

        Args:
            batch (LogDataBatch): 로그 데이터 배치 DTO.
        """
        self.left_section.append_rx_data(batch)

    # --------------------------------------------------------
    # 내부 로직 (Internal Logic)
    # --------------------------------------------------------
    def init_shortcuts(self) -> None:
        """전역 단축키를 초기화하고 시그널을 연결합니다."""
        # F2: 연결
        self.shortcut_connect = QShortcut(QKeySequence("F2"), self)
        self.shortcut_connect.activated.connect(self.shortcut_connect_requested.emit)

        # F3: 연결 해제
        self.shortcut_disconnect = QShortcut(QKeySequence("F3"), self)
        self.shortcut_disconnect.activated.connect(self.shortcut_disconnect_requested.emit)

        # F5: 로그 지우기
        self.shortcut_clear = QShortcut(QKeySequence("F5"), self)
        self.shortcut_clear.activated.connect(self.shortcut_clear_requested.emit)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        윈도우 종료 이벤트를 처리합니다.

        Logic:
            - Presenter에게 종료 요청 시그널(close_requested) 발송
            - Presenter가 설정 저장 및 리소스 정리를 수행하도록 함
            - 이벤트를 수락하여 종료 진행

        Args:
            event (QCloseEvent): 종료 이벤트.
        """
        self.close_requested.emit()
        event.accept()

    def _connect_menu_signals(self) -> None:
        """
        메뉴바의 액션 시그널을 내부 메서드 또는 외부 시그널에 연결합니다.
        """
        # File Menu
        self.menu_bar.tab_new_requested.connect(self.left_section.add_new_port_tab)
        self.menu_bar.exit_requested.connect(self.close)
        self.menu_bar.connect_requested.connect(self.left_section.open_current_port)
        self.menu_bar.tab_close_requested.connect(self.left_section.close_current_tab)
        self.menu_bar.data_log_save_requested.connect(self.manual_save_log)

        # View Menu
        self.menu_bar.theme_changed.connect(self.switch_theme)
        self.menu_bar.font_settings_requested.connect(self.open_font_settings_dialog)
        self.menu_bar.language_changed.connect(lambda lang: language_manager.set_language(lang))
        self.menu_bar.preferences_requested.connect(self.preferences_requested.emit)
        self.menu_bar.toggle_right_section_requested.connect(self.toggle_right_section)

        # Tools Menu
        self.menu_bar.file_transfer_requested.connect(self.open_file_transfer_dialog)

        # Help Menu
        self.menu_bar.about_requested.connect(self.open_about_dialog)

    def clear_log(self) -> None:
        """현재 활성 탭의 로그를 삭제합니다 (단축키 처리용)."""
        if hasattr(self, 'left_section'):
            current_index = self.left_section.port_tab_panel.currentIndex()
            current_widget = self.left_section.port_tab_panel.widget(current_index)
            if current_widget and hasattr(current_widget, 'data_log_widget'):
                current_widget.data_log_widget.on_clear_data_log_clicked()

    def switch_theme(self, theme_name: str) -> None:
        """
        애플리케이션 테마를 전환합니다.

        Logic:
            - ThemeManager를 통해 테마 적용 (theme_name 전달)
            - 메뉴바의 테마 체크 상태 동기화
            - 상태바 메시지 출력

        Args:
            theme_name (str): 테마 이름 (예: 'dark', 'light').
        """
        # 인자 개수 오류 수정: QApplication.instance() 제거
        self.theme_manager.apply_theme(theme_name)

        # 메뉴바의 테마 체크 표시 업데이트
        if hasattr(self, 'menu_bar'):
            self.menu_bar.set_current_theme(theme_name)

        msg = f"Theme changed to {theme_name.capitalize()}"
        self.show_status_message(msg, 2000)

    def open_font_settings_dialog(self) -> None:
        """
        폰트 설정 대화상자를 엽니다.

        Logic:
            - FontSettingsDialog 실행 (Modal)
            - 다이얼로그 종료 후 변경 사항이 있으면 시그널(font_settings_changed) 발행
            - UI에 즉시 반영
        """
        dialog = FontSettingsDialog(self.theme_manager, self)
        if dialog.exec_():
            # 폰트 설정 DTO 획득
            font_config = self.theme_manager.get_font_settings()
            self.font_settings_changed.emit(font_config)

            # 애플리케이션에 가변폭 폰트 적용 (UI 즉시 반영)
            prop_font = self.theme_manager.get_proportional_font()
            QApplication.instance().setFont(prop_font)

            self.show_status_message("Font settings updated", 2000)

    def open_preferences_dialog(self, state: PreferencesState) -> None:
        """
        설정 대화상자를 엽니다.

        Args:
            state (PreferencesState): 현재 설정 상태 DTO.
        """
        dialog = PreferencesDialog(self, state)
        # 설정 변경 시그널을 MainWindow 핸들러로 연결
        dialog.settings_changed.connect(self.on_settings_change_requested)
        dialog.exec_()

    def open_about_dialog(self) -> None:
        """정보(About) 대화상자를 엽니다."""
        dialog = AboutDialog(self)
        dialog.exec_()

    def open_file_transfer_dialog(self) -> None:
        """
        파일 전송 대화상자를 엽니다.

        Logic:
            - 다이얼로그 생성
            - Presenter에 다이얼로그 인스턴스를 전달하여 로직 연결 (Signal)
            - 다이얼로그 실행
        """
        dialog = FileTransferDialog(self)
        self.file_transfer_dialog_opened.emit(dialog)
        dialog.exec_()

    def on_settings_change_requested(self, new_state: PreferencesState) -> None:
        """
        설정 대화상자에서 변경 요청이 왔을 때 중계합니다.

        Args:
            new_state (PreferencesState): 변경된 설정 상태 DTO.
        """
        self.settings_save_requested.emit(new_state)

    def on_language_changed(self, language_code: Optional[str] = None) -> None:
        """
        언어 변경 시 UI 텍스트를 업데이트합니다.

        Args:
            language_code (Optional[str]): 변경된 언어 코드 (사용되지 않더라도 시그널 호환성을 위해 유지).
        """
        self.setWindowTitle(f"{language_manager.get_text('main_title')} v1.0")

        # 상태바 및 메뉴바 재번역
        if hasattr(self, 'global_status_bar'):
            self.global_status_bar.retranslate_ui()
        if hasattr(self, 'menu_bar'):
            self.menu_bar.retranslate_ui()

    def toggle_right_section(self, visible: bool) -> None:
        """
        우측 패널의 가시성을 토글하고 윈도우 크기를 조정합니다.

        Logic:
            - 표시: 윈도우 폭을 늘리고 패널 표시, 스플리터 비율 조정
            - 숨김: 패널 너비 저장, 패널 숨김, 윈도우 폭을 줄여서 빈 공간 제거

        Args:
            visible (bool): 표시 여부.
        """
        if visible == self.right_section.isVisible():
            return

        current_width = self.width()
        handle_width = self.splitter.handleWidth()

        if visible:
            # 보이기: 윈도우 폭 증가
            # 저장된 너비가 있으면 사용, 없으면 기본값(윈도우의 30% 또는 최소 300px)
            if hasattr(self, '_right_section_width') and self._right_section_width is not None:
                target_right_width = self._right_section_width
            else:
                target_right_width = max(int(self.width() * 0.3), 300)

            # 현재 왼쪽 패널 너비 유지
            left_width = self.left_section.width()

            self.resize(current_width + target_right_width + handle_width, self.height())
            self.right_section.setVisible(True)

            # 스플리터 크기 설정
            self.splitter.setSizes([left_width, target_right_width])

            # 복원 후 저장값 초기화
            self._saved_left_width = None
            self._right_section_width = None

        else:
            # 숨기기: 윈도우 폭 감소
            # 현재 패널 너비 저장
            self._right_section_width = self.right_section.width()

            # 왼쪽 패널의 현재 너비를 기준으로 윈도우 크기 재조정
            margins = self.centralWidget().layout().contentsMargins()
            total_margin = margins.left() + margins.right()

            new_window_width = self.left_section.width() + total_margin
            self.right_section.setVisible(False)
            self.resize(new_window_width, self.height())