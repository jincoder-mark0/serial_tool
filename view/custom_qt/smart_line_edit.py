"""
스마트 라인 에디터 모듈

HEX 입력 모드와 자동 포맷팅을 지원하는 커스텀 라인 에디터입니다.

## WHY
* 시리얼 통신에서 빈번한 HEX 데이터 입력의 편의성 제공
* 잘못된 문자 입력을 사전에 방지하여 데이터 무결성 확보

## WHAT
* QLineEdit 기반 커스텀 위젯
* HEX 모드 토글 기능 (0-9, A-F 만 입력 허용)
* 소문자 입력 시 자동 대문자 변환

## HOW
* QRegExpValidator를 사용한 입력 제한
* keyPressEvent 오버라이딩을 통한 실시간 문자 변환
"""
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp

class QSmartLineEdit(QLineEdit):
    """
    HEX 모드와 일반 텍스트 모드를 지원하는 스마트 라인 에디트입니다.
    HEX 모드일 때는 0-9, A-F, 공백만 입력을 허용하고 자동으로 대문자로 변환합니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hex_mode = False
        self._ascii_validator = None # 기본적으로 모든 입력 허용

        # HEX 모드용 검증기 (0-9, A-F, a-f, 공백)
        hex_regex = QRegExp("[0-9A-Fa-f ]+")
        self._hex_validator = QRegExpValidator(hex_regex)

    def set_hex_mode(self, enabled: bool):
        """
        HEX 모드 활성화/비활성화를 설정합니다.
        """
        self._hex_mode = enabled
        if enabled:
            self.setValidator(self._hex_validator)
            # 현재 텍스트를 HEX 형식에 맞게 정리 (선택 사항)
            # self.setText(self.text().upper())
        else:
            self.setValidator(self._ascii_validator)

    def keyPressEvent(self, event):
        """
        키 입력 이벤트를 처리합니다.
        HEX 모드일 때 소문자를 대문자로 변환합니다.
        """
        if self._hex_mode:
            text = event.text()
            if text.isalnum():
                # 소문자 a-f를 대문자로 변환하여 입력
                if 'a' <= text <= 'f':
                    new_event = type(event)(
                        event.type(),
                        event.key(),
                        event.modifiers(),
                        text.upper(),
                        event.isAutoRepeat(),
                        event.count()
                    )
                    super().keyPressEvent(new_event)
                    return

        super().keyPressEvent(event)
