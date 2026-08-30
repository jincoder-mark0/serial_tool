"""
언어 파일 무결성 검사 스크립트

다국어 JSON 파일들의 키 동기화 상태와 미번역 항목 유무를 검증합니다.
주로 CI/CD 파이프라인에서 빌드 전 검사 용도로 사용됩니다.

## WHY
* 번역 키가 누락된 채로 배포되어 UI에 빈 텍스트나 에러 코드가 노출되는 것을 방지
* 'manage_language_keys.py'로 자동 생성된 `[TODO]` 항목이 실제 번역으로 수정되었는지 확인
* 언어 파일 간의 구조적 일관성 보장
* (S-048) 코드가 참조하는 키가 실제로 JSON에 존재하는지 검증 — 오타 키는 JSON
  대칭 검사만으로는 잡히지 않고 런타임에 조용히 원문(키 자체 또는 default)으로
  폴백된다(S-020 `manual_panel_title` 사고 유형).
* (S-048) en/ko 값 사이의 `.format()` 플레이스홀더(`{0}`, `{1}` ...) 개수 불일치
  검증 — 불일치 시 특정 언어에서만 `.format()` 호출이 `IndexError`로 죽는다.

## WHAT
* 기준 언어(EN)와 대상 언어(KO) 파일 로드
* 양방향 키 집합 비교 (차집합 연산)
* 값(Value) 내의 `[TODO]` 마커 스캔
* `view/`·`presenter/`를 AST로 스캔해 `get_text("literal_key")` 형태의 리터럴 키가
  JSON에 실재하는지 검증(동적 키는 검출 불가하므로 경고로만 분리 보고 — 실패시키지 않음)
* en/ko 값의 `{N}` 플레이스홀더 개수 불일치 검사
* 결함 발견 시 비정상 종료 코드(Exit Code 1) 반환

## HOW
* `sys.exit(1)`을 사용하여 검사 실패 시 파이프라인 중단 유도
* 누락된 키 목록과 미번역 항목을 콘솔에 상세 출력
* 코드 참조 키 검사는 `ast` 모듈로 `get_text(...)` 호출의 첫 인자만 본다
  (Qt를 실행하지 않는 정적 분석 — tests/test_ui_guidelines.py와 동일한 접근)
"""
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Set, Dict, Tuple, List, Optional

# -----------------------------------------------------------------------------
# 설정 (Configuration)
# -----------------------------------------------------------------------------
# 스크립트 실행 위치 기준 리소스 경로 설정
# 프로젝트 루트에서 실행한다고 가정하거나, 파일 위치 기준으로 상대 경로 계산
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 실제 프로젝트 구조에 맞춰 경로 수정 필요 (예: ../resources/lang)
LANG_DIR = os.path.join(BASE_DIR, '..', 'resources', 'languages')

FILE_EN = 'en.json'
FILE_KO = 'ko.json'

# 코드 참조 키 검사 대상 디렉터리 (tests/test_ui_guidelines.py의 SCAN_DIRS와 동일 기준)
PROJECT_ROOT = Path(BASE_DIR).resolve().parent
CODE_SCAN_DIRS: Tuple[str, ...] = ("view", "presenter")

# `.get_text(...)`처럼 이 이름의 속성 호출만 키 조회로 간주한다.
GET_TEXT_METHOD_NAME = "get_text"

# 플레이스홀더 패턴: {0}, {1}, {} 등 (중첩 없는 단순 `.format()` 자리표시자)
PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


class LanguageIntegrityChecker:
    """
    언어 파일의 무결성을 검증하는 클래스
    """

    def __init__(self, directory: str, code_root: Optional[Path] = None):
        """
        LanguageIntegrityChecker 초기화

        Args:
            directory (str): 언어 파일이 위치한 디렉토리 경로.
            code_root (Optional[Path]): `CODE_SCAN_DIRS`(view/, presenter/)를 찾을
                기준 루트. None이면 실제 프로젝트 루트(PROJECT_ROOT)를 사용한다.
                테스트에서 가짜 소스 트리를 스캔시키기 위한 주입 지점(S-048).
        """
        self.directory = directory
        self.en_path = os.path.join(directory, FILE_EN)
        self.ko_path = os.path.join(directory, FILE_KO)
        self.code_root = code_root if code_root is not None else PROJECT_ROOT
        self.has_error = False

    def run_check(self) -> bool:
        """
        검사를 수행합니다.

        Logic:
            1. 파일 존재 여부 확인
            2. JSON 로드
            3. 키 불일치 검사 (Missing Keys)
            4. 미번역 항목 검사 (TODO Markers)

        Returns:
            bool: 검사 통과 시 True, 실패 시 False.
        """
        print(f"[INFO] Checking language files in: {self.directory}")

        if not self._check_files_exist():
            return False

        # 데이터 로드
        data_en = self._load_json(self.en_path)
        data_ko = self._load_json(self.ko_path)

        if data_en is None or data_ko is None:
            return False

        # 검사 1: 키 동기화 확인
        self._check_key_sync(data_en, data_ko)

        # 검사 2: 미번역 항목([TODO]) 확인
        self._check_todos(FILE_EN, data_en)
        self._check_todos(FILE_KO, data_ko)

        # 검사 3: 플레이스홀더({0}, {1}...) 개수 불일치 확인 (S-048)
        self._check_placeholder_counts(data_en, data_ko)

        # 검사 4: 코드가 참조하는 리터럴 키가 실재하는지 확인 (S-048)
        valid_keys = set(data_en.keys()) | set(data_ko.keys())
        self._check_key_usage(valid_keys)

        if self.has_error:
            print("\n[FAIL] Language integrity check failed.")
            return False
        else:
            print("\n[SUCCESS] All language files are valid.")
            return True

    def _check_files_exist(self) -> bool:
        """파일 존재 여부 확인"""
        if not os.path.exists(self.en_path):
            print(f"[ERROR] Missing file: {self.en_path}")
            return False
        if not os.path.exists(self.ko_path):
            print(f"[ERROR] Missing file: {self.ko_path}")
            return False
        return True

    def _load_json(self, path: str) -> Dict[str, str]:
        """
        JSON 파일 로드

        Args:
            path (str): 파일 경로.

        Returns:
            Dict[str, str]: 로드된 데이터. 실패 시 None.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Invalid JSON format in {path}: {e}")
            self.has_error = True
            return None

    def _check_key_sync(self, en_data: Dict[str, str], ko_data: Dict[str, str]) -> None:
        """
        양방향 키 누락 검사

        Args:
            en_data (Dict): 영어 데이터.
            ko_data (Dict): 한국어 데이터.
        """
        keys_en = set(en_data.keys())
        keys_ko = set(ko_data.keys())

        # EN에는 있지만 KO에 없는 키
        missing_in_ko = keys_en - keys_ko
        if missing_in_ko:
            self._report_missing_keys(FILE_KO, missing_in_ko)

        # KO에는 있지만 EN에 없는 키
        missing_in_en = keys_ko - keys_en
        if missing_in_en:
            self._report_missing_keys(FILE_EN, missing_in_en)

    def _report_missing_keys(self, filename: str, keys: Set[str]) -> None:
        """
        누락된 키 목록 출력 및 에러 플래그 설정

        Args:
            filename (str): 파일명.
            keys (Set[str]): 누락된 키 집합.
        """
        self.has_error = True
        print(f"\n[ERROR] Missing keys in '{filename}':")
        for key in sorted(keys):
            print(f"  - {key}")

    def _check_todos(self, filename: str, data: Dict[str, str]) -> None:
        """
        값(Value)에 '[TODO]' 마커가 포함되어 있는지 검사

        Args:
            filename (str): 파일명.
            data (Dict): 검사할 데이터.
        """
        todo_keys: List[str] = []

        for key, value in data.items():
            if isinstance(value, str) and "[TODO]" in value:
                todo_keys.append(key)

        if todo_keys:
            self.has_error = True
            print(f"\n[ERROR] Untranslated '[TODO]' items found in '{filename}':")
            for key in todo_keys:
                print(f"  - {key}: {data[key]}")

    def _check_placeholder_counts(self, en_data: Dict[str, str], ko_data: Dict[str, str]) -> None:
        """
        en/ko 공통 키의 `.format()` 플레이스홀더(`{0}`, `{1}`, `{}` 등) 개수가
        일치하는지 검사합니다.

        Logic:
            - 두 파일 모두에 존재하는 키만 비교 대상으로 삼는다(편도 누락은
              `_check_key_sync`가 이미 별도로 잡는다).
            - 플레이스홀더 '개수'만 비교한다(순서는 `.format(*args)`가 위치 인자를
              그대로 대입하므로 언어별 어순차로 `{0}`/`{1}` 위치가 바뀌는 것은
              정상이라 순서 자체는 검사하지 않는다).

        Args:
            en_data (Dict): 영어 데이터.
            ko_data (Dict): 한국어 데이터.
        """
        mismatches: List[Tuple[str, int, int]] = []

        common_keys = set(en_data.keys()) & set(ko_data.keys())
        for key in common_keys:
            en_value = en_data[key]
            ko_value = ko_data[key]
            if not isinstance(en_value, str) or not isinstance(ko_value, str):
                continue

            en_count = len(PLACEHOLDER_RE.findall(en_value))
            ko_count = len(PLACEHOLDER_RE.findall(ko_value))
            if en_count != ko_count:
                mismatches.append((key, en_count, ko_count))

        if mismatches:
            self.has_error = True
            print("\n[ERROR] Placeholder count mismatch between en/ko values:")
            for key, en_count, ko_count in sorted(mismatches):
                print(
                    f"  - {key}: en has {en_count} placeholder(s) "
                    f"({en_data[key]!r}), ko has {ko_count} ({ko_data[key]!r})"
                )

    def _check_key_usage(self, valid_keys: Set[str]) -> None:
        """
        `view/`·`presenter/` 소스가 참조하는 `get_text("literal_key")` 리터럴 키가
        실제로 JSON에 존재하는지 검사합니다.

        Logic:
            - AST로 `xxx.get_text(...)` 형태의 호출을 찾아 첫 인자(위치 인자
              또는 `key=` 키워드 인자)를 확인한다.
            - 리터럴 문자열(`ast.Constant`)이면 `valid_keys`에 있는지 검사 —
              없으면 오타 키로 간주해 실패시킨다.
            - f-string/변수/함수호출 등 리터럴이 아닌 표현식(예:
              `f"main_menu_theme_{theme_name.lower()}"`, `get_text(status_key)`)은
              정적으로 값을 알 수 없으므로 **검증하지 않고 경고로만 보고**한다
              (오탐으로 빌드를 실패시키지 않기 위함 — S-048).

        Args:
            valid_keys (Set[str]): en.json ∪ ko.json에 실재하는 키 집합.
        """
        missing: List[Tuple[str, int, str]] = []
        dynamic: List[Tuple[str, int, str]] = []

        for path in self._iter_code_files():
            rel_path = str(path.relative_to(self.code_root).as_posix())
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError) as e:
                self.has_error = True
                print(f"[ERROR] Could not parse {rel_path} for key usage check: {e}")
                continue

            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr != GET_TEXT_METHOD_NAME:
                    continue

                key_arg = self._extract_key_arg(node)
                if key_arg is None:
                    continue

                if isinstance(key_arg, ast.Constant) and isinstance(key_arg.value, str):
                    if key_arg.value not in valid_keys:
                        missing.append((rel_path, node.lineno, key_arg.value))
                else:
                    snippet = ast.unparse(key_arg) if hasattr(ast, "unparse") else ast.dump(key_arg)
                    dynamic.append((rel_path, node.lineno, snippet))

        if missing:
            self.has_error = True
            print("\n[ERROR] get_text() literal keys not found in en.json/ko.json:")
            for rel_path, lineno, key in sorted(missing):
                print(f"  - {rel_path}:{lineno}: '{key}'")

        if dynamic:
            # 동적 키는 정적으로 검증 불가 - 실패시키지 않고 경고만 출력한다.
            print("\n[WARN] get_text() dynamic key expressions (not statically verifiable):")
            for rel_path, lineno, snippet in sorted(dynamic):
                print(f"  - {rel_path}:{lineno}: {snippet}")

    @staticmethod
    def _extract_key_arg(call: ast.Call) -> Optional[ast.expr]:
        """
        `get_text(...)` 호출 노드에서 키에 해당하는 인자 표현식을 추출합니다.

        Args:
            call (ast.Call): 호출 AST 노드.

        Returns:
            Optional[ast.expr]: 키 인자 표현식. 인자가 없으면 None.
        """
        if call.args:
            return call.args[0]
        for kw in call.keywords:
            if kw.arg == "key":
                return kw.value
        return None

    def _iter_code_files(self):
        """CODE_SCAN_DIRS(view/, presenter/) 아래 모든 .py 파일을 재귀 순회합니다."""
        for sub_dir in CODE_SCAN_DIRS:
            base = self.code_root / sub_dir
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.py")):
                yield path


def main():
    """
    메인 실행 함수
    """
    # 경로 유효성 확인
    if not os.path.exists(LANG_DIR):
        print(f"[ERROR] Language directory not found: {LANG_DIR}")
        print("Please check the 'LANG_DIR' configuration in the script.")
        sys.exit(1)

    checker = LanguageIntegrityChecker(LANG_DIR)
    success = checker.run_check()

    # 종료 코드 설정 (성공=0, 실패=1)
    # CI/CD 파이프라인이 이 코드를 보고 빌드 성공/실패를 판단함
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
