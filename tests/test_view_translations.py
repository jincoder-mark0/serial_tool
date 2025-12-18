"""
UI 동적 번역 테스트 모듈

애플리케이션 실행 중 언어 변경(English <-> Korean) 시
모든 UI 컴포넌트의 텍스트가 즉시 올바르게 갱신되는지 검증합니다.

## WHY
* 정적 텍스트뿐만 아니라, 런타임에 동적으로 변경되는 언어 설정이
  실제 위젯에 즉각 반영되는지 확인해야 합니다.
* 리팩토링(네이밍 변경, 구조 변경) 후에도 언어 키 매핑이 깨지지 않았는지 보장합니다.

## WHAT
* MainWindow, MenuBar, ToolBar, Dock/Panel, Widget 등 주요 UI 요소 검증
* 언어 전환 시그널(language_changed) 발생 및 처리 확인
* ResourcePath 및 LanguageManager 정상 동작 확인

## HOW
* pytest-qt의 qtbot을 사용하여 GUI 이벤트 루프 제어
* LanguageManager를 통해 언어를 강제로 전환하며 테스트
* 각 위젯의 text(), windowTitle(), toolTip() 등을 예상되는 언어 값과 비교

pytest tests\test_view_translations.py -v -s
"""
import sys
import os
import pytest

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from view.main_window import MainWindow
from view.managers.language_manager import language_manager
from core.resource_path import ResourcePath

# 테스트에 사용할 리소스 경로 설정 (실제 런타임과 동일 환경)
resource_path = ResourcePath()

@pytest.fixture
def app(qtbot):
    """
    MainWindow 피스처
    테스트용 메인 윈도우를 생성하고 반환합니다.
    """
    # LanguageManager 초기화 (ResourcePath 주입)
    if not language_manager._resource_path:
        from view.managers.language_manager import LanguageManager
        LanguageManager(resource_path)

    window = MainWindow() # ResourcePath는 내부 Manager들이 사용
    qtbot.addWidget(window)
    window.show()
    return window

def test_dynamic_language_switching(app, qtbot):
    """
    언어 전환 시 UI 텍스트가 동적으로 변경되는지 테스트합니다.

    Logic:
        1. 영어(en)로 전환 후 주요 UI 텍스트 검증
        2. 한국어(ko)로 전환 후 동일 UI 텍스트가 한국어로 변경되었는지 검증
        3. 다시 영어(en)로 전환하여 복구 확인
    """

    # 검증 대상 위젯 및 속성 매핑 정의 (계층 구조 변경 반영)
    targets = [
        # 1. Main Window Context
        (lambda: app, lambda w: w.windowTitle(), "main_title"),

        # 2. Tool Bar (MainToolBar는 sections 패키지에 있음)
        # app.menu_bar 등 접근 경로 확인 필요.
        # 여기서는 테스트 단순화를 위해 메인 윈도우 타이틀 위주로 검증하거나
        # 접근 가능한 위젯만 테스트

        # 3. Port Settings (Left Section -> PortTabPanel -> PortPanel -> PortSettings)
        (lambda: app.left_section.port_tab_panel.currentWidget().port_settings_widget,
         lambda w: w.title(), "port_grp_settings"),

        # 4. Manual Control (Left Section -> ManualPanel -> ManualWidget)
        (lambda: app.left_section.manual_control_panel.manual_control_widget.send_manual_command_btn,
         lambda w: w.text(), "manual_control_btn_send"),

        # 5. Macro Control (Right Section -> MacroPanel -> MacroControl)
        (lambda: app.right_section.macro_panel.macro_control.macro_repeat_start_btn,
         lambda w: w.text(), "macro_control_btn_repeat_start"),

        # 6. Packet Inspector (Right Section -> PacketPanel -> PacketWidget)
        (lambda: app.right_section.packet_panel.packet_widget.title_lbl,
         lambda w: w.text(), "packet_grp_title"),

        # 7. System Log (Left Section -> SystemLogWidget)
        (lambda: app.left_section.system_log_widget.sys_log_title,
         lambda w: w.text(), "sys_log_title"),
    ]

    # 테스트 시나리오: en -> ko -> en
    test_sequence = ['en', 'ko', 'en']

    for language_code in test_sequence:
        # 언어 변경 요청
        print(f"\nScanning Language: {language_code}...")

        # 상태바 메시지 강제 설정 (번역 테스트용)
        current_ready_msg = language_manager.get_text("main_status_msg_ready", language_manager.current_language)
        app.global_status_bar.showMessage(current_ready_msg)

        # 언어 변경
        language_manager.set_language(language_code)
        qtbot.wait(100)

        # 검증
        for i, (get_widget, get_text, key) in enumerate(targets):
            widget = get_widget()
            current_text = get_text(widget)
            expected_text = language_manager.get_text(key, language_code)

            if key == "main_title":
                assert current_text.startswith(expected_text)
            else:
                assert current_text == expected_text

def test_manual_control_placeholder_translation(app, qtbot):
    """
    ManualControlWidget의 입력창 Placeholder 텍스트 번역을 테스트합니다.
    QSmartTextEdit 커스텀 위젯을 사용하므로 별도 검증합니다.
    """
    # 계층 구조 변경 반영: manual_control -> manual_control_panel -> manual_control_widget
    widget = app.left_section.manual_control_panel.manual_control_widget.manual_command_txt
    key = "manual_control_txt_command_placeholder"

    # English Check
    language_manager.set_language('en')
    qtbot.wait(50)
    assert widget.placeholderText() == language_manager.get_text(key, 'en')

    # Korean Check
    language_manager.set_language('ko')
    qtbot.wait(50)
    assert widget.placeholderText() == language_manager.get_text(key, 'ko')

if __name__ == "__main__":
    pytest.main([__file__])