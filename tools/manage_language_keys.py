"""
언어 키 관리 유틸리티 스크립트

다국어 지원을 위한 JSON 파일들(en.json, ko.json 등)의 키를 동기화하고 정렬합니다.

## WHY
* 수동으로 JSON 파일을 관리할 때 발생하는 키 누락(Missing Keys) 방지
* 여러 언어 파일 간의 정렬 순서를 통일하여 버전 관리(Git Diff) 가독성 향상
* 새로운 번역 키 추가 시 다른 언어 파일에도 자동으로 템플릿 생성

## WHAT
* 기준 언어(영어)와 대상 언어(한국어) 파일 로드
* 양방향 키 비교 및 누락된 키 감지
* 누락된 키에 대해 `[TODO]` 마커가 붙은 임시 값 삽입
* 모든 키를 알파벳 순으로 정렬하여 저장

## HOW
* `json` 모듈을 사용하여 데이터 로드/저장
* 집합(Set) 연산을 이용한 키 차집합 계산
* 딕셔너리 재구성을 통한 정렬 수행
"""
import json
import os
import sys
from typing import Dict, Any

# -----------------------------------------------------------------------------
# 설정 (Configuration)
# -----------------------------------------------------------------------------
# 스크립트 파일 기준 상대 경로로 리소스 디렉토리 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 프로젝트 구조에 따라 경로 조정 필요 (예: ../resources/lang)
LANG_DIR = os.path.join(BASE_DIR, 'resources', 'lang')

# 관리할 언어 파일 목록 (파일명)
FILE_EN = 'en.json'
FILE_KO = 'ko.json'


class LanguageKeyManager:
    """
    언어 파일 동기화 및 관리를 담당하는 클래스
    """

    def __init__(self, directory: str):
        """
        LanguageKeyManager 초기화

        Args:
            directory (str): 언어 파일이 위치한 디렉토리 경로.
        """
        self.directory = directory
        self.en_path = os.path.join(directory, FILE_EN)
        self.ko_path = os.path.join(directory, FILE_KO)

    def run(self) -> None:
        """
        동기화 작업을 실행합니다.

        Logic:
            1. 파일 존재 여부 확인
            2. JSON 데이터 로드
            3. 영어 <-> 한국어 양방향 키 동기화
            4. 키 정렬
            5. 파일 저장
        """
        print(f"[INFO] Target Directory: {self.directory}")

        if not self._check_files_exist():
            print("[ERROR] Language files not found. Please check the path.")
            return

        # 1. 데이터 로드
        data_en = self._load_json(self.en_path)
        data_ko = self._load_json(self.ko_path)

        if data_en is None or data_ko is None:
            return

        print(f"[INFO] Loaded keys - EN: {len(data_en)}, KO: {len(data_ko)}")

        # 2. 키 동기화 (Sync)
        # 영어 파일에 있는데 한국어에 없는 것 추가
        added_to_ko = self._sync_missing_keys(source=data_en, target=data_ko, tag="KO")
        # 한국어 파일에 있는데 영어에 없는 것 추가
        added_to_en = self._sync_missing_keys(source=data_ko, target=data_en, tag="EN")

        # 3. 정렬 (Sort)
        sorted_en = self._sort_dictionary(data_en)
        sorted_ko = self._sort_dictionary(data_ko)

        # 4. 저장 (Save)
        if added_to_ko or added_to_en:
            print("[INFO] Changes detected. Saving files...")
            self._save_json(self.en_path, sorted_en)
            self._save_json(self.ko_path, sorted_ko)
            print("[SUCCESS] Language files synchronized and sorted.")
        else:
            # 변경사항은 없어도 정렬 상태 보장을 위해 저장 수행 (선택적)
            self._save_json(self.en_path, sorted_en)
            self._save_json(self.ko_path, sorted_ko)
            print("[INFO] No missing keys found. Files sorted and saved.")

    def _check_files_exist(self) -> bool:
        """
        언어 파일들이 실제로 존재하는지 확인합니다.

        Returns:
            bool: 두 파일이 모두 존재하면 True.
        """
        return os.path.exists(self.en_path) and os.path.exists(self.ko_path)

    def _load_json(self, path: str) -> Dict[str, str]:
        """
        JSON 파일을 로드합니다.

        Args:
            path (str): 파일 경로.

        Returns:
            Dict[str, str]: 파싱된 딕셔너리 데이터. 실패 시 None.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load {path}: {e}")
            return None

    def _save_json(self, path: str, data: Dict[str, str]) -> None:
        """
        딕셔너리 데이터를 JSON 파일로 저장합니다.

        Logic:
            - UTF-8 인코딩 사용
            - ensure_ascii=False (한글 깨짐 방지)
            - indent=4 (가독성 확보)

        Args:
            path (str): 저장할 경로.
            data (Dict[str, str]): 저장할 데이터.
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Failed to save {path}: {e}")

    def _sync_missing_keys(self, source: Dict[str, Any], target: Dict[str, Any], tag: str) -> int:
        """
        소스에는 있지만 타겟에는 없는 키를 찾아 타겟에 추가합니다.

        Logic:
            - 소스 키 집합 - 타겟 키 집합 = 누락된 키 집합
            - 누락된 키에 대해 `[TODO]` 접두사를 붙여 타겟에 추가

        Args:
            source (Dict): 기준 데이터.
            target (Dict): 업데이트할 대상 데이터.
            tag (str): 로그용 태그 (예: "KO").

        Returns:
            int: 추가된 키의 개수.
        """
        missing_keys = set(source.keys()) - set(target.keys())
        count = 0

        for key in missing_keys:
            # 값은 소스의 값을 가져오되, 번역 필요 마커를 붙임
            source_value = source[key]
            # 문자열이 아닌 경우(중첩 딕셔너리)도 대비, 여기선 문자열 가정
            if isinstance(source_value, str):
                target[key] = f"[TODO] {source_value}"
            else:
                target[key] = source_value

            print(f"  [+] Added missing key to {tag}: '{key}'")
            count += 1

        return count

    def _sort_dictionary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        딕셔너리를 키(Key) 기준으로 알파벳 오름차순 정렬합니다.

        Args:
            data (Dict): 정렬할 딕셔너리.

        Returns:
            Dict: 정렬된 새 딕셔너리.
        """
        return dict(sorted(data.items()))


def main():
    """메인 실행 함수"""
    # 리소스 디렉토리가 없으면 생성 (개발 편의성)
    if not os.path.exists(LANG_DIR):
        print(f"[WARN] Resource directory not found at: {LANG_DIR}")
        print("[INFO] Creating dummy directory and files for demonstration...")
        os.makedirs(LANG_DIR, exist_ok=True)

        # 더미 파일 생성
        dummy_en = {"hello": "Hello", "world": "World", "only_en": "Only in English"}
        dummy_ko = {"hello": "안녕하세요", "world": "세상", "only_ko": "한국어에만 있음"}

        with open(os.path.join(LANG_DIR, FILE_EN), 'w', encoding='utf-8') as f:
            json.dump(dummy_en, f, indent=4)
        with open(os.path.join(LANG_DIR, FILE_KO), 'w', encoding='utf-8') as f:
            json.dump(dummy_ko, f, indent=4, ensure_ascii=False)

    # 매니저 실행
    manager = LanguageKeyManager(LANG_DIR)
    manager.run()


if __name__ == "__main__":
    main()