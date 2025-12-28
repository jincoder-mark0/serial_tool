"""
언어 관리자 모듈

애플리케이션의 다국어(I18N) 지원을 담당하는 싱글톤 클래스입니다.
JSON 기반의 언어 리소스를 로드하고, 런타임 언어 변경 및 텍스트 조회를 수행합니다.

## WHY
* 하드코딩된 문자열 대신 키(Key) 기반의 텍스트 조회를 통해 유지보수성 향상
* 애플리케이션 재시작 없이 런타임에 즉시 언어를 변경하는 UX 제공 (Dynamic Switching)
* 중앙 집중식 번역 관리 및 누락된 번역에 대한 Fallback(영어) 처리

## WHAT
* JSON(및 commentjson) 기반 언어 파일 로드 및 파싱
* 현재 언어 상태 관리 및 변경 시그널(language_changed) 방출
* 키를 이용한 번역 텍스트 반환 (get_text) 및 Fallback 로직
* 메타데이터(_meta_lang_name)를 이용한 동적 언어 목록 제공

## HOW
* Singleton 패턴으로 전역에서 접근 가능한 인스턴스 제공
* ResourcePath를 사용하여 실행 환경(Dev/Prod)에 따른 정확한 경로 탐색
* Lazy Initialization: 초기화 시 경로가 없으면 로드를 지연하여 시작 속도 최적화
"""
import os
from typing import Dict, Optional, List, Any

# commentjson 라이브러리 지원 (주석이 포함된 JSON 파싱)
try:
    import commentjson as json
except ImportError:
    import json

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger
from core.resource_path import ResourcePath


class LanguageManager(QObject):
    """
    다국어 리소스를 관리하고 텍스트 번역을 제공하는 관리자 클래스 (Singleton).
    """

    # -------------------------------------------------------------------------
    # Signals & Attributes
    # -------------------------------------------------------------------------
    # 언어가 변경되었을 때 UI 컴포넌트들에게 알리는 시그널 (변경된 언어 코드 전달)
    language_changed = pyqtSignal(str)

    _instance = None
    _resource_path: Optional[ResourcePath] = None

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

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """
        LanguageManager 초기화

        Logic:
            - 중복 초기화 방지 (Singleton)
            - ResourcePath 설정
            - 리소스 경로가 주입된 경우에만 언어 파일 로드 수행 (Lazy Load)
            - super().__init__() 호출 (QObject 초기화)

        Args:
            resource_path: ResourcePath 인스턴스. None이면 내부에서 생성하지 않고 대기.
        """
        # 1. 싱글톤 중복 초기화 방지 및 재설정 로직
        if hasattr(self, '_initialized') and self._initialized:
            # 이미 초기화되었더라도, 새로운 resource_path가 들어오면 업데이트 및 리로드
            if resource_path is not None:
                self._resource_path = resource_path
                self.load_languages()
            return

        # 2. QObject 초기화 (가장 먼저 호출해야 함)
        super().__init__()

        # 3. 리소스 경로 설정 (None일 수 있음)
        self._resource_path = resource_path

        # 4. 멤버 변수 초기화
        self._current_language = "en"  # 기본 언어
        # 전체 언어 데이터를 메모리에 저장 { 'en': {...}, 'ko': {...} }
        self.resources: Dict[str, Dict[str, str]] = {}

        # 5. 로직 실행 (경로가 있을 때만 로드하여 불필요한 스캔 방지)
        if self._resource_path:
            self.load_languages()

        # 6. 초기화 완료 플래그 설정
        self._initialized = True

    def load_languages(self) -> None:
        """
        언어 파일(*.json)을 디렉토리에서 스캔하여 메모리에 로드합니다.

        Logic:
            - ResourcePath를 통해 언어 디렉토리 경로 획득
            - 디렉토리 내의 모든 .json 파일 스캔 (template 제외)
            - 파일명을 언어 코드로 사용 (예: ko.json -> 'ko')
            - JSON 파싱 후 self.resources 딕셔너리에 저장

        Raises:
            IOError: 파일 읽기 실패 시 로그 출력 (중단되지 않음)
        """
        if not self._resource_path:
            # 경로가 설정되지 않았으면 로드하지 않음 (Lazy Init 대기)
            return

        language_dir = self._resource_path.languages_dir

        if not language_dir.exists():
            logger.error(f"Language directory not found: {language_dir}")
            return

        logger.debug(f"Scanning languages in: {language_dir}")

        # 디렉토리 내 파일 순회
        try:
            for filename in os.listdir(language_dir):
                # .json 파일이면서 template으로 시작하지 않는 파일만 로드
                if filename.endswith('.json') and not filename.startswith('template'):
                    language_code = os.path.splitext(filename)[0]
                    file_path = language_dir / filename

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            self.resources[language_code] = json.load(f)
                        logger.debug(f"Loaded language: {language_code} ({len(self.resources[language_code])} keys)")
                    except Exception as e:
                        logger.error(f"Failed to load language file {filename}: {e}")
        except OSError as e:
            logger.error(f"Failed to list language directory: {e}")

    def set_language(self, language_code: str) -> None:
        """
        애플리케이션의 현재 언어를 변경하고 시그널을 방출합니다.

        Logic:
            1. 요청한 언어 코드가 로드된 리소스에 존재하는지 확인
            2. 현재 언어와 다를 경우 변경 수행
            3. language_changed 시그널 방출

        Args:
            language_code (str): 변경할 언어 코드 (예: 'en', 'ko').
        """
        if language_code in self.resources and self._current_language != language_code:
            logger.info(f"Switching language to: {language_code}")
            self._current_language = language_code
            self.language_changed.emit(language_code)
        elif language_code not in self.resources:
            logger.warning(f"Attempted to switch to unknown language: {language_code}")

    def get_text(self, key: str, language_code: Optional[str] = None) -> str:
        """
        키(Key)에 해당하는 번역된 텍스트를 반환합니다.

        Logic:
            1. 대상 언어(기본값: 현재 언어)에서 키 조회
            2. 키가 없으면 기본 언어('en')에서 Fallback 조회
            3. 여전히 없으면 키(Key) 자체를 반환

        Args:
            key (str): 번역 키 (예: 'menu_file_open').
            language_code (Optional[str]): 강제 조회할 언어 코드. None이면 현재 언어 사용.

        Returns:
            str: 번역된 텍스트 또는 키.
        """
        target_lang = language_code if language_code else self._current_language

        # 1. 대상 언어 딕셔너리 가져오기
        language_dict = self.resources.get(target_lang, {})
        text = language_dict.get(key)

        # 2. Fallback Mechanism (영어로 조회)
        if text is None and target_lang != 'en':
            fallback_dict = self.resources.get('en', {})
            text = fallback_dict.get(key)

        # 3. 최후의 수단: 키 반환
        return text if text is not None else key

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
        JSON 파일 내부의 '_meta_lang_name' 키를 사용하여 표시 이름을 가져옵니다.

        Returns:
            Dict[str, str]: {언어코드: 표시이름} 형태의 딕셔너리.
                            예: {'en': 'English', 'ko': '한국어'}
        """
        languages = {}
        for code, data in self.resources.items():
            # 메타데이터 키(_meta_lang_name) 확인, 없으면 코드를 대문자로 표시
            name = data.get("_meta_lang_name", code.upper())
            languages[code] = name

        # 만약 로드된 언어가 없으면 기본값 반환
        if not languages:
            return {"en": "English"}

        return languages

    def get_supported_languages(self) -> List[str]:
        """
        지원하는 모든 언어 코드 목록을 리스트로 반환합니다.

        Returns:
            List[str]: 언어 코드 리스트 (예: ['en', 'ko']).
        """
        return list(self.resources.keys())

    def text_matches_key(self, text: str, key: str) -> bool:
        """
        주어진 텍스트가 특정 키의 번역문(어떤 언어든)과 일치하는지 확인합니다.
        (주로 UI 상태 확인이나 역방향 조회 시 사용)

        Logic:
            - 로드된 모든 언어를 순회하며 해당 키의 번역값과 텍스트를 비교

        Args:
            text (str): 화면에 표시된 텍스트.
            key (str): 비교할 번역 키.

        Returns:
            bool: 일치하면 True.
        """
        for language_code in self.get_supported_languages():
            if text == self.get_text(key, language_code):
                return True
        return False

# 전역에서 접근 가능한 싱글톤 인스턴스 생성
# 여기서는 ResourcePath가 없으므로 초기화만 되고 로드는 수행하지 않음 (Lazy Load)
language_manager = LanguageManager()