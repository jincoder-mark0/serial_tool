"""
언어 관리자 모듈

애플리케이션의 다국어(I18N) 지원을 담당합니다.
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
* 모듈 하단의 전역 인스턴스를 composition root가 `configure()`로 설정한다.
  class singleton(`__new__`)은 쓰지 않는다 — 생성처럼 보이는 설정은 읽는 사람을 속인다
* ResourcePath를 사용하여 실행 환경(Dev/Prod)에 따른 정확한 경로 탐색
* Lazy Initialization: 초기화 시 경로가 없으면 로드를 지연하여 시작 속도 최적화
"""
import os
from typing import Dict, Optional, List

# commentjson 라이브러리 지원 (주석이 포함된 JSON 파싱)
try:
    import commentjson as json
except ImportError:
    import json

from PyQt5.QtCore import QObject, pyqtSignal

from core.logger import logger
from core.resource_path import ResourcePath


class LanguageManager(QObject):
    """다국어 리소스를 관리하고 텍스트 번역을 제공하는 관리자 클래스.

    WHY 전역 인스턴스를 유지하는가:
        "현재 언어"는 앱 전체에 하나뿐인 값이고, 텍스트 조회는 452곳의 위젯 내부
        `retranslate_ui()`에서 일어난다. 이것을 생성자 주입으로 바꾸면 위젯 트리
        전체(약 25개 클래스)에 인자를 관통시켜야 하는데, 그렇게 해서 고쳐지는
        결함이 없다.

        이 프로젝트는 같은 성격의 값을 이미 전역으로 인정했다 — S-050의
        `view/managers/theme_state.py`가 "현재 테마"를 어느 매니저도 아닌 리프
        모듈에 둔 것이 그 판단이다. 언어 카탈로그는 같은 종류이고 크기만 크다.

        `ThemeManager`/`ColorManager`를 주입으로 바꾼 것과 다른 결론인 이유는,
        그 둘에는 실제 결함이 있었기 때문이다(주입한 ResourcePath가 무시됨,
        import만으로 파일 I/O). 여기에는 둘 다 없다 — 아래 `configure()`는 실제로
        다시 로드하고, `resource_path` 없이 만들면 파일을 읽지 않는다.

    WHY `__new__`를 없앴는가:
        과거에는 `__new__` 기반 class singleton이라 `main.py`의
        `LanguageManager(resource_path)`가 **새 객체를 만드는 것처럼 보이지만 실은
        전역을 설정**했다. 읽는 사람이 속는다. 지금은 `configure()`로 하는 일이
        그대로 보인다.
    """

    # -------------------------------------------------------------------------
    # Signals & Attributes
    # -------------------------------------------------------------------------
    # 언어가 변경되었을 때 UI 컴포넌트들에게 알리는 시그널 (변경된 언어 코드 전달)
    language_changed = pyqtSignal(str)

    def __init__(self, resource_path: Optional[ResourcePath] = None) -> None:
        """
        LanguageManager 초기화

        Logic:
            - ResourcePath 설정 (None이면 로드를 지연)
            - 리소스 경로가 주어진 경우에만 언어 파일 로드 (Lazy Load)

        Args:
            resource_path: ResourcePath 인스턴스. None이면 로드하지 않고 대기한다
                — 이 지연 덕분에 import만으로는 파일을 읽지 않는다.

        Note:
            production에서 이 생성자를 직접 부르지 않는다. 모듈 하단의 전역
            `language_manager`를 `configure()`로 설정한다 — 새 인스턴스를 만들면
            위젯들이 구독한 전역과 다른 객체가 되어, 언어를 바꿔도 화면이 갱신되지
            않는다 (`tests/test_language_manager_contract.py`가 막는다).
        """
        super().__init__()

        self._resource_path = resource_path
        self._current_language = "en"  # 기본 언어
        # 전체 언어 데이터를 메모리에 저장 { 'en': {...}, 'ko': {...} }
        self.resources: Dict[str, Dict[str, str]] = {}

        # 경로가 있을 때만 로드하여 불필요한 스캔 방지
        if self._resource_path:
            self.load_languages()

    def configure(self, resource_path: ResourcePath) -> None:
        """리소스 경로를 설정하고 언어 파일을 (다시) 로드한다.

        composition root가 시작 시 한 번 호출한다. 과거에는 생성자를 다시 부르는
        형태였는데, 그 호출은 새 객체를 만드는 것처럼 보이면서 실제로는 기존
        전역을 설정하고 있었다.

        Args:
            resource_path: 언어 파일을 찾을 ResourcePath.
        """
        self._resource_path = resource_path
        self.load_languages()

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

    def get_text(
        self,
        key: str,
        default: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> str:
        """
        키(Key)에 해당하는 번역된 텍스트를 반환합니다.

        Logic:
            1. 대상 언어(기본값: 현재 언어)에서 키 조회
            2. 키가 없으면 기본 언어('en')에서 Fallback 조회
            3. 여전히 없으면 키(Key) 자체를 반환

        Args:
            key (str): 번역 키 (예: 'menu_file_open').
            default (Optional[str]): 번역 키가 없을 때 반환할 기본 텍스트.
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
        return text if text is not None else (default if default is not None else key)

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
            if text == self.get_text(key, language_code=language_code):
                return True
        return False

# 앱 전역 텍스트 카탈로그.
#
# 위젯 452곳이 자기 `retranslate_ui()`에서 이 인스턴스를 직접 조회하고, 17곳이
# `language_changed`를 구독한다. "현재 언어"는 앱 전체에 하나뿐인 값이므로
# `theme_state`(S-050)와 같은 성격으로 전역에 둔다 — 자세한 판단 근거는 클래스 docstring.
#
# ResourcePath 없이 만들므로 여기서는 파일을 읽지 않는다. 로드는 composition root가
# `language_manager.configure(resource_path)`를 부를 때 일어난다.
language_manager = LanguageManager()
