"""
명령어 처리기 모듈

사용자 입력 문자열을 전송 가능한 바이트 데이터로 변환합니다.

## WHY
* Presenter 계층에 산재된 명령어 가공 로직의 중복 제거 (DRY 원칙)
* 설정(SettingsManager)에 따른 접두사/접미사 처리의 일관성 보장
* Hex 문자열 변환 및 에러 처리 로직의 중앙 집중화

## WHAT
* 텍스트 명령어에 Prefix/Suffix 설정 적용
* HEX/ASCII 모드에 따른 데이터 인코딩
* 변환 실패 시 예외 처리

## HOW
* 정적 메서드(Static Method)를 통해 상태 없이 순수 로직 수행
* SettingsManager를 조회하여 현재 설정값 적용
"""
from typing import Tuple
from core.settings_manager import SettingsManager
from constants import ConfigKeys

class CmdProcessor:
    """
    명령어 가공 및 변환 유틸리티 클래스
    """

    @staticmethod
    def process_cmd(text: str, hex_mode: bool, use_prefix: bool, use_suffix: bool) -> bytes:
        """
        명령어 텍스트를 설정에 맞춰 바이트 데이터로 변환

        Logic:
            - 설정된 Prefix/Suffix 적용
            - Hex 모드일 경우 공백 제거 후 bytes 변환
            - ASCII 모드일 경우 UTF-8 인코딩

        Args:
            text (str): 원본 명령어 텍스트
            hex_mode (bool): HEX 모드 여부
            use_prefix (bool): 접두사 사용 여부
            use_suffix (bool): 접미사 사용 여부

        Returns:
            bytes: 전송 가능한 바이트 데이터

        Raises:
            ValueError: 유효하지 않은 HEX 문자열일 경우
        """
        settings = SettingsManager()
        final_text = text

        # Prefix 적용
        if use_prefix:
            prefix = settings.get(ConfigKeys.CMD_PREFIX, "")
            final_text = prefix + final_text

        # Suffix 적용
        if use_suffix:
            suffix = settings.get(ConfigKeys.CMD_SUFFIX, "")
            final_text = final_text + suffix

        # 데이터 변환
        if hex_mode:
            # 공백 제거 후 Hex 변환
            return bytes.fromhex(final_text.replace(' ', ''))
        else:
            return final_text.encode('utf-8')
