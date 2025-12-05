try:
    import commentjson as json
except ImportError:
    import json
    print("Warning: commentjson not found, using standard json. Comments in language files will not be supported.")
import os
from typing import Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from core.logger import logger

class LanguageManager(QObject):
    """
    애플리케이션 언어 관리 클래스 (싱글톤 패턴 적용).
    JSON 파일에서 언어 리소스를 로드하고 다국어 텍스트를 제공합니다.
    """
    language_changed = pyqtSignal(str)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
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
        # 프로젝트 루트 경로 계산 (view/language_manager.py 기준)
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

    def get_text(self, key: str) -> str:
        """
        현재 언어에 맞는 텍스트를 반환합니다.

        Args:
            key (str): 텍스트 키.

        Returns:
            str: 번역된 텍스트. 키가 없으면 키 자체를 반환.
        """
        lang_dict = self.resources.get(self.current_language, {})
        text = lang_dict.get(key)

        if text is None:
            # 현재 언어에 키가 없으면 기본 언어(영어)에서 시도
            if self.current_language != 'en':
                fallback_dict = self.resources.get('en', {})
                text = fallback_dict.get(key)

        # 여전히 없으면 키 자체를 반환
        return text if text is not None else key

# 전역 인스턴스
language_manager = LanguageManager()
