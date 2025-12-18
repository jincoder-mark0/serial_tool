"""
애플리케이션 생명주기 관리자 모듈

MainPresenter의 비대화를 방지하기 위해 초기화 및 종료 로직을 전담합니다.

## WHY
* MainPresenter가 GOD 클래스가 되는 것을 방지
* 초기화 순서 및 로직의 명확한 분리
* 테스트 용이성 향상

## WHAT
* AppLifecycleManager 클래스
* 설정 로드 및 View 초기화
* Model/Core 시스템 초기화
* Presenter 연결 및 복원
* 서비스 시작/종료

## HOW
* MainPresenter 인스턴스를 주입받아 위임 처리
* 단계별 초기화 메서드 제공
"""
from PyQt5.QtCore import QTimer
from core.settings_manager import SettingsManager
from core.logger import logger
from view.managers.color_manager import color_manager
from common.constants import ConfigKeys
from common.dtos import MainWindowState, FontConfig, ManualControlState, PreferencesState

# Circular Import 방지를 위해 TYPE_CHECKING 사용
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from presenter.main_presenter import MainPresenter

class AppLifecycleManager:
    """
    애플리케이션 초기화 및 종료를 관리하는 클래스
    """
    def __init__(self, main_presenter: 'MainPresenter'):
        self.mp = main_presenter
        self.view = main_presenter.view
        self.settings_manager = SettingsManager()

    def initialize_app(self) -> None:
        """
        애플리케이션 전체 초기화 시퀀스 실행
        """
        logger.info("Starting application initialization sequence...")

        # 1. 설정 로드 및 View 초기 구성
        self._init_settings_and_view()

        # 2. Model 및 Handler 초기화
        self.mp._init_core_systems()

        # 3. Sub-Presenter 초기화
        self.mp._init_sub_presenters()

        # 4. 하위 Presenter 상태 복원
        self._restore_sub_presenter_states()

        # 5. Fast Path 연결
        self.mp.connection_controller.data_received.connect(
            self.mp.data_handler.on_fast_data_received
        )

        # 6. 이벤트 및 시그널 연결
        self.mp._connect_signals()

        # 7. 서비스 시작
        self._start_services()

        logger.info("Application initialization completed.")

    def _init_settings_and_view(self) -> None:
        """
        설정 로드 및 View 초기화
        """
        # 설정 초기화 알림 체크
        if self.settings_manager.config_was_reset:
            reason = self.settings_manager.reset_reason
            self.view.show_alert_message(
                "Settings Reset",
                f"Configuration file corrupted or invalid.\nDefaults restored.\n\nReason: {reason}"
            )

        # View 초기화 로직 수행
        self._initialize_view_from_settings()

    def _initialize_view_from_settings(self) -> None:
        """
        설정 파일에서 값을 읽어 View의 초기 상태를 구성
        """
        all_settings = self.settings_manager.get_all_settings()
        window_state, font_config = self._create_initial_states(all_settings)

        # View에 설정 주입하여 초기 상태 복원
        self.view.apply_state(window_state, font_config)

        # 테마 적용
        theme = self.settings_manager.get(ConfigKeys.THEME, 'dark')
        self.view.switch_theme(theme)

        # Color Rules 주입
        self.view.left_section.system_log_widget.set_color_rules(color_manager.rules)

    def _restore_sub_presenter_states(self) -> None:
        """
        하위 Presenter의 상태 복원
        """
        all_settings = self.settings_manager.get_all_settings()
        window_state, _ = self._create_initial_states(all_settings)

        # ManualControl 상태 복원
        manual_settings = window_state.left_section_state.get("manual_control", {}).get("manual_control_widget", {})
        manual_state_dto = ManualControlState(
            input_text=manual_settings.get("input_text", ""),
            hex_mode=manual_settings.get("hex_mode", False),
            prefix_chk=manual_settings.get("prefix_chk", False),
            suffix_chk=manual_settings.get("suffix_chk", False),
            rts_chk=manual_settings.get("rts_chk", False),
            dtr_chk=manual_settings.get("dtr_chk", False),
            local_echo_chk=manual_settings.get("local_echo_chk", False),
            broadcast_chk=manual_settings.get("broadcast_chk", False)
        )
        self.mp.manual_control_presenter.apply_state(manual_state_dto)

    def _start_services(self) -> None:
        """
        백그라운드 서비스 및 타이머 시작
        """
        self.mp.status_timer = QTimer()
        self.mp.status_timer.timeout.connect(self.mp.update_status_bar)
        self.mp.status_timer.start(1000)

        self.view.log_system_message("Application initialized", "INFO")

    def _create_initial_states(self, settings: dict) -> tuple[MainWindowState, FontConfig]:
        """
        설정 딕셔너리를 DTO로 변환하는 헬퍼 메서드
        """
        def get_val(path, default=None):
            """
            설정 딕셔너리에서 값을 가져오는 헬퍼 메서드

            Args:
                path (str): 설정 키 경로
                default (Any, optional): 기본값. Defaults to None.
            """
            keys = path.split('.')
            val = settings
            try:
                for k in keys: val = val.get(k, {})
                return val if val != {} else default
            except AttributeError: return default

        window_state = MainWindowState(
            width=get_val(ConfigKeys.WINDOW_WIDTH, 1400),
            height=get_val(ConfigKeys.WINDOW_HEIGHT, 900),
            x=get_val(ConfigKeys.WINDOW_X),
            y=get_val(ConfigKeys.WINDOW_Y),
            splitter_state=get_val(ConfigKeys.SPLITTER_STATE),
            right_panel_visible=get_val(ConfigKeys.RIGHT_PANEL_VISIBLE, True),
            saved_right_width=get_val(ConfigKeys.SAVED_RIGHT_WIDTH),
            left_section_state={
                "manual_control": get_val(ConfigKeys.MANUAL_CONTROL_STATE, {}),
                "ports": get_val(ConfigKeys.PORTS_TABS_STATE, [])
            },
            right_section_state={
                "macro_panel": {
                    "commands": get_val(ConfigKeys.MACRO_COMMANDS, []),
                    "control_state": get_val(ConfigKeys.MACRO_CONTROL_STATE, {})
                }
            }
        )

        font_config = FontConfig(
            prop_family=get_val(ConfigKeys.PROP_FONT_FAMILY, "Segoe UI"),
            prop_size=get_val(ConfigKeys.PROP_FONT_SIZE, 9),
            fixed_family=get_val(ConfigKeys.FIXED_FONT_FAMILY, "Consolas"),
            fixed_size=get_val(ConfigKeys.FIXED_FONT_SIZE, 9)
        )

        return window_state, font_config
