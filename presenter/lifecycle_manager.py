"""
애플리케이션 생명주기 관리자 모듈

MainPresenter의 비대화를 방지하기 위해 초기화 및 종료 로직을 전담합니다.

## WHY
* MainPresenter가 GOD 클래스가 되는 것을 방지
* 초기화 순서 및 로직의 명확한 분리
* 테스트 용이성 향상 (초기화 로직만 별도 테스트 가능)

## WHAT
* AppLifecycleManager 클래스 정의
* 설정 로드 및 View 초기 상태 복원
* Model/Core 시스템 및 하위 Presenter 초기화
* Fast Path 및 시그널 연결 설정
* 백그라운드 서비스 시작

## HOW
* MainPresenter 인스턴스를 주입받아 위임(Delegation) 처리
* 단계별 초기화 메서드(_init_*)를 순차적으로 호출
* DTO를 사용하여 설정 데이터를 View에 주입
"""
from typing import TYPE_CHECKING, Dict, Any
from PyQt5.QtCore import QTimer

from core.settings_manager import SettingsManager
from core.logger import logger
from view.managers.color_manager import color_manager
from common.constants import ConfigKeys
from common.dtos import (
    MainWindowState,
    FontConfig,
    ManualControlState,
    PreferencesState,
    SystemLogEvent  # [수정] DTO 추가
)

# Circular Import 방지를 위해 TYPE_CHECKING 사용
if TYPE_CHECKING:
    from presenter.main_presenter import MainPresenter


class AppLifecycleManager:
    """
    애플리케이션 초기화 및 종료를 관리하는 클래스입니다.

    MainPresenter의 생성자에서 호출되어 앱의 구동에 필요한 모든 요소를
    순서대로 준비시킵니다.
    """

    def __init__(self, main_presenter: 'MainPresenter') -> None:
        """
        AppLifecycleManager 초기화

        Args:
            main_presenter (MainPresenter): 메인 프레젠터 인스턴스.
        """
        self.mp = main_presenter
        self.view = main_presenter.view
        self.settings_manager = SettingsManager()

    def initialize_app(self) -> None:
        """
        애플리케이션 전체 초기화 시퀀스를 실행합니다.

        Logic:
            1. 설정 로드 및 View 초기 구성 (테마, 폰트, 윈도우 크기)
            2. Core 시스템 및 Model 초기화 (Controller, Runner)
            3. 하위 Presenter 초기화
            4. 하위 Presenter 상태 복원 (Manual Control 등)
            5. Fast Path 데이터 수신 경로 연결
            6. 이벤트 및 시그널 연결
            7. 백그라운드 서비스 시작
        """
        logger.info("Starting application initialization sequence...")

        # 1. 설정 로드 및 View 초기 구성
        self._init_settings_and_view()

        # 2. Model 및 Handler 초기화 (MainPresenter 메서드 호출)
        self.mp._init_core_systems()

        # 3. Sub-Presenter 초기화 (MainPresenter 메서드 호출)
        self.mp._init_sub_presenters()

        # 4. 하위 Presenter 상태 복원
        self._restore_sub_presenter_states()

        # 5. Fast Path 연결 (ConnectionController -> DataHandler)
        # EventBus를 거치지 않고 직접 연결하여 성능 최적화
        self.mp.connection_controller.data_received.connect(
            self.mp.data_handler.on_fast_data_received
        )

        # 6. 이벤트 및 시그널 연결 (MainPresenter 메서드 호출)
        self.mp._connect_signals()

        # 7. 서비스 시작
        self._start_services()

        logger.info("Application initialization completed.")

    def _init_settings_and_view(self) -> None:
        """
        설정 파일을 로드하고 View를 초기화합니다.

        Logic:
            - 설정 파일 초기화(Reset) 여부 확인 및 알림
            - 저장된 설정값을 바탕으로 DTO 생성
            - View에 상태 주입 (apply_state)
            - 테마 및 색상 규칙 적용
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
        설정 파일에서 값을 읽어 View의 초기 상태를 구성합니다.
        """
        all_settings = self.settings_manager.get_all_settings()
        window_state, font_config = self._create_initial_states(all_settings)

        # View에 설정 주입하여 초기 상태 복원
        self.view.apply_state(window_state, font_config)

        # 테마 적용
        theme = self.settings_manager.get(ConfigKeys.THEME, 'dark')
        self.view.switch_theme(theme)

        # 시스템 로그 위젯에 색상 규칙 주입
        # View가 Model(ColorManager)에 직접 접근하지 않도록 주입
        self.view.left_section.system_log_widget.set_color_rules(color_manager._rules)

    def _restore_sub_presenter_states(self) -> None:
        """
        하위 Presenter들의 상태를 복원합니다.
        (예: 수동 제어 패널의 이전 입력값 복원)
        """
        all_settings = self.settings_manager.get_all_settings()
        window_state, _ = self._create_initial_states(all_settings)

        # ManualControl 상태 복원
        # 설정 딕셔너리 구조를 탐색하여 데이터 추출
        manual_settings = window_state.left_section_state.get("manual_control", {}).get("manual_control_widget", {})

        # DTO 생성
        manual_state_dto = ManualControlState(
            input_text=manual_settings.get("input_text", ""),
            hex_mode=manual_settings.get("hex_mode", False),
            prefix_enabled=manual_settings.get("prefix_enabled", False),
            suffix_enabled=manual_settings.get("suffix_enabled", False),
            rts_enabled=manual_settings.get("rts_enabled", False),
            dtr_enabled=manual_settings.get("dtr_enabled", False),
            local_echo_enabled=manual_settings.get("local_echo_enabled", False),
            broadcast_enabled=manual_settings.get("broadcast_enabled", False)
        )

        # Presenter에 상태 주입
        self.mp.manual_control_presenter.apply_state(manual_state_dto)

    def _start_services(self) -> None:
        """
        백그라운드 서비스 및 타이머를 시작합니다.
        """
        # 상태바 업데이트 타이머 시작 (1초 주기)
        self.mp.status_timer = QTimer()
        self.mp.status_timer.timeout.connect(self.mp.update_status_bar)
        self.mp.status_timer.start(1000)

        # 초기화 완료 로그 - DTO 사용
        event = SystemLogEvent(message="Application initialized", level="INFO")
        self.view.log_system_message(event)

    def _create_initial_states(self, settings: Dict[str, Any]) -> tuple[MainWindowState, FontConfig]:
        """
        설정 딕셔너리를 DTO로 변환하는 헬퍼 메서드입니다.

        Args:
            settings (Dict[str, Any]): 로드된 전체 설정 데이터.

        Returns:
            tuple[MainWindowState, FontConfig]: 생성된 상태 DTO 튜플.
        """
        def get_val(path: str, default: Any = None) -> Any:
            """
            점(.) 표기법 경로를 사용하여 중첩된 딕셔너리 값을 가져옵니다.

            Args:
                path (str): 키 경로 (예: "ui.window_width").
                default (Any): 키가 없을 경우 반환할 기본값.

            Returns:
                Any: 설정값 또는 기본값.
            """
            keys = path.split('.')
            val = settings
            try:
                for k in keys:
                    val = val.get(k, {})
                # 빈 딕셔너리({})가 반환되는 경우(경로 중간 끊김) default 반환
                return val if val != {} else default
            except AttributeError:
                return default

        # MainWindowState DTO 생성
        window_state = MainWindowState(
            width=get_val(ConfigKeys.WINDOW_WIDTH, 1400),
            height=get_val(ConfigKeys.WINDOW_HEIGHT, 900),
            x=get_val(ConfigKeys.WINDOW_X),
            y=get_val(ConfigKeys.WINDOW_Y),
            splitter_state=get_val(ConfigKeys.SPLITTER_STATE),
            right_panel_visible=get_val(ConfigKeys.RIGHT_PANEL_VISIBLE, True),
            right_section_width=get_val(ConfigKeys.SAVED_RIGHT_WIDTH),
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

        # FontConfig DTO 생성
        font_config = FontConfig(
            prop_family=get_val(ConfigKeys.PROP_FONT_FAMILY, "Segoe UI"),
            prop_size=get_val(ConfigKeys.PROP_FONT_SIZE, 9),
            fixed_family=get_val(ConfigKeys.FIXED_FONT_FAMILY, "Consolas"),
            fixed_size=get_val(ConfigKeys.FIXED_FONT_SIZE, 9)
        )

        return window_state, font_config