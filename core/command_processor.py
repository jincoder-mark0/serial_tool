"""
명령어 처리기 모듈

사용자 입력 문자열을 전송 가능한 바이트 데이터로 변환합니다.

## WHY
* Hex 문자열 변환 및 에러 처리 로직의 중앙 집중화

## WHAT
* 텍스트 명령어에 Prefix/Suffix 설정 적용 (인자로 전달받음)
* HEX/ASCII 모드에 따른 데이터 인코딩
* 변환 실패 시 예외 처리

## HOW
* 인자로 받은 Prefix/Suffix를 적용하여 순수 로직 수행
"""
from typing import Optional
from core.settings_manager import SettingsManager # 주석 참조용으로 유지
from common.constants import ConfigKeys # 주석 참조용으로 유지

class CommandProcessor:
    """
    명령어 가공 및 변환 유틸리티 클래스
    """

    @staticmethod
    def process_command(text: str, hex_mode: bool, prefix: Optional[str] = None, suffix: Optional[str] = None) -> bytes:
        """
        명령어 텍스트를 설정에 맞춰 바이트 데이터로 변환

        Logic:
            - **인자로 전달받은** Prefix/Suffix 적용
            - Hex 모드일 경우 공백 제거 후 bytes 변환
            - ASCII 모드일 경우 UTF-8 인코딩

        Args:
            text (str): 원본 명령어 텍스트
            hex_mode (bool): HEX 모드 여부
            prefix (Optional[str]): 적용할 접두사. (None일 경우 무시)
            suffix (Optional[str]): 적용할 접미사. (None일 경우 무시)

        Returns:
            bytes: 전송 가능한 바이트 데이터

        Raises:
            ValueError: 유효하지 않은 HEX 문자열일 경우
        """
        final_text = text

        # Prefix 적용
        if prefix:
            final_text = prefix + final_text

        # Suffix 적용
        if suffix:
            final_text = final_text + suffix

        # 데이터 변환
        if hex_mode:
            # 공백 제거 후 Hex 변환
            return bytes.fromhex(final_text.replace(' ', ''))
        else:
            return final_text.encode('utf-8')
