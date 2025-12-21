"""
언어 파일 무결성 검사 스크립트

다국어 JSON 파일들의 키 동기화 상태와 미번역 항목 유무를 검증합니다.
주로 CI/CD 파이프라인에서 빌드 전 검사 용도로 사용됩니다.

## WHY
* 번역 키가 누락된 채로 배포되어 UI에 빈 텍스트나 에러 코드가 노출되는 것을 방지
* 'manage_language_keys.py'로 자동 생성된 `[TODO]` 항목이 실제 번역으로 수정되었는지 확인
* 언어 파일 간의 구조적 일관성 보장

## WHAT
* 기준 언어(EN)와 대상 언어(KO) 파일 로드
* 양방향 키 집합 비교 (차집합 연산)
* 값(Value) 내의 `[TODO]` 마커 스캔
* 결함 발견 시 비정상 종료 코드(Exit Code 1) 반환

## HOW
* `sys.exit(1)`을 사용하여 검사 실패 시 파이프라인 중단 유도
* 누락된 키 목록과 미번역 항목을 콘솔에 상세 출력
"""
import json
import os
import sys
from typing import Set, Dict, Tuple, List

# -----------------------------------------------------------------------------
# 설정 (Configuration)
# -----------------------------------------------------------------------------
# 스크립트 실행 위치 기준 리소스 경로 설정
# 프로젝트 루트에서 실행한다고 가정하거나, 파일 위치 기준으로 상대 경로 계산
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 실제 프로젝트 구조에 맞춰 경로 수정 필요 (예: ../resources/lang)
LANG_DIR = os.path.join(BASE_DIR, '..', 'resources', 'lang')

FILE_EN = 'en.json'
FILE_KO = 'ko.json'


class LanguageIntegrityChecker:
    """
    언어 파일의 무결성을 검증하는 클래스
    """

    def __init__(self, directory: str):
        """
        LanguageIntegrityChecker 초기화

        Args:
            directory (str): 언어 파일이 위치한 디렉토리 경로.
        """
        self.directory = directory
        self.en_path = os.path.join(directory, FILE_EN)
        self.ko_path = os.path.join(directory, FILE_KO)
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