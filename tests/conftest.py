"""
Pytest 설정 및 공통 Fixture 모듈

테스트 실행 시 전역적으로 사용되는 설정과 Fixture를 정의합니다.

## WHY
* 반복되는 테스트 객체(DTO, Mock) 생성 코드 제거
* 실제 하드웨어/파일시스템 의존성 격리 (Mocking)
* PyQt5 QApplication 인스턴스의 전역 관리

## WHAT
* sys.path 설정 (프로젝트 루트 인식)
* QApplication 인스턴스 관리 (qapp)
* Serial/Settings/EventBus Mocking Fixture
* 공통 DTO 데이터 Fixture

## HOW
* pytest.fixture 데코레이터 활용
* unittest.mock.MagicMock을 이용한 가짜 객체 주입
* autouse=True를 통한 자동 초기화

pytest tests/test_conf_test.py -v
"""
import sys
import os
import copy
import pytest
from unittest.mock import patch

# -----------------------------------------------------------------------------
# 1. 경로 설정 (Path Setup)
# -----------------------------------------------------------------------------
# 프로젝트 루트 디렉토리를 sys.path에 추가하여 모듈 import 에러 방지
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt5.QtWidgets import QApplication
from common.dtos import PortConfig, ManualCommand, MacroEntry
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.event_bus import event_bus
from core.resource_path import ResourcePath


# -----------------------------------------------------------------------------
# 2. PyQt 관련 Fixture (PyQt Fixtures)
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """
    테스트 세션 전체에서 공유되는 QApplication 인스턴스를 제공합니다.

    PyQt 위젯을 테스트하려면 반드시 하나의 QApplication 인스턴스가 필요합니다.
    이미 생성된 인스턴스가 있다면 그것을 반환하고, 없다면 새로 생성합니다.

    Yields:
        QApplication: Qt 애플리케이션 인스턴스.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # 세션 종료 시 별도 정리 작업은 필요 없음 (프로세스 종료로 처리)


# -----------------------------------------------------------------------------
# 3. Mocking Fixtures (Core & Hardware)
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_serial_port():
    """
    pyserial의 Serial 클래스를 Mocking합니다.

    실제 하드웨어 연결 없이 시리얼 통신 로직을 테스트하기 위해 사용됩니다.
    read, write, open, close 등의 메서드가 Mock 객체로 대체됩니다.

    Yields:
        MagicMock: Mocking된 Serial 인스턴스.
    """
    with patch("core.transport.serial_transport.serial.Serial") as mock_cls:
        mock_instance = mock_cls.return_value

        # 기본 동작 설정
        # serial.Serial(...) opens the configured port during construction.
        mock_instance.is_open = True
        mock_instance.in_waiting = 0

        # open() 호출 시 is_open을 True로 변경하는 사이드 이펙트
        def open_side_effect():
            mock_instance.is_open = True

        # close() 호출 시 is_open을 False로 변경하는 사이드 이펙트
        def close_side_effect():
            mock_instance.is_open = False

        mock_instance.open.side_effect = open_side_effect
        mock_instance.close.side_effect = close_side_effect

        # write()는 보낸 바이트 수를 반환하도록 설정
        mock_instance.write.side_effect = lambda data: len(data)

        yield mock_instance


@pytest.fixture
def mock_settings_manager(tmp_path):
    """
    SettingsManager를 Mocking하여 임시 경로를 사용하도록 설정합니다.

    실제 config.json 파일을 덮어쓰지 않고 테스트하기 위함입니다.
    pytest의 tmp_path 픽스처를 사용하여 격리된 파일 시스템을 제공합니다.

    Args:
        tmp_path (Path): pytest가 제공하는 임시 디렉토리 경로.

    Yields:
        SettingsManager: 임시 경로로 초기화된 설정 관리자.
    """
    from core.settings_manager import SettingsManager

    resource_path = ResourcePath(tmp_path)
    resource_path.config_dir.mkdir(parents=True)

    SettingsManager._instance = None
    SettingsManager._initialized = False
    manager = SettingsManager(resource_path)
    yield manager
    SettingsManager._instance = None
    SettingsManager._initialized = False


@pytest.fixture(autouse=True)
def reset_event_bus():
    """
    각 테스트 실행 전후에 EventBus를 초기화합니다 (자동 적용).

    테스트 간 이벤트 구독(Subscribe) 상태가 공유되어 발생하는 사이드 이펙트를 방지합니다.
    """
    # 테스트 전: 구독자 목록 초기화
    # (EventBus 내부 구현에 따라 _subscribers 접근이 필요할 수 있음)
    if hasattr(event_bus, '_subscribers'):
        event_bus._subscribers.clear()

    yield

    # 테스트 후: 다시 초기화
    if hasattr(event_bus, '_subscribers'):
        event_bus._subscribers.clear()


@pytest.fixture(autouse=True)
def reset_ui_manager_state():
    """
    ThemeManager/ColorManager/LanguageManager 싱글톤의 가변 상태를 테스트 전후로
    스냅샷/복원합니다 (자동 적용, S-048).

    ## WHY (SettingsManager 리셋 패턴을 그대로 재사용하지 않은 이유)
    `mock_settings_manager`(위)는 `SettingsManager._instance`를 None으로 리셋한 뒤
    `SettingsManager()`를 다시 호출하는 방식이 통한다 — 실제 소비 코드
    (presenter 등)가 필요할 때마다 `SettingsManager()`를 새로 호출해 싱글톤을
    조회하기 때문이다.

    반면 ThemeManager/ColorManager/LanguageManager는 각 모듈 하단에서 **단 한 번**
    `theme_manager = ThemeManager()` 식으로 생성된 모듈 전역 인스턴스를 소비 코드가
    `from view.managers.xxx import xxx_manager`로 직접 import해 재사용한다(생성자를
    다시 호출하는 곳이 없음 — 코드베이스 전체 검색으로 확인, 2026-08-22). 따라서
    `_instance`/`_initialized`를 None으로 리셋해도 이미 import되어 여기저기 박혀있는
    전역 인스턴스 자체는 그대로 남아 오염이 사라지지 않는다(오히려 다음에 우연히
    생성자가 호출되면 별개의 "두 번째 싱글톤"이 생겨 상태가 갈라지는 위험만 추가).

    그래서 이 픽스처는 실제로 공유되는 그 전역 인스턴스의 **가변 상태 값**을
    스냅샷/복원한다 — 재생성(파일 재로드) 없이 오염을 막는 방식.

    ## WHY autouse (재생성이 아니라 스냅샷이므로 비용이 무시할 수준)
    재생성 방식 비용을 측정한 결과(2026-08-22, 이 머신 기준):
    - ThemeManager 재생성: ~0.02ms/회 (무시 가능)
    - ColorManager 재생성: ~0.3ms/회 (무시 가능, JSON 규칙 8개 재로드/재저장)
    - LanguageManager 재생성: ~64ms/회 (commentjson으로 en/ko 278키 재파싱 —
      227개 테스트 전체에 autouse로 걸면 +14초 이상, 기준선(2.91초)의 5배 이상 증가)
    반면 아래 스냅샷/복원 방식은 문자열 대입 + 작은 dict/list의 `copy.deepcopy`
    뿐이라 1000회 반복 측정 기준 총 0.04ms(1회당 0.00004ms) 수준 — autouse로 걸어도
    전체 실행 시간에 측정 가능한 영향이 없다. 그래서 opt-in이 아니라 autouse로 걸어
    (아직 존재하지 않는 미래의) "상태를 바꾸는 테스트"까지 기본적으로 보호한다.

    ## WHAT
    - `ThemeManager._current_theme`: 문자열 스칼라라 얕은 복원으로 충분.
    - `ColorManager._rules`: 규칙 리스트 자체가 재할당되기도 하고(add/remove_rule),
      기존 ColorRule 객체의 `.color` 필드가 `apply_theme()`으로 제자리 수정되기도
      하므로 `copy.deepcopy`로 값 단위 스냅샷이 필요하다(얕은 리스트 복사로는
      제자리 mutation을 못 막음). `COLOR_*` 팔레트 속성도 함께 복원한다.
    - `LanguageManager._current_language`, `.resources`: `test_view_translations.py`가
      이미 `.resources`를 통째로 테스트용 dict로 교체하는 실사용 사례가 있어
      (교체된 채 복원되지 않으면 이후 세션의 다른 테스트가 실제 언어 데이터 대신
      그 테스트용 mini dict를 보게 된다) `.resources`도 deepcopy로 스냅샷한다.
    """
    from view.managers.theme_manager import theme_manager
    from view.managers.color_manager import color_manager
    from view.managers.language_manager import language_manager

    theme_snapshot = theme_manager._current_theme

    color_rules_snapshot = copy.deepcopy(color_manager._rules)
    color_palette_snapshot = {
        k: v for k, v in vars(color_manager).items() if k.startswith("COLOR_")
    }

    lang_current_snapshot = language_manager._current_language
    lang_resources_snapshot = copy.deepcopy(language_manager.resources)

    yield

    theme_manager._current_theme = theme_snapshot

    color_manager._rules = color_rules_snapshot
    for key, value in color_palette_snapshot.items():
        setattr(color_manager, key, value)

    language_manager._current_language = lang_current_snapshot
    language_manager.resources = lang_resources_snapshot


# -----------------------------------------------------------------------------
# 4. Data Object Fixtures (DTOs)
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_port_config():
    """
    테스트용 기본 PortConfig DTO를 제공합니다.

    Returns:
        PortConfig: 유효한 값을 가진 포트 설정 객체.
    """
    return PortConfig(
        port="COM_TEST",
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value
    )


@pytest.fixture
def sample_manual_command():
    """
    테스트용 기본 ManualCommand DTO를 제공합니다.

    Returns:
        ManualCommand: "TEST_CMD" 명령어를 가진 객체.
    """
    return ManualCommand(
        command="TEST_CMD",
        hex_mode=False,
        prefix_enabled=False,
        suffix_enabled=True,  # 보통 \n을 붙이므로 True로 설정
        local_echo_enabled=True,
        broadcast_enabled=False
    )


@pytest.fixture
def sample_macro_entry():
    """
    테스트용 기본 MacroEntry DTO를 제공합니다.

    Returns:
        MacroEntry: 매크로 실행 테스트용 객체.
    """
    return MacroEntry(
        enabled=True,
        command="MACRO_CMD",
        delay_ms=100,
        hex_mode=False
    )
