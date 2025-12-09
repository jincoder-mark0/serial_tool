try:
    import commentjson as json
except ImportError:
    import json
    print("Warning: commentjson not found, using standard json. Comments in language files will not be supported.")
import os
from typing import Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger

class LangManager(QObject):
    """
    애플리케이션 언어 관리 클래스 (싱글톤 패턴 적용).
    JSON 파일에서 언어 리소스를 로드하고 다국어 텍스트를 제공합니다.
    """
    language_changed = pyqtSignal(str)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LangManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self.current_language = 'en'
        self.resources: Dict[str, Dict[str, str]] = {}
        self.load_languages()

    def load_languages(self) -> None:
        """
        config/languages 디렉토리에서 언어 파일(*.json)을 로드합니다.
        """
        # 프로젝트 루트 경로 계산 (view/lang_manager.py 기준)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lang_dir = os.path.join(base_dir, 'config', 'languages')

        if not os.path.exists(lang_dir):
            logger.error(f"Language directory not found: {lang_dir}")
            return

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
        현재 언어를 설정하고 시그널을 발생시킵니다.

        Args:
            lang_code (str): 설정할 언어 코드 (예: 'en', 'ko').
        """
        if lang_code in self.resources and self.current_language != lang_code:
            self.current_language = lang_code
            self.language_changed.emit(lang_code)

    def get_text(self, key: str, lang_code: Optional[str] = None) -> str:
        """
        지정된 언어(또는 현재 언어)에 맞는 텍스트를 반환합니다.

        Args:
            key (str): 텍스트 키.
            lang_code (Optional[str]): 언어 코드. None이면 현재 언어 사용.

        Returns:
            str: 번역된 텍스트. 키가 없으면 키 자체를 반환.
        """
        target_lang = lang_code if lang_code else self.current_language
        lang_dict = self.resources.get(target_lang, {})
        text = lang_dict.get(key)

        if text is None:
            # 지정된 언어에 키가 없으면 기본 언어(영어)에서 시도
            if target_lang != 'en':
                fallback_dict = self.resources.get('en', {})
                text = fallback_dict.get(key)

        # 여전히 없으면 키 자체를 반환
        return text if text is not None else key

    def get_supported_languages(self) -> list:
        """
        지원되는 모든 언어 코드 목록을 반환합니다.

        Returns:
            list: 언어 코드 리스트 (예: ['en', 'ko']).
        """
        return list(self.resources.keys())

    def text_matches_key(self, text: str, key: str) -> bool:
        """
        주어진 텍스트가 특정 키의 어떤 언어 번역과 일치하는지 확인합니다.

        Args:
            text (str): 확인할 텍스트.
            key (str): 언어 키.

        Returns:
            bool: 일치하면 True, 아니면 False.
        """
        for lang_code in self.get_supported_languages():
            if text == self.get_text(key, lang_code):
                return True
        return False

# 전역 인스턴스
lang_manager = LangManager()
