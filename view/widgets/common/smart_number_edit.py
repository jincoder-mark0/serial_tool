from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp, Qt

class SmartNumberEdit(QLineEdit):
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
