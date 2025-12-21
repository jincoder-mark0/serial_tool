"""
스마트 라인 에디터 모듈

HEX 입력 모드와 자동 포맷팅을 지원하는 커스텀 라인 에디터입니다.

## WHY
* 시리얼 통신에서 빈번한 HEX 데이터 입력의 편의성 제공
* 잘못된 문자 입력을 사전에 방지하여 데이터 무결성 확보

## WHAT
* QSmartLineEdit: QLineEdit 기반 커스텀 위젯
* HEX 모드 토글 기능 (0-9, A-F, 공백만 입력 허용)
* 소문자 입력 시 자동 대문자 변환

## HOW
* QRegExpValidator를 사용한 입력 제한
* keyPressEvent 오버라이딩을 통한 실시간 문자 변환 이벤트 재발생
"""
from typing import Optional
from PyQt5.QtWidgets import QLineEdit, QWidget
from PyQt5.QtGui import QRegExpValidator, QKeyEvent
from PyQt5.QtCore import QRegExp


class QSmartLineEdit(QLineEdit):
    """
    HEX 모드와 일반 텍스트 모드를 지원하는 스마트 라인 에디트입니다.
    HEX 모드일 때는 0-9, A-F, 공백만 입력을 허용하고 자동으로 대문자로 변환합니다.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        QSmartLineEdit 초기화

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self._hex_mode = False
        self._ascii_validator = None  # 기본적으로 모든 입력 허용 (None)

        # HEX 모드용 검증기 (0-9, A-F, a-f, 공백)
        # 정규식: 16진수 문자와 공백만 허용
        hex_regex = QRegExp("[0-9A-Fa-f ]+")
        self._hex_validator = QRegExpValidator(hex_regex)

    def set_hex_mode(self, enabled: bool) -> None:
        """
        HEX 모드 활성화/비활성화를 설정합니다.

        Logic:
            - 활성화 시: HEX 검증기(Validator) 적용
            - 비활성화 시: 검증기 해제 (모든 입력 허용)

        Args:
            enabled (bool): True면 HEX 모드, False면 ASCII 모드.
        """
        self._hex_mode = enabled
        if enabled:
            self.setValidator(self._hex_validator)
        else:
            self.setValidator(self._ascii_validator)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        키 입력 이벤트를 처리합니다.

        Logic:
            - HEX 모드일 때 입력된 텍스트가 소문자 a-f 사이인지 확인
            - 소문자라면 대문자로 변환한 새 이벤트 생성하여 부모 클래스에 전달
            - 그 외의 경우 원래 이벤트를 그대로 처리

        Args:
            event (QKeyEvent): 키보드 입력 이벤트.
        """
        if self._hex_mode:
            text = event.text()
            # 입력된 값이 문자열이고 비어있지 않은 경우
            if text and text.isalnum():
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