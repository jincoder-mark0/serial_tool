import sys
import os
import pytest
from PyQt5.QtWidgets import QApplication

# 부모 디렉토리를 경로에 추가하여 모듈 import 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from view.language_manager import language_manager
from view.widgets.manual_control import ManualControlWidget
from view.widgets.command_list import CommandListWidget
from view.widgets.received_area import ReceivedAreaWidget
from view.widgets.packet_inspector import PacketInspectorWidget
from view.widgets.file_progress import FileProgressWidget
from view.widgets.status_area import StatusAreaWidget
from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection

@pytest.fixture(scope="session")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_manual_control_translation(app, qtbot):
    widget = ManualControlWidget()
    qtbot.addWidget(widget)

    # Switch to English
    language_manager.set_language('en')
    assert widget.send_manual_cmd_btn.text() == "Send"
    assert widget.hex_chk.text() == "Hex"

    # Switch to Korean
    language_manager.set_language('ko')
    assert widget.send_manual_cmd_btn.text() == "전송"
    assert widget.hex_chk.text() == "Hex"

def test_cmd_list_translation(app, qtbot):
    widget = CommandListWidget()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    # Check tooltips for buttons as they have no text
    assert widget.add_cmd_btn.toolTip() == "Add new command"

    language_manager.set_language('ko')
    assert widget.add_cmd_btn.toolTip() == "새 명령 추가"

def test_received_area_translation(app, qtbot):
    widget = ReceivedAreaWidget()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    assert widget.clear_rx_log_btn.text() == "Clear"

    language_manager.set_language('ko')
    assert widget.clear_rx_log_btn.text() == "지우기"

def test_packet_inspector_translation(app, qtbot):
    widget = PacketInspectorWidget()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    assert widget.title_label.text() == "Packet Inspector"

    language_manager.set_language('ko')
    assert widget.title_label.text() == "패킷 인스펙터"

def test_file_progress_translation(app, qtbot):
    widget = FileProgressWidget()
    qtbot.addWidget(widget)

    # Force switch to Korean first to ensure change to English triggers signal
    language_manager.set_language('ko')
    language_manager.set_language('en')
    assert widget.cancel_btn.text() == "Cancel"

    language_manager.set_language('ko')
    assert widget.cancel_btn.text() == "취소"

def test_status_area_translation(app, qtbot):
    widget = StatusAreaWidget()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    assert widget.log_lbl.text() == "Status Log"

    language_manager.set_language('ko')
    assert widget.log_lbl.text() == "상태 로그"

def test_left_panel_translation(app, qtbot):
    widget = MainLeftSection()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    assert widget.port_tabs.toolTip() == "Port Tabs"

    language_manager.set_language('ko')
    assert widget.port_tabs.toolTip() == "포트 탭"

def test_right_panel_translation(app, qtbot):
    widget = MainRightSection()
    qtbot.addWidget(widget)

    language_manager.set_language('en')
    assert widget.tabs.tabText(0) == "Command List"
    assert widget.tabs.tabText(1) == "Inspector"

    language_manager.set_language('ko')
    assert widget.tabs.tabText(0) == "명령 리스트"
    assert widget.tabs.tabText(1) == "인스펙터"
