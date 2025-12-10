import sys
import os
import pytest
from PyQt5.QtWidgets import QApplication

from view.managers.lang_manager import lang_manager
from view.widgets.manual_ctrl import ManualCtrlWidget
from view.widgets.macro_list import MacroListWidget
from view.widgets.received_area import ReceivedAreaWidget
from view.widgets.packet_inspector import PacketInspectorWidget
from view.widgets.file_progress import FileProgressWidget
from view.widgets.system_log import SystemLogWidget
from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection

# 부모 디렉토리를 경로에 추가하여 모듈 import 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_manual_ctrl_translation(app, qtbot):
    manual_ctrl_widget = ManualCtrlWidget()
    qtbot.addWidget(manual_ctrl_widget)

    # Switch to English
    lang_manager.set_language('en')
    assert manual_ctrl_widget.send_manual_cmd_btn.text() == "Send"
    assert manual_ctrl_widget.hex_chk.text() == "Hex"

    # Switch to Korean
    lang_manager.set_language('ko')
    assert manual_ctrl_widget.send_manual_cmd_btn.text() == "전송"
    assert manual_ctrl_widget.hex_chk.text() == "Hex"

def test_macro_list_translation(app, qtbot):
    macro_list_widget = MacroListWidget()
    qtbot.addWidget(macro_list_widget)

    lang_manager.set_language('en')
    # Check tooltips for buttons as they have no text
    assert macro_list_widget.add_row_btn.toolTip() == "Add new command"

    lang_manager.set_language('ko')
    assert macro_list_widget.add_row_btn.toolTip() == "새 명령 추가"

def test_received_area_translation(app, qtbot):
    received_area_widget = ReceivedAreaWidget()
    qtbot.addWidget(received_area_widget)

    lang_manager.set_language('en')
    assert received_area_widget.rx_clear_log_btn.text() == "Clear"

    lang_manager.set_language('ko')
    assert received_area_widget.rx_clear_log_btn.text() == "지우기"

def test_packet_inspector_translation(app, qtbot):
    packet_inspector_widget = PacketInspectorWidget()
    qtbot.addWidget(packet_inspector_widget)

    lang_manager.set_language('en')
    assert packet_inspector_widget.title_label.text() == "Packet Inspector"

    lang_manager.set_language('ko')
    assert packet_inspector_widget.title_label.text() == "패킷 인스펙터"

def test_file_progress_translation(app, qtbot):
    file_progress_widget = FileProgressWidget()
    qtbot.addWidget(file_progress_widget)

    # Force switch to Korean first to ensure change to English triggers signal
    lang_manager.set_language('ko')
    lang_manager.set_language('en')
    assert file_progress_widget.cancel_btn.text() == "Cancel"

    lang_manager.set_language('ko')
    assert file_progress_widget.cancel_btn.text() == "취소"

def test_system_log_widget_translation(app, qtbot):
    system_log_widget = SystemLogWidget()
    qtbot.addWidget(system_log_widget)

    lang_manager.set_language('en')
    assert system_log_widget.status_log_title.text() == "Status Log"

    lang_manager.set_language('ko')
    assert system_log_widget.status_log_title.text() == "상태 로그"

def test_left_panel_translation(app, qtbot):
    left_panel_widget = MainLeftSection()
    qtbot.addWidget(left_panel_widget)

    lang_manager.set_language('en')
    assert left_panel_widget.port_tabs.toolTip() == "Port Tabs"

    lang_manager.set_language('ko')
    assert left_panel_widget.port_tabs.toolTip() == "포트 탭"

def test_right_panel_translation(app, qtbot):
    right_panel_widget = MainRightSection()
    qtbot.addWidget(right_panel_widget)

    lang_manager.set_language('en')
    assert right_panel_widget.tabs.tabText(0) == "Macro List"
    assert right_panel_widget.tabs.tabText(1) == "Inspector"

    lang_manager.set_language('ko')
    assert right_panel_widget.tabs.tabText(0) == "매크로 리스트"
    assert right_panel_widget.tabs.tabText(1) == "인스펙터"
