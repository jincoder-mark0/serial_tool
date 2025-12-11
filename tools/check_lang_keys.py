import re
try:
    import commentjson as json
except ImportError:
    import json
from pathlib import Path

# view 폴더의 모든 .py 파일에서 get_text 호출을 찾기
root_dir = Path(__file__).parent.parent
view_dir = root_dir / "view"
lang_dir = root_dir / "resources/languages"
used_keys = set()

for py_file in view_dir.rglob("*.py"):
    content = py_file.read_text(encoding='utf-8')
    # get_text("key") 또는 get_text('key') 패턴 찾기
    matches = re.findall(r'get_text\(["\']([^"\']+)["\']\)', content)
    used_keys.update(matches)

# JSON 파일의 키들 읽기
en_json = lang_dir / "en.json"
ko_json = lang_dir / "ko.json"

en_keys = set(json.loads(en_json.read_text(encoding='utf-8')).keys())
ko_keys = set(json.loads(ko_json.read_text(encoding='utf-8')).keys())

# 비교
print("=== 코드에서 사용되지만 JSON에 없는 키 ===")
missing_in_en = used_keys - en_keys
missing_in_ko = used_keys - ko_keys

if missing_in_en:
    print(f"\nen.json에 없는 키 ({len(missing_in_en)}개):")
    for key in sorted(missing_in_en):
        print(f"  - {key}")
else:
    print("\nen.json: 모든 키가 존재합니다!")

if missing_in_ko:
    print(f"\nko.json에 없는 키 ({len(missing_in_ko)}개):")
    for key in sorted(missing_in_ko):
        print(f"  - {key}")
else:
    print("\nko.json: 모든 키가 존재합니다!")

print("\n=== JSON에는 있지만 코드에서 사용되지 않는 키 ===")
unused_in_en = en_keys - used_keys
unused_in_ko = ko_keys - used_keys

if unused_in_en:
    print(f"\nen.json에서 사용되지 않는 키 ({len(unused_in_en)}개):")
    for key in sorted(unused_in_en):
        print(f"  - {key}")

if unused_in_ko:
    print(f"\nko.json에서 사용되지 않는 키 ({len(unused_in_ko)}개):")
    for key in sorted(unused_in_ko):
        print(f"  - {key}")

print(f"\n=== 통계 ===")
print(f"코드에서 사용되는 키: {len(used_keys)}개")
print(f"en.json의 키: {len(en_keys)}개")
print(f"ko.json의 키: {len(ko_keys)}개")
