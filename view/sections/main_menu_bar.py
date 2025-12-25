"""
메인 메뉴바 모듈

애플리케이션의 상단 메뉴바(File, View, Tools, Help)를 구성하고 이벤트를 처리합니다.
설정(테마, 언어, 폰트) 변경 및 애플리케이션 주요 기능(포트 열기/닫기, 탭 관리 등)을 제공합니다.

## WHY
* 사용자가 애플리케이션의 전역 설정 및 기능에 접근할 수 있는 표준 인터페이스 필요
* 단축키(Shortcut) 안내를 통한 접근성 향상
* 동적으로 변경되는 테마 및 언어 목록을 메뉴에 반영

## WHAT
* File 메뉴: 새 탭, 포트 열기, 탭 닫기, 로그 저장, 종료
* View 메뉴: 우측 패널 토글, 테마/언어/폰트/설정 변경
* Tools 메뉴: 파일 전송 등 유틸리티 기능
* Help 메뉴: 정보(About) 확인
* ThemeManager/LanguageManager와 연동한 동적 메뉴 구성

## HOW
* QMenuBar 상속 및 시그널(pyqtSignal) 정의
* QActionGroup을 활용한 배타적(Radio) 선택 구현 (테마, 언어)
* 람다(lambda) 함수를 사용하여 동적 생성된 액션에 데이터 바인딩
"""
from typing import Dict, Optional

from PyQt5.QtWidgets import QMenuBar, QAction, QActionGroup, QApplication
from PyQt5.QtCore import pyqtSignal

from view.managers.language_manager import language_manager
from view.managers.theme_manager import theme_manager
from core.logger import logger


class MainMenuBar(QMenuBar):
    """
    메인 윈도우의 메뉴바를 관리하는 클래스입니다.
    테마와 언어 메뉴를 동적으로 구성하고, 각 액션에 대한 시그널을 방출합니다.
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # File Menu Signals
    tab_new_requested = pyqtSignal()
    connect_requested = pyqtSignal()
    tab_close_requested = pyqtSignal()
    data_log_save_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    # View Menu Signals
    toggle_right_section_requested = pyqtSignal(bool)
    theme_changed = pyqtSignal(str)
    font_settings_requested = pyqtSignal()
    language_changed = pyqtSignal(str)
    preferences_requested = pyqtSignal()

    # Tools Menu Signals
    file_transfer_requested = pyqtSignal()

    # Help Menu Signals
    about_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        """
        MainMenuBar 초기화

        Logic:
            - 부모 클래스(QMenuBar) 초기화
            - 메뉴 구성 (init_menu)
            - 언어 변경 시그널 연결 (즉시 UI 갱신)

        Args:
            parent: 부모 위젯.
        """
        super().__init__(parent)

        # 액션 그룹 참조 (상태 갱신용)
        self.theme_action_group: Optional[QActionGroup] = None
        self.toggle_right_section_action: Optional[QAction] = None

        self.init_menu()

        # 언어 변경 시 메뉴 텍스트 갱신 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_menu(self) -> None:
        """
        메뉴바를 초기화하고 액션을 설정합니다.

        Logic:
            1. 기존 메뉴 제거 (clear)
            2. File, View, Tools, Help 순으로 메뉴 및 액션 생성
            3. 동적 항목(테마, 언어)은 매니저를 통해 목록 조회 후 생성
        """
        self.clear()

        # ---------------------------------------------------------
        # 1. 파일 메뉴 (File Menu)
        # ---------------------------------------------------------
        file_menu = self.addMenu(language_manager.get_text("main_menu_file"))

        # 새 탭
        new_tab_action = QAction(language_manager.get_text("main_menu_new_tab"), self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.setToolTip(language_manager.get_text("main_menu_new_tab_tooltip"))
        new_tab_action.triggered.connect(self.tab_new_requested.emit)
        file_menu.addAction(new_tab_action)

        # 포트 열기
        open_port_action = QAction(language_manager.get_text("main_menu_open_port"), self)
        open_port_action.setShortcut("Ctrl+O")
        open_port_action.triggered.connect(self.connect_requested.emit)
        file_menu.addAction(open_port_action)

        # 탭 닫기
        close_tab_action = QAction(language_manager.get_text("main_menu_close_tab"), self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(self.tab_close_requested.emit)
        file_menu.addAction(close_tab_action)

        # 데이터 로그 저장
        save_data_log_action = QAction(language_manager.get_text("main_menu_save_data_log"), self)
        save_data_log_action.setShortcut("Ctrl+Shift+S")
        save_data_log_action.triggered.connect(self.data_log_save_requested.emit)
        file_menu.addAction(save_data_log_action)

        file_menu.addSeparator()

        # 종료
        exit_action = QAction(language_manager.get_text("main_menu_exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip(language_manager.get_text("main_menu_exit_tooltip"))
        exit_action.setIcon(theme_manager.get_icon("exit")) # 아이콘 추가
        exit_action.triggered.connect(self.exit_requested.emit)
        file_menu.addAction(exit_action)

        # ---------------------------------------------------------
        # 2. 보기 메뉴 (View Menu)
        # ---------------------------------------------------------
        view_menu = self.addMenu(language_manager.get_text("main_menu_view"))

        # 우측 패널 토글
        self.toggle_right_section_action = QAction(language_manager.get_text("main_menu_toggle_right_section"), self)
        self.toggle_right_section_action.setCheckable(True)
        self.toggle_right_section_action.setChecked(True) # 기본값 체크
        self.toggle_right_section_action.triggered.connect(self.toggle_right_section_requested.emit)
        view_menu.addAction(self.toggle_right_section_action)

        view_menu.addSeparator()

        # 테마 서브메뉴 (Theme Submenu)
        theme_menu = view_menu.addMenu(language_manager.get_text("main_menu_theme"))
        theme_menu.setIcon(theme_manager.get_icon("theme"))

        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        # ThemeManager에서 사용 가능한 테마 목록 스캔
        available_themes = theme_manager.get_available_themes()
        current_theme = theme_manager.get_current_theme()

        for theme_name in available_themes:
            # 메뉴 표시 이름 번역 시도
            lang_key = f"main_menu_theme_{theme_name.lower()}"
            display_name = language_manager.get_text(lang_key)
            if display_name == lang_key: # 번역 키가 없으면 파일명 그대로 사용
                display_name = theme_name

            action = QAction(display_name, self)
            action.setCheckable(True)
            action.setData(theme_name) # 원본 테마 이름 저장

            # 현재 테마 체크
            if theme_name.lower() == current_theme.lower():
                action.setChecked(True)

            # 람다 캡처 주의: name=theme_name
            action.triggered.connect(lambda checked, name=theme_name: self.theme_changed.emit(name.lower()))

            theme_menu.addAction(action)
            self.theme_action_group.addAction(action)

        # 폰트 설정 액션
        font_action = QAction(language_manager.get_text("main_menu_font"), self)
        font_action.setShortcut("Ctrl+Shift+F")
        font_action.setToolTip(language_manager.get_text("main_menu_font_tooltip"))
        font_action.setIcon(theme_manager.get_icon("font"))
        font_action.triggered.connect(self.font_settings_requested.emit)
        view_menu.addAction(font_action)

        # 언어 서브메뉴 (Language Submenu)
        language_menu = view_menu.addMenu(language_manager.get_text("main_menu_lang"))
        language_menu.setIcon(theme_manager.get_icon("language"))

        # LanguageManager에서 사용 가능한 언어 목록 스캔
        available_langs = language_manager.get_available_languages()
        current_lang_code = language_manager.get_current_language()

        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        for code, name in available_langs.items():
            action = QAction(name, self)
            action.setCheckable(True)

            if code == current_lang_code:
                action.setChecked(True)

            # 람다 캡처 주의: c=code
            action.triggered.connect(lambda checked, c=code: self.language_changed.emit(c))

            lang_group.addAction(action)
            language_menu.addAction(action)

        # Preferences 액션
        preferences_action = QAction(language_manager.get_text("main_menu_preferences"), self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self.preferences_requested.emit)
        view_menu.addAction(preferences_action)

        # ---------------------------------------------------------
        # 3. 도구 메뉴 (Tools Menu)
        # ---------------------------------------------------------
        tools_menu = self.addMenu(language_manager.get_text("main_menu_tools"))

        # 파일 전송 액션
        file_transfer_action = QAction(language_manager.get_text("main_menu_file_transfer"), self)
        file_transfer_action.triggered.connect(self.file_transfer_requested.emit)
        tools_menu.addAction(file_transfer_action)

        # ---------------------------------------------------------
        # 4. 도움말 메뉴 (Help Menu)
        # ---------------------------------------------------------
        help_menu = self.addMenu(language_manager.get_text("main_menu_help"))

        # 정보(About) 액션
        about_action = QAction(language_manager.get_text("main_menu_about"), self)
        about_action.setIcon(theme_manager.get_icon("info"))
        about_action.triggered.connect(self.about_requested.emit)
        help_menu.addAction(about_action)

    def set_right_section_checked(self, checked: bool) -> None:
        """
        우측 패널 토글 액션의 체크 상태를 설정합니다.
        (사용자가 툴바나 단축키로 패널을 여닫을 때 동기화용)

        Args:
            checked (bool): 체크 여부.
        """
        if self.toggle_right_section_action:
            self.toggle_right_section_action.setChecked(checked)

    def set_current_theme(self, theme_name: str) -> None:
        """
        현재 테마를 설정하고 메뉴의 체크 표시를 업데이트합니다.

        Args:
            theme_name (str): 테마 이름 (예: "dark").
        """
        if not self.theme_action_group:
            return

        for action in self.theme_action_group.actions():
            # 저장된 데이터(테마 이름)와 비교
            if str(action.data()).lower() == theme_name.lower():
                action.setChecked(True)
                break

    def retranslate_ui(self) -> None:
        """언어 변경 시 메뉴 텍스트를 업데이트합니다."""
        # 메뉴 전체를 재생성하여 번역 반영
        self.init_menu()