"""
동적 UI 번역 테스트

위젯의 속성을 자동으로 탐지하여 번역을 검증합니다.
명명 규칙(_btn, _lbl, _chk 등)을 활용하여 하드코딩 없이 테스트합니다.
"""
import sys
import os

# 부모 디렉토리를 경로에 추가 (import 전에 실행)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import json
import pytest
import re
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel, QCheckBox, QComboBox, QLineEdit, QTextEdit
from typing import Dict, List, Tuple, Type, Any

from view.managers.lang_manager import lang_manager
from view.widgets.manual_ctrl import ManualCtrlWidget
from view.widgets.macro_list import MacroListWidget
from view.widgets.rx_log import RxLogWidget
from view.widgets.packet_inspector import PacketInspectorWidget
from view.widgets.file_progress import FileProgressWidget
from view.widgets.system_log import SystemLogWidget

# 언어 파일 경로
LANG_DIR = Path(parent_dir) / "resources" / "languages"

# 위젯 타입별 접미사 매핑
WIDGET_SUFFIXES = {
    '_btn': (QPushButton, 'text'),
    '_lbl': (QLabel, 'text'),
    '_chk': (QCheckBox, 'text'),
    '_combo': (QComboBox, None),  # 콤보박스는 항목별로 다름
    '_input': (QLineEdit, 'text'),
    '_txt': (QTextEdit, None),  # 텍스트 에디트는 플레이스홀더 등 다양
}

def discover_language_files() -> Dict[str, Path]:
    """
    언어 파일 자동 탐지

    resources/languages 폴더의 모든 .json 파일을 찾아서 반환합니다.

    Returns:
        Dict[str, Path]: {언어코드: 파일경로} 딕셔너리
    """
    lang_files = {}

    if not LANG_DIR.exists():
        return lang_files

    for json_file in LANG_DIR.glob("*.json"):
        # 파일명에서 언어 코드 추출 (예: en.json -> en)
        lang_code = json_file.stem

        # template 파일은 제외
        if lang_code.startswith("template"):
            continue

        lang_files[lang_code] = json_file

    return lang_files

def load_language_files() -> Dict[str, Dict]:
    """
    모든 언어 파일 로드

    Returns:
        Dict[str, Dict]: {언어코드: 언어데이터} 딕셔너리
    """
    lang_files = discover_language_files()
    lang_data = {}

    for lang_code, file_path in lang_files.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lang_data[lang_code] = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")

    return lang_data

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

def find_translatable_widgets(widget_instance: Any) -> List[Tuple[str, Any, str]]:
    """
    위젯 인스턴스에서 번역 가능한 모든 위젯 찾기

    Args:
        widget_instance: 검사할 위젯 인스턴스

    Returns:
        List[Tuple[str, Any, str]]: (속성명, 위젯객체, 메서드명) 리스트
    """
    translatable = []

    for attr_name in dir(widget_instance):
        # private 속성 제외
        if attr_name.startswith('_'):
            continue

        try:
            attr = getattr(widget_instance, attr_name)
        except:
            continue

        # 위젯 타입별로 검사
        for suffix, (widget_type, method) in WIDGET_SUFFIXES.items():
            if attr_name.endswith(suffix) and isinstance(attr, widget_type):
                if method:
                    translatable.append((attr_name, attr, method))
                break

    return translatable

def attr_name_to_lang_key(attr_name: str, widget_class_name: str) -> str:
    """
    속성 이름을 언어 키로 변환

    예: send_manual_cmd_btn -> manual_ctrl_btn_send

    Args:
        attr_name: 위젯 속성 이름
        widget_class_name: 위젯 클래스 이름

    Returns:
        str: 예상되는 언어 키
    """
    # 클래스 이름에서 context 추출
    # ManualCtrlWidget -> manual_ctrl
    context_match = re.findall(r'[A-Z][a-z]+', widget_class_name)
    if context_match:
        context = '_'.join([word.lower() for word in context_match[:-1]])  # Widget 제외
    else:
        context = widget_class_name.lower()

    # 속성 이름에서 type과 name 추출
    # send_manual_cmd_btn -> btn_send_manual_cmd
    for suffix in WIDGET_SUFFIXES.keys():
        if attr_name.endswith(suffix):
            name_part = attr_name[:-len(suffix)]  # suffix 제거
            type_part = suffix[1:]  # _ 제거

            # 일반적인 패턴: {context}_{type}_{name}
            # 예: manual_ctrl_btn_send
            lang_key = f"{context}_{type_part}_{name_part}"
            return lang_key

    return None

def test_widget_translations_dynamic(app, qtbot, lang_data):
    """
    모든 위젯의 번역을 동적으로 검증

    이 테스트는 위젯의 속성을 자동으로 탐지하고,
    명명 규칙을 기반으로 언어 키를 추론하여 검증합니다.
    """
    en_data, ko_data = lang_data

    # 테스트할 위젯 클래스 목록
    widget_classes = [
        ManualCtrlWidget,
        MacroListWidget,
        RxLogWidget,
        PacketInspectorWidget,
        FileProgressWidget,
        SystemLogWidget,
    ]

    results = {
        'tested': 0,
        'passed': 0,
        'failed': [],
        'missing_keys': []
    }

    for widget_class in widget_classes:
        widget = widget_class()
        qtbot.addWidget(widget)

        # 번역 가능한 위젯 찾기
        translatable_widgets = find_translatable_widgets(widget)

        for attr_name, widget_obj, method in translatable_widgets:
            results['tested'] += 1

            # 언어 키 추론
            lang_key = attr_name_to_lang_key(attr_name, widget_class.__name__)

            if not lang_key:
                continue

            # 언어 파일에 키가 있는지 확인
            if lang_key not in en_data or lang_key not in ko_data:
                results['missing_keys'].append({
                    'widget': widget_class.__name__,
                    'attr': attr_name,
                    'expected_key': lang_key
                })
                continue

            # 영어 번역 검증
            lang_manager.set_language('en')
            try:
                actual_text = getattr(widget_obj, method)()
                expected_text = en_data[lang_key]

                if actual_text == expected_text:
                    results['passed'] += 1
                else:
                    results['failed'].append({
                        'widget': widget_class.__name__,
                        'attr': attr_name,
                        'lang': 'en',
                        'expected': expected_text,
                        'actual': actual_text
                    })
            except Exception as e:
                results['failed'].append({
                    'widget': widget_class.__name__,
                    'attr': attr_name,
                    'error': str(e)
                })

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"동적 번역 테스트 결과")
    print(f"{'='*60}")
    print(f"✓ 테스트된 위젯: {results['tested']}개")
    print(f"✓ 통과: {results['passed']}개")
    print(f"✗ 실패: {len(results['failed'])}개")
    print(f"⚠ 누락된 키: {len(results['missing_keys'])}개")

    if results['failed']:
        print(f"\n실패 상세:")
        for fail in results['failed']:
            print(f"  - {fail}")

    if results['missing_keys']:
        print(f"\n누락된 언어 키:")
        for missing in results['missing_keys']:
            print(f"  - {missing['widget']}.{missing['attr']} -> {missing['expected_key']}")

    # 실패가 있으면 테스트 실패
    assert len(results['failed']) == 0, f"{len(results['failed'])}개의 번역 불일치 발견"

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
