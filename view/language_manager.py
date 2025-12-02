import json
import os
from typing import Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal

class LanguageManager(QObject):
    """
    애플리케이션 다국어 지원을 관리하는 클래스입니다.
    JSON 파일에서 언어 리소스를 로드하고, 언어 변경 시그널을 발생시킵니다.
    """
    
    language_changed = pyqtSignal(str)  # 언어 코드 (예: 'ko', 'en')

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
        self.current_language = "en"
        self.resources: Dict[str, Dict[str, str]] = {}
        self.load_resources()

    def load_resources(self) -> None:
        """
        언어 리소스 파일을 로드합니다.
        기본적으로 'en'과 'ko'를 지원합니다.
        실제 파일이 없으면 하드코딩된 기본값을 사용합니다.
        """
        # TODO: 추후 외부 JSON 파일에서 로드하도록 확장 가능
        self.resources = {
            "en": {
                "app_title": "SerialTool",
                "file": "File",
                "view": "View",
                "help": "Help",
                "connect": "Connect",
                "disconnect": "Disconnect",
                "send": "Send",
                "clear": "Clear",
                "settings": "Settings",
                "exit": "Exit",
                "ready": "Ready",
                "error": "Error",
                "preferences": "Preferences",
                "about": "About"
            },
            "ko": {
                "app_title": "시리얼 툴",
                "file": "파일",
                "view": "보기",
                "help": "도움말",
                "connect": "연결",
                "disconnect": "연결 해제",
                "send": "전송",
                "clear": "지우기",
                "settings": "설정",
                "exit": "종료",
                "ready": "준비",
                "error": "오류",
                "preferences": "환경설정",
                "about": "정보"
            }
        }

    def set_language(self, lang_code: str) -> None:
        """
        현재 언어를 설정합니다.
        
        Args:
            lang_code (str): 언어 코드 ('en', 'ko' 등)
        """
        if lang_code in self.resources and lang_code != self.current_language:
            self.current_language = lang_code
            self.language_changed.emit(lang_code)

    def get_text(self, key: str) -> str:
        """
        현재 언어에 해당하는 텍스트를 반환합니다.
        
        Args:
            key (str): 텍스트 키
            
        Returns:
            str: 번역된 텍스트. 키가 없으면 키 자체를 반환.
        """
        lang_dict = self.resources.get(self.current_language, {})
        return lang_dict.get(key, key)

# 전역 인스턴스
language_manager = LanguageManager()
