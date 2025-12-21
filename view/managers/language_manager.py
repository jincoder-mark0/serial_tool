"""
언어 관리자 모듈

애플리케이션의 다국어(I18N) 지원을 담당하는 싱글톤 클래스입니다.
런타임 언어 변경, JSON 기반 번역 파일 로드, 키 기반 텍스트 조회를 수행합니다.

## WHY
* 하드코딩된 문자열 대신 키(Key) 기반의 텍스트 조회를 통해 유지보수성 향상
* 애플리케이션 재시작 없이 런타임에 즉시 언어를 변경하는 UX 제공
* UI 컴포넌트들에게 언어 변경 이벤트를 일관되게 전파

## WHAT
* JSON 언어 파일 로드 및 파싱
* 현재 언어 상태 관리 및 변경 시그널(language_changed) 방출
* 키를 이용한 번역 텍스트 반환 (get_text)
* 지원 가능한 언어 목록 스캔 및 제공

## HOW
* Singleton 패턴으로 전역에서 접근 가능한 인스턴스 제공
* QObject를 상속받아 PyQt 시그널/슬롯 메커니즘 활용
* os.path 및 json 모듈을 사용하여 리소스 파일 처리
"""
import json
import os
from typing import Dict, Optional, List, Any

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger


class LanguageManager(QObject):
    """
    다국어 리소스를 관리하고 텍스트 번역을 제공하는 관리자 클래스
    """

    # -------------------------------------------------------------------------
    # Singleton Instance & Signals
    # -------------------------------------------------------------------------
    _instance = None

    # 언어가 변경되었을 때 UI 컴포넌트들에게 알리는 시그널
    language_changed = pyqtSignal()

    # 언어 코드별 표시 이름 매핑 (UI 표시용)
    DISPLAY_NAMES = {
        "en": "English",
        "ko": "한국어",
        "jp": "日本語",
        "cn": "中文"
    }

    def __new__(cls, *args, **kwargs):
        """
        Singleton 인스턴스 보장 및 초기화 플래그 설정
        """
        if not cls._instance:
            # QObject 상속 시 super().__new__에는 인자를 전달하지 않는 것이 안전함
            cls._instance = super(LanguageManager, cls).__new__(cls)
            # 인스턴스 생성 직후 플래그 초기화
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, resource_path: Optional[str] = None) -> None:
        """
        LanguageManager 초기화

        Logic:
            - 중복 초기화 방지
            - super().__init__() 호출 (QObject 초기화 필수)
            - 리소스 경로 설정 (전달받은 경로 우선 사용)
            - 기본 언어 로드

        Args:
            resource_path (Optional[str]): 리소스 루트 디렉토리 경로.
        """
        # 싱글톤 중복 초기화 방지
        if hasattr(self, '_initialized') and self._initialized:
            return

        super().__init__()

        self._current_language = "en"
        self._translations: Dict[str, str] = {}

        # 언어 파일 디렉토리 설정
        # main.py에서 전달받은 resource_path가 있으면 사용 (우선순위 높음)
        if resource_path:
            self._language_dir = os.path.join(resource_path, 'lang')
        else:
            # Fallback: 현재 파일 기준 상대 경로
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._language_dir = os.path.join(base_dir, '..', '..', 'resources', 'lang')

        # 초기 언어 로드
        self._load_translations(self._current_language)

        self._initialized = True

    def load_languages(self) -> None:
        """
        언어 파일 디렉토리에서 사용 가능한 언어들을 스캔하고 로드 준비를 합니다.
        (현재 구조에서는 초기화 시점에 자동으로 수행되지만, 명시적 재스캔이 필요할 때 사용)
        """
        if not os.path.exists(self._language_dir):
            logger.warning(f"Language directory not found: {self._language_dir}")
            return

        # 디렉토리 존재 확인 및 로그 출력
        logger.debug(f"Scanning languages in: {self._language_dir}")
        self.get_available_languages()

    def set_language(self, language_code: str) -> None:
        """
        애플리케이션 언어를 변경합니다.

        Logic:
            1. 현재 언어와 동일하면 무시
            2. 새 언어 파일 로드 시도
            3. 성공 시 현재 언어 업데이트 및 시그널 방출

        Args:
            language_code (str): 변경할 언어 코드 (예: 'en', 'ko').
        """
        if self._current_language == language_code:
            return

        logger.info(f"Switching language to: {language_code}")

        if self._load_translations(language_code):
            self._current_language = language_code
            # 모든 UI 컴포넌트에 변경 알림
            self.language_changed.emit()
        else:
            logger.error(f"Failed to switch language to {language_code}. File not found or invalid.")

    def get_text(self, key: str, language_code: Optional[str] = None) -> str:
        """
        키에 해당하는 번역된 텍스트를 반환합니다.

        Logic:
            - language_code가 제공되지 않으면 현재 로드된 번역 사용
            - 키가 없으면 키 자체를 반환 (Fallback)
            - [확장] 특정 언어 코드가 명시되면 해당 언어에서 조회 (현재는 캐시된 언어만 지원)

        Args:
            key (str): 번역 키 (예: 'menu_file_open').
            language_code (Optional[str]): 특정 언어로 강제 조회 시 사용 (현재 구현은 기본 언어 우선).

        Returns:
            str: 번역된 텍스트.
        """
        # 현재 구현에서는 메모리에 로드된 단일 언어 팩만 사용
        # 추후 다중 언어 동시 로드가 필요하면 _translations 구조 변경 필요
        return self._translations.get(key, key)

    def get_current_language(self) -> str:
        """
        현재 설정된 언어 코드를 반환합니다.

        Returns:
            str: 언어 코드 ('en', 'ko' 등).
        """
        return self._current_language

    def get_available_languages(self) -> Dict[str, str]:
        """
        사용 가능한 언어 목록을 딕셔너리 형태로 반환합니다.

        Logic:
            - 언어 폴더 스캔하여 .json 파일 탐색
            - 파일명(code)을 DISPLAY_NAMES 맵을 이용해 표시 이름으로 변환
            - 파일이 없으면 기본값(English) 반환

        Returns:
            Dict[str, str]: {언어코드: 표시이름} 형태의 딕셔너리.
                            예: {"en": "English", "ko": "한국어"}
        """
        languages = {}

        # 디렉토리 존재 확인
        if os.path.exists(self._language_dir):
            try:
                for filename in os.listdir(self._language_dir):
                    if filename.endswith(".json"):
                        code = filename.replace(".json", "")
                        # 매핑된 이름이 있으면 사용, 없으면 코드 대문자로 표시
                        name = self.DISPLAY_NAMES.get(code, code.upper())
                        languages[code] = name
            except OSError as e:
                logger.error(f"Failed to list languages in {self._language_dir}: {e}")

        # 언어 파일이 하나도 없거나 디렉토리가 없는 경우 기본값 제공
        if not languages:
            logger.warning("No language files found. Using default English.")
            languages = {"en": "English"}

        return languages

    def get_supported_languages(self) -> list:
        """
        지원하는 언어 코드 목록을 리스트로 반환합니다.

        Returns:
            list: 언어 코드 문자열 리스트 (예: ['en', 'ko']).
        """
        return list(self.get_available_languages().keys())

    def text_matches_key(self, text: str, key: str) -> bool:
        """
        주어진 텍스트가 특정 키의 번역문과 일치하는지 확인합니다.
        (UI 상태 확인이나 역방향 조회 시 사용)

        Args:
            text (str): 화면에 표시된 텍스트.
            key (str): 비교할 번역 키.

        Returns:
            bool: 일치하면 True.
        """
        # 현재 언어 기준으로만 비교
        translated = self.get_text(key)
        return text == translated

    def _load_translations(self, language_code: str) -> bool:
        """
        JSON 파일에서 번역 데이터를 로드합니다.

        Logic:
            - 파일 경로 구성
            - JSON 로드 및 파싱
            - 실패 시 에러 로깅

        Args:
            language_code (str): 언어 코드.

        Returns:
            bool: 로드 성공 여부.
        """
        file_path = os.path.join(self._language_dir, f"{language_code}.json")

        if not os.path.exists(file_path):
            # 파일이 없을 경우 로그만 남기고 False 반환 (앱 크래시 방지)
            # logger.warning(f"Language file not found: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self._translations = json.load(f)
            logger.debug(f"Loaded translations for '{language_code}': {len(self._translations)} keys")
            return True
        except Exception as e:
            logger.error(f"Error loading translation file {file_path}: {e}")
            return False


# 전역에서 접근 가능한 싱글톤 인스턴스 생성
language_manager = LanguageManager()