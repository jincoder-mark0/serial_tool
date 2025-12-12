"""
UI 번역 테스트

언어 파일(en.json, ko.json)의 내용을 기반으로 UI 위젯의 번역이 올바르게 적용되는지 검증합니다.
하드코딩된 값 대신 실제 언어 파일을 참조하여 테스트합니다.

pytest tests\test_ui_translations.py -v
"""
import sys
import os

# 부모 디렉토리를 경로에 추가 (import 전에 실행)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import json
import pytest
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget
from typing import Dict, List, Tuple

from view.managers.lang_manager import lang_manager
from view.widgets.manual_ctrl import ManualCtrlWidget
from view.widgets.macro_list import MacroListWidget
from view.widgets.rx_log import RxLogWidget
from view.widgets.packet_inspector import PacketInspectorWidget
from view.widgets.file_progress import FileProgressWidget
from view.widgets.system_log import SystemLogWidget
from view.sections.main_left_section import MainLeftSection
from view.sections.main_right_section import MainRightSection

# 언어 파일 경로
LANG_DIR = Path(parent_dir) / "resources" / "languages"
EN_FILE = LANG_DIR / "en.json"
KO_FILE = LANG_DIR / "ko.json"

def load_language_files() -> Tuple[Dict, Dict]:
    """
    언어 파일 로드

    Returns:
        Tuple[Dict, Dict]: (en_data, ko_data)
    """
    with open(EN_FILE, 'r', encoding='utf-8') as f:
        en_data = json.load(f)

    with open(KO_FILE, 'r', encoding='utf-8') as f:
        ko_data = json.load(f)

    return en_data, ko_data

@pytest.fixture(scope="session")
def app():
    """QApplication 인스턴스 생성"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture(scope="session")
def lang_data():
    """언어 파일 데이터 로드"""
    return load_language_files()

def get_widget_text(widget, attr_name: str) -> str:
    """
    위젯의 텍스트 또는 툴팁 가져오기

    Args:
        widget: PyQt5 위젯
        attr_name: 속성 이름

    Returns:
        str: 텍스트 또는 툴팁
    """
    if not hasattr(widget, attr_name):
        return None

    obj = getattr(widget, attr_name)

    # 텍스트 가져오기
    if hasattr(obj, 'text'):
        return obj.text()
    elif hasattr(obj, 'toolTip'):
        return obj.toolTip()
    elif hasattr(obj, 'placeholderText'):
        return obj.placeholderText()

    return None

class TestManualCtrlWidget:
    """ManualCtrlWidget 번역 테스트"""

    def test_button_translations(self, app, qtbot, lang_data):
        """버튼 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = ManualCtrlWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.send_manual_cmd_btn.text() == en_data.get("manual_ctrl_btn_send", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.send_manual_cmd_btn.text() == ko_data.get("manual_ctrl_btn_send", "")

    def test_checkbox_translations(self, app, qtbot, lang_data):
        """체크박스 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = ManualCtrlWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.hex_chk.text() == en_data.get("manual_ctrl_chk_hex", "")
        assert widget.local_echo_chk.text() == en_data.get("manual_ctrl_chk_local_echo", "")
        assert widget.prefix_chk.text() == en_data.get("manual_ctrl_chk_prefix", "")
        assert widget.suffix_chk.text() == en_data.get("manual_ctrl_chk_suffix", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.hex_chk.text() == ko_data.get("manual_ctrl_chk_hex", "")
        assert widget.local_echo_chk.text() == ko_data.get("manual_ctrl_chk_local_echo", "")

class TestMacroListWidget:
    """MacroListWidget 번역 테스트"""

    def test_button_tooltips(self, app, qtbot, lang_data):
        """버튼 툴팁 번역 검증"""
        en_data, ko_data = lang_data
        widget = MacroListWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.add_row_btn.toolTip() == en_data.get("macro_list_btn_add_row_tooltip", "")
        assert widget.del_row_btn.toolTip() == en_data.get("macro_list_btn_del_row_tooltip", "")
        assert widget.up_row_btn.toolTip() == en_data.get("macro_list_btn_up_row_tooltip", "")
        assert widget.down_row_btn.toolTip() == en_data.get("macro_list_btn_down_row_tooltip", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.add_row_btn.toolTip() == ko_data.get("macro_list_btn_add_row_tooltip", "")
        assert widget.del_row_btn.toolTip() == ko_data.get("macro_list_btn_del_row_tooltip", "")

class TestRxLogWidget:
    """RxLogWidget 번역 테스트"""

    def test_button_translations(self, app, qtbot, lang_data):
        """버튼 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = RxLogWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.rx_clear_log_btn.text() == en_data.get("rx_btn_clear", "")
        assert widget.rx_toggle_data_log_btn.text() == en_data.get("rx_btn_save", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.rx_clear_log_btn.text() == ko_data.get("rx_btn_clear", "")
        assert widget.rx_toggle_data_log_btn.text() == ko_data.get("rx_btn_save", "")

    def test_checkbox_translations(self, app, qtbot, lang_data):
        """체크박스 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = RxLogWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.rx_hex_chk.text() == en_data.get("rx_chk_hex", "")
        assert widget.rx_timestamp_chk.text() == en_data.get("rx_chk_timestamp", "")
        assert widget.rx_pause_chk.text() == en_data.get("rx_chk_pause", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.rx_hex_chk.text() == ko_data.get("rx_chk_hex", "")
        assert widget.rx_timestamp_chk.text() == ko_data.get("rx_chk_timestamp", "")

class TestPacketInspectorWidget:
    """PacketInspectorWidget 번역 테스트"""

    def test_title_translation(self, app, qtbot, lang_data):
        """제목 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = PacketInspectorWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.title_lbl.text() == en_data.get("inspector_grp_title", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.title_lbl.text() == ko_data.get("inspector_grp_title", "")

class TestFileProgressWidget:
    """FileProgressWidget 번역 테스트"""

    def test_button_translation(self, app, qtbot, lang_data):
        """버튼 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = FileProgressWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.cancel_btn.text() == en_data.get("file_prog_btn_cancel", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.cancel_btn.text() == ko_data.get("file_prog_btn_cancel", "")

class TestSystemLogWidget:
    """SystemLogWidget 번역 테스트"""

    def test_title_translation(self, app, qtbot, lang_data):
        """제목 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = SystemLogWidget()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.system_log_title.text() == en_data.get("system_title", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.system_log_title.text() == ko_data.get("system_title", "")

class TestMainRightSection:
    """MainRightSection 번역 테스트"""

    def test_tab_translations(self, app, qtbot, lang_data):
        """탭 텍스트 번역 검증"""
        en_data, ko_data = lang_data
        widget = MainRightSection()
        qtbot.addWidget(widget)

        # 영어
        lang_manager.set_language('en')
        assert widget.tabs.tabText(0) == en_data.get("right_tab_macro_list", "")
        assert widget.tabs.tabText(1) == en_data.get("right_tab_packet", "")

        # 한국어
        lang_manager.set_language('ko')
        assert widget.tabs.tabText(0) == ko_data.get("right_tab_macro_list", "")
        assert widget.tabs.tabText(1) == ko_data.get("right_tab_packet", "")

class TestLanguageFileIntegrity:
    """언어 파일 무결성 테스트"""

    def test_language_files_exist(self):
        """언어 파일 존재 확인"""
        assert EN_FILE.exists(), f"English language file not found: {EN_FILE}"
        assert KO_FILE.exists(), f"Korean language file not found: {KO_FILE}"

    def test_language_files_valid_json(self, lang_data):
        """언어 파일이 유효한 JSON인지 확인"""
        en_data, ko_data = lang_data
        assert isinstance(en_data, dict), "en.json should be a dictionary"
        assert isinstance(ko_data, dict), "ko.json should be a dictionary"

    def test_language_files_have_same_keys(self, lang_data):
        """영어와 한국어 파일이 동일한 키를 가지는지 확인"""
        en_data, ko_data = lang_data
        en_keys = set(en_data.keys())
        ko_keys = set(ko_data.keys())

        missing_in_ko = en_keys - ko_keys
        missing_in_en = ko_keys - en_keys

        assert not missing_in_ko, f"Keys missing in ko.json: {missing_in_ko}"
        assert not missing_in_en, f"Keys missing in en.json: {missing_in_en}"

    def test_no_empty_values(self, lang_data):
        """빈 값이 없는지 확인"""
        en_data, ko_data = lang_data

        empty_en = [k for k, v in en_data.items() if not v or not v.strip()]
        empty_ko = [k for k, v in ko_data.items() if not v or not v.strip()]

        assert not empty_en, f"Empty values in en.json: {empty_en}"
        assert not empty_ko, f"Empty values in ko.json: {empty_ko}"
