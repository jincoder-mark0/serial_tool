"""
뷰 번역 테스트 모듈

다국어 지원(Internationalization) 기능과 UI 동적 번역을 검증합니다.

## WHY
* 언어 변경 시 UI 텍스트가 즉시 반영되지 않는 버그 방지
* 지원하지 않는 언어 키 요청 시 프로그램이 멈추지 않도록 예외 처리 검증
* LanguageManager Singleton의 상태 관리 무결성 확인

## WHAT
* LanguageManager: 언어 설정 변경, 시그널 방출, 텍스트 조회
* UI Integration: 언어 변경 시그널에 반응하여 위젯 텍스트(Label, Button) 갱신

## HOW
* LanguageManager에 테스트용 가짜 번역 데이터 주입
* qtbot.waitSignal을 사용하여 언어 변경 시그널 감지
* 실제 위젯(ManualControlPanel)을 생성하여 setText 호출 결과 확인

pytest tests/test_view_translations.py -v
"""
import pytest
from PyQt5.QtWidgets import QPushButton, QLabel

from view.managers.language_manager import language_manager
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.packet_panel import PacketPanel


@pytest.fixture(autouse=True)
def reset_language_manager():
    """
    각 테스트 전후로 LanguageManager의 상태를 초기화합니다.
    Singleton 객체이므로 테스트 간 상태 공유를 방지해야 합니다.
    """
    # 초기 상태(영어)로 설정
    language_manager.set_language('en')

    # 테스트용 번역 데이터 주입 (파일 I/O 의존성 제거)
    # 실제 구현에서는 JSON 파일에서 로드하지만, 테스트의 결정성을 위해 직접 주입
    language_manager._translations = {
        "en": {
            "manual_btn_send": "Send",
            "manual_panel_title": "Manual Control",
            "packet_btn_clear": "Clear"
        },
        "ko": {
            "manual_btn_send": "전송",
            "manual_panel_title": "수동 제어",
            "packet_btn_clear": "지우기"
        }
    }

    yield

    # 테스트 종료 후 정리 (필요 시)
    language_manager.set_language('en')


class TestLanguageManager:
    """
    LanguageManager의 핵심 기능을 검증하는 테스트 클래스
    """

    def test_set_language_emits_signal(self, qtbot):
        """
        언어 변경 시 시그널 방출 테스트

        Logic:
            - 현재 언어가 'en'인지 확인
            - set_language('ko') 호출
            - language_changed 시그널 발생 여부 확인
        """
        # GIVEN: 초기 상태 확인
        assert language_manager.get_current_language() == 'en'

        # WHEN: 언어 변경 (SignalSpy 사용)
        with qtbot.waitSignal(language_manager.language_changed) as blocker:
            language_manager.set_language('ko')

        # THEN: 시그널 발생 및 상태 변경 확인
        assert blocker.signal_triggered
        assert language_manager.get_current_language() == 'ko'

    def test_get_text_translation(self):
        """
        키 기반 텍스트 조회 및 번역 테스트

        Logic:
            - 영어 모드에서 get_text 호출 -> 영어 값 반환
            - 한국어 모드로 변경
            - get_text 호출 -> 한국어 값 반환
        """
        # GIVEN: 영어 모드
        language_manager.set_language('en')

        # WHEN & THEN
        assert language_manager.get_text("manual_btn_send") == "Send"

        # WHEN: 한국어 모드 변경
        language_manager.set_language('ko')

        # THEN
        assert language_manager.get_text("manual_btn_send") == "전송"

    def test_get_text_fallback(self):
        """
        존재하지 않는 키 요청 시 Fallback 테스트

        Logic:
            - 번역 사전에 없는 키 요청
            - 에러 없이 키 자체나 기본값을 반환해야 함
        """
        # GIVEN
        key = "unknown_key_123"
        default_val = "Default Text"

        # WHEN
        result = language_manager.get_text(key, default_val)

        # THEN: 기본값 반환 확인
        assert result == default_val


class TestViewRetranslation:
    """
    UI 위젯의 동적 재번역(RetranslateUi) 기능을 검증하는 테스트 클래스
    """

    def test_manual_control_panel_retranslation(self, qtbot):
        """
        ManualControlPanel의 언어 변경 반응 테스트

        Logic:
            - 패널 생성 (기본 영어)
            - 버튼 텍스트가 "Send"인지 확인
            - 언어를 한국어로 변경
            - 버튼 텍스트가 "전송"으로 바뀌었는지 확인
        """
        # GIVEN: 패널 생성
        panel = ManualControlPanel()
        qtbot.addWidget(panel)

        # 초기 상태(영어) 확인
        # ManualControlPanel -> ManualControlWidget -> btn_send
        btn_send = panel.manual_control_widget.btn_send
        title_label = panel.title_label

        assert btn_send.text() == "Send"
        assert title_label.text() == "Manual Control"

        # WHEN: 언어 변경 (한국어)
        with qtbot.waitSignal(language_manager.language_changed):
            language_manager.set_language('ko')

        # THEN: 텍스트 갱신 확인
        assert btn_send.text() == "전송"
        assert title_label.text() == "수동 제어"

    def test_packet_panel_retranslation(self, qtbot):
        """
        PacketPanel의 언어 변경 반응 테스트

        Logic:
            - 패킷 패널 생성
            - Clear 버튼 텍스트 확인
            - 언어 변경 후 텍스트 변경 확인
        """
        # GIVEN: 패널 생성
        panel = PacketPanel()
        qtbot.addWidget(panel)

        btn_clear = panel.btn_clear

        # 초기 상태(영어)
        assert btn_clear.text() == "Clear"

        # WHEN: 언어 변경 (한국어)
        with qtbot.waitSignal(language_manager.language_changed):
            language_manager.set_language('ko')

        # THEN: 텍스트 갱신 확인
        assert btn_clear.text() == "지우기"

    def test_dynamic_switching_multiple_times(self, qtbot):
        """
        언어를 여러 번 전환해도 UI가 정상적으로 업데이트되는지 테스트

        Logic:
            - En -> Ko -> En 순서로 전환
            - 각 단계마다 텍스트 확인
        """
        # GIVEN
        panel = ManualControlPanel()
        qtbot.addWidget(panel)
        btn = panel.manual_control_widget.btn_send

        # 1. En -> Ko
        language_manager.set_language('ko')
        assert btn.text() == "전송"

        # 2. Ko -> En
        language_manager.set_language('en')
        assert btn.text() == "Send"