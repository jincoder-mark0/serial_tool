"""
언어 키 관리 도구

이 스크립트는 다음 작업을 수행합니다:
1. view 폴더의 모든 .py 파일에서 사용되는 language_manager.get_text() 호출을 분석
2. 모듈별로 키를 그룹화
3. 주석이 추가된 언어 템플릿 JSON 파일 생성
4. 누락되거나 사용되지 않는 키 확인
"""

import re
try:
    import commentjson as json
except ImportError:
    import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set

# view 폴더의 모든 .py 파일에서 get_text 호출을 찾고 모듈별로 그룹화
def extract_keys_by_module(view_dir: Path) -> Dict[str, Set[str]]:
    """
    view 폴더의 각 모듈에서 사용되는 키를 추출합니다.

    Args:
        view_dir: view 폴더의 경로

    Returns:
        Dict[str, Set[str]]: 모듈명을 키로, 사용되는 키 집합을 값으로 하는 딕셔너리
    """
    keys_by_module = defaultdict(set)

    for py_file in view_dir.rglob("*.py"):
        # __pycache__ 및 __init__.py 제외
        if '__pycache__' in str(py_file) or py_file.name == '__init__.py':
            continue

        # 모듈 경로 생성 (예: widgets/manual_control, dialogs/font_settings)
        try:
            relative_path = py_file.relative_to(view_dir)
            module_path = str(relative_path.with_suffix('')).replace('\\', '/')
        except ValueError:
            continue

        content = py_file.read_text(encoding='utf-8')
        # get_text("key") 또는 get_text('key') 패턴 찾기
        matches = re.findall(r'get_text\(["\']([^"\']+)["\']\)', content)

        if matches:
            keys_by_module[module_path].update(matches)

    return keys_by_module

def get_module_display_name(module_path: str) -> str:
    """모듈 경로를 사람이 읽기 쉬운 이름으로 변환"""
    # 파일 이름을 기반으로 자동 생성
    parts = module_path.split('/')
    if len(parts) == 1:
        # 단일 파일 (예: main_window)
        name = parts[0].replace('_', ' ').title()
    else:
        # 중첩된 파일 (예: widgets/port_settings_widget)
        category = parts[-2].rstrip('s').title()  # 'widgets' -> 'Widget'
        name = parts[-1].replace('_', ' ').title()
        name = f"{name} {category}"

    return name

def generate_template(keys_by_module: Dict[str, Set[str]], output_file: Path, language: str = "en"):
    """
    모듈별로 그룹화되고 주석이 추가된 언어 템플릿 파일을 생성합니다.

    Args:
        keys_by_module: 모듈별 키 딕셔너리
        output_file: 출력 파일 경로
        language: 언어 코드 ("en" 또는 "ko")
    """
    # 기존 JSON 파일이 있으면 값을 가져옴
    existing_values = {}
    if Path(output_file).exists():
        try:
            existing_values = json.loads(Path(output_file).read_text(encoding='utf-8'))
            # 주석 키 제거 (이전 버전에서 생성된 경우)
            existing_values = {k: v for k, v in existing_values.items() if not k.startswith("//")}
        except json.JSONDecodeError:
            print(f"⚠ 기존 템플릿 파일이 손상되어 새로 생성합니다: {output_file}")
            existing_values = {}

    # 모듈을 알파벳순으로 정렬하되, 중요한 순서를 우선
    priority_order = ['main_window', 'widgets', 'panels', 'dialogs']

    def get_sort_key(path):
        for idx, priority in enumerate(priority_order):
            if path.startswith(priority):
                return idx, path
        return len(priority_order), path

    sorted_modules = sorted(keys_by_module.keys(), key=get_sort_key)

    # JSON 파일 생성 (주석은 별도 처리)
    lines = ["{\n"]

    # 공통 키들 (여러 모듈에서 사용)
    common_keys = set()
    key_count = defaultdict(int)
    for keys in keys_by_module.values():
        for key in keys:
            key_count[key] += 1

    # 3개 이상의 모듈에서 사용되는 키를 공통 키로 분류
    common_keys = {key for key, count in key_count.items() if count >= 3}

    # 공통 키 먼저 출력
    if common_keys:
        lines.append('  // ============================================\n')
        lines.append('  // Common Keys (Used in multiple modules)\n')
        lines.append('  // ============================================\n')
        for key in sorted(common_keys):
            value = existing_values.get(key, f"TODO: {key}")
            lines.append(f'  "{key}": "{value}",\n')
        lines.append('\n')

    # 모듈별 키 출력
    for module_path in sorted_modules:
        keys = keys_by_module[module_path]
        # 공통 키가 아닌 것만 출력
        module_specific_keys = keys - common_keys

        if module_specific_keys:
            display_name = get_module_display_name(module_path)
            # 파일 경로 추가 (예: widgets/port_settings_widget.py)
            file_path = f"{module_path}.py"
            lines.append('  // ============================================\n')
            lines.append(f'  // {display_name} ({file_path}),\n')
            lines.append('  // ============================================\n')

            for key in sorted(module_specific_keys):
                value = existing_values.get(key, f"TODO: {key}")
                lines.append(f'  "{key}": "{value}",\n')
            lines.append('\n')

    # 마지막 쉼표 제거
    if lines[-1] == '\n':
        lines.pop()
    lines[-1] = lines[-1].rstrip(',\n') + '\n'

    lines.append("}\n")

    # 실제로는 정상 JSON으로 저장 (주석은 키로 포함)
    output_file.write_text(''.join(lines), encoding='utf-8')

    print(f"✓ 템플릿 파일 생성: {output_file}")
    print(f"  - 공통 키: {len(common_keys)}개")
    print(f"  - 모듈별 키: {sum(len(keys - common_keys) for keys in keys_by_module.values())}개")
    print(f"  - 발견된 모듈: {len(sorted_modules)}개")

def check_missing_and_unused(view_dir: Path, language_files: Dict[str, Path]):
    """
    누락되거나 사용되지 않는 키를 확인

    Args:
        view_dir: view 폴더의 경로
        language_files: 언어 파일의 경로

    """

    used_keys = set()

    for py_file in view_dir.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue
        content = py_file.read_text(encoding='utf-8')
        matches = re.findall(r'get_text\(["\']([^"\']+)["\']\)', content)
        used_keys.update(matches)

    # JSON 파일의 키들 읽기
    language_keys = {}
    for lang, json_path in language_files.items():
        try:
            if not json_path.exists():
                print(f"⚠ 경고: {lang}.json 파일이 존재하지 않습니다: {json_path}")
                language_keys[lang] = set()
                continue

            content = json_path.read_text(encoding='utf-8')
            language_keys[lang] = set(json.loads(content).keys())
        except json.JSONDecodeError as e:
            print(f"⚠ 경고: {lang}.json 파일 파싱 오류: {e}")
            language_keys[lang] = set()
        except Exception as e:
            print(f"⚠ 경고: {lang}.json 파일 읽기 오류: {e}")
            language_keys[lang] = set()

    # 비교
    print("\n=== 누락된 키 확인 ===")

    for lang, keys in language_keys.items():
        missing = used_keys - keys
        if missing:
            print(f"\n❌ {lang}.json에 없는 키 ({len(missing)}개):")
            for key in sorted(missing):
                print(f"  - {key}")
        else:
            print(f"\n✓ {lang}.json: 모든 키가 존재합니다!")

    print("\n=== 사용되지 않는 키 확인 ===")
    all_keys = set().union(*language_keys.values()) if language_keys.values() else set()
    unused = all_keys - used_keys

    if unused:
        print(f"\n⚠ 사용되지 않는 키 ({len(unused)}개):")
        for key in sorted(unused):
            print(f"  - {key}")
    else:
        print("\n✓ 모든 키가 사용되고 있습니다!")

    print(f"\n=== 통계 ===")
    print(f"코드에서 사용: {len(used_keys)}개")
    for lang, keys in language_keys.items():
        print(f"{lang}.json: {len(keys)}개")


def main():
    root_dir = Path(__file__).parent.parent
    view_dir = root_dir / "view"
    language_dir = root_dir / "resources/languages"
    language_template_file = language_dir / "template_en.json"
    language_files = {
        "en": language_dir / "en.json",
        "ko": language_dir / "ko.json"
    }

    """메인 함수"""
    print("=" * 60)
    print("언어 키 관리 도구")
    print("=" * 60)

    # 1. 모듈별 키 추출
    print("\n[1] 모듈별 키 추출 중...")
    keys_by_module = extract_keys_by_module(view_dir)
    print(f"✓ {len(keys_by_module)}개 모듈에서 키 추출 완료")

    # 2. 템플릿 생성
    print("\n[2] 언어 템플릿 생성 중...")
    generate_template(
        keys_by_module,
        language_template_file,
        "en"
    )

    # 3. 누락/미사용 키 확인
    print("\n[3] 키 검증 중...")
    check_missing_and_unused(view_dir,language_files)

    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()
