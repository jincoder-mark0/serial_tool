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
        self.current_language = "ko"
        self.resources: Dict[str, Dict[str, str]] = {}
        self.load_resources()

    def load_resources(self) -> None:
        """
        언어 리소스 파일을 로드합니다.
        config/languages/ 디렉토리에서 JSON 파일을 읽어옵니다.
        """
        # 기본 경로 설정
        if hasattr(os, '_MEIPASS'):
            # PyInstaller 번들 환경
            base_path = os.path.join(os._MEIPASS, 'config', 'languages')
        else:
            # 개발 모드 환경
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.join(os.path.dirname(current_dir), 'config', 'languages')
        
        # 지원 언어 목록
        supported_languages = ['en', 'ko']
        
        for lang in supported_languages:
            lang_file = os.path.join(base_path, f'{lang}.json')
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.resources[lang] = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Language file not found: {lang_file}")
                self.resources[lang] = {}
            except json.JSONDecodeError as e:
                print(f"Error: Failed to parse {lang_file}: {e}")
                self.resources[lang] = {}
        
        # 최소 리소스 확인
        if not self.resources.get('en') and not self.resources.get('ko'):
            print("Warning: No language resources loaded, using fallback")
            self.resources = self._get_fallback_resources()
    
    def _get_fallback_resources(self) -> Dict[str, Dict[str, str]]:
        """폴백 리소스 (JSON 파일 로드 실패 시 사용)"""
        return {
            "en": {"app_title": "SerialTool", "ready": "Ready", "error": "Error"},
            "ko": {"app_title": "시리얼 툴", "ready": "준비", "error": "오류"}
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
