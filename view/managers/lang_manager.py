"""
언어 관리자 모듈

애플리케이션의 다국어 지원을 담당합니다.

## WHY
* 다국어 UI 지원으로 사용자 접근성 향상
* 언어 전환 시 실시간 UI 업데이트
* 중앙 집중식 번역 관리
* Fallback 메커니즘으로 누락된 번역 처리

## WHAT
* JSON 기반 언어 리소스 로드
* 현재 언어 설정 및 변경 Signal 발행
* 언어 키 기반 텍스트 조회
* 지원 언어 목록 제공
* Fallback 언어 지원 (영어)

## HOW
* Singleton 패턴으로 전역 인스턴스 제공
* commentjson으로 주석 포함 JSON 파싱
* PyQt Signal로 언어 변경 알림
* Dictionary로 언어별 텍스트 관리
* ResourcePath로 동적 경로 처리
"""
from core.logger import logger
try:
    import commentjson as json
except ImportError:
    import json
    logger.warning("Warning: commentjson not found, using standard json. Comments in language files will not be supported.")
import os
from typing import Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger

class LangManager(QObject):
    """
    언어 관리자 (Singleton)

    JSON 파일에서 언어 리소스를 로드하고 다국어 텍스트를 제공합니다.
    """
    language_changed = pyqtSignal(str)  # 언어 변경 Signal

    _instance = None
    _resource_path = None

    def __new__(cls, *args, **kwargs):
        """Singleton 인스턴스 생성"""
        if cls._instance is None:
            cls._instance = super(LangManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path=None):
        """
        LangManager 초기화

        Args:
            resource_path: ResourcePath 인스턴스. None이면 기본 경로 사용
        """
        # ResourcePath가 전달되면 항상 업데이트하고 리로드
        if resource_path is not None:
            LangManager._resource_path = resource_path
            self.load_languages()

        if self._initialized:
            return

        super().__init__()
        self._initialized = True

        self.current_language = 'en'
        self.resources: Dict[str, Dict[str, str]] = {}

        # ResourcePath가 없는 경우(최초 import 시), Fallback 경로로 로드 시도
        if resource_path is None:
            self.load_languages()

    def load_languages(self) -> None:
        """
        언어 파일(*.json) 로드

        Logic:
            - ResourcePath 또는 Fallback 경로 결정
            - 언어 디렉토리의 모든 JSON 파일 스캔
            - 파일명을 언어 코드로 사용 (예: en.json → 'en')
            - JSON 파싱 및 Dictionary에 저장
            - 에러 발생 시 로깅 후 계속 진행
        """
        if LangManager._resource_path is not None:
            # ResourcePath가 제공되었으면 사용
            lang_dir = LangManager._resource_path.languages_dir
        else:
            # Fallback: 상대 경로 계산
            # view/managers/lang_manager.py → project_root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            lang_dir = os.path.join(base_dir, 'resources', 'languages')

        if not os.path.exists(lang_dir):
            logger.error(f"Language directory not found: {lang_dir}")
            return

        # 모든 JSON 파일 로드
        for filename in os.listdir(lang_dir):
            if filename.endswith('.json'):
                lang_code = os.path.splitext(filename)[0]
                file_path = os.path.join(lang_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.resources[lang_code] = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load language file {filename}: {e}")

    def set_language(self, lang_code: str) -> None:
        """
        현재 언어 설정 및 Signal 발행

        Args:
            lang_code: 설정할 언어 코드 (예: 'en', 'ko')
        """
        if lang_code in self.resources and self.current_language != lang_code:
            self.current_language = lang_code
            self.language_changed.emit(lang_code)

    def get_text(self, key: str, lang_code: Optional[str] = None) -> str:
        """
        언어 키에 해당하는 텍스트 반환

        Logic:
            - 지정된 언어(또는 현재 언어)에서 키 조회
            - 키가 없으면 Fallback 언어(영어)에서 조회
            - 여전히 없으면 키 자체 반환

        Args:
            key: 텍스트 키
            lang_code: 언어 코드. None이면 현재 언어 사용

        Returns:
            str: 번역된 텍스트. 키가 없으면 키 자체 반환
        """
        target_lang = lang_code if lang_code else self.current_language
        lang_dict = self.resources.get(target_lang, {})
        text = lang_dict.get(key)

        # Fallback: 영어에서 조회
        if text is None and target_lang != 'en':
            fallback_dict = self.resources.get('en', {})
            text = fallback_dict.get(key)

        # 여전히 없으면 키 자체 반환
        return text if text is not None else key

    def get_supported_languages(self) -> list:
        """
        지원되는 모든 언어 코드 목록 반환

        Returns:
            list: 언어 코드 리스트 (예: ['en', 'ko'])
        """
        return list(self.resources.keys())

    def text_matches_key(self, text: str, key: str) -> bool:
        """
        텍스트가 특정 키의 어떤 언어 번역과 일치하는지 확인

        Args:
            text: 확인할 텍스트
            key: 언어 키

        Returns:
            bool: 일치하면 True, 아니면 False
        """
        for lang_code in self.get_supported_languages():
            if text == self.get_text(key, lang_code):
                return True
        return False

# 전역 인스턴스
lang_manager = LangManager()
