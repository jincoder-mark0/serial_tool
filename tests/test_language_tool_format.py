"""언어 키 관리 도구가 리소스 파일 형식을 보존하는지 검증한다.

## WHY
문서화된 절차(`.claude/skills/lang-keys`)는 키를 추가한 뒤
`tools/manage_language_keys.py`를 돌리라고 한다. 그런데 이 도구가 `indent=4`로
저장하는 반면 `resources/languages/*.json`은 2칸이었다. 그래서 **키를 하나만
추가해도 두 파일 607줄이 통째로 재포맷**됐다.

결과는 두 가지다. PR diff가 노이즈로 뒤덮여 실제 변경이 묻히고, 재포맷된 줄의
blame이 전부 끊긴다. 절차를 따를수록 기록이 나빠지는 셈이었다.

형식은 도구가 아니라 저장된 파일이 정본이다 — 도구를 파일에 맞췄다.

## WHAT
도구의 저장 형식이 실제 리소스 파일과 **바이트 단위로** 일치하는가.
즉, 내용 변경이 없을 때 도구 실행이 멱등인가.

## HOW
리포지토리 파일을 건드리지 않는다. 실제 파일을 읽어 도구의 저장 경로로 임시
디렉터리에 다시 쓴 뒤, 원본과 비교한다.

줄바꿈은 정규화해서 비교한다 — CI가 Windows(CRLF)와 Ubuntu(LF) 양쪽에서 돌고,
줄바꿈은 git의 몫이지 이 도구가 정할 문제가 아니다. 여기서 고정하려는 것은
들여쓰기·정렬·끝 개행·비ASCII 보존이다.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANGUAGES_DIR = PROJECT_ROOT / "resources" / "languages"
TOOL_PATH = PROJECT_ROOT / "tools" / "manage_language_keys.py"


def _load_tool():
    """도구를 모듈로 불러온다 (main()은 실행하지 않는다)."""
    spec = importlib.util.spec_from_file_location("manage_language_keys", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _normalized(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.mark.parametrize("filename", ["en.json", "ko.json"])
def test_tool_save_format_matches_the_stored_resource_file(filename, tmp_path):
    """
    도구가 저장하는 형식이 실제 파일과 같아야 한다.

    다르면 키를 하나 추가할 때마다 파일 전체가 재포맷되어, 실제 변경이 diff에
    묻히고 blame이 끊긴다.
    """
    tool = _load_tool()
    source = LANGUAGES_DIR / filename

    manager = tool.LanguageKeyManager(str(LANGUAGES_DIR))
    data = manager._load_json(str(source))
    assert data, f"{filename}을 읽지 못했다"

    rewritten = tmp_path / filename
    manager._save_json(str(rewritten), data)

    assert _normalized(rewritten) == _normalized(source), (
        f"도구의 저장 형식이 {filename}과 다르다 — 도구를 한 번 돌리는 것만으로 "
        f"파일 전체가 재포맷된다. 들여쓰기/끝 개행/ensure_ascii를 리소스 파일에 맞춰라."
    )


@pytest.mark.parametrize("filename", ["en.json", "ko.json"])
def test_stored_files_keep_their_documented_shape(filename):
    """
    리소스 파일 자체의 형식을 고정한다.

    도구만 맞춰두고 파일이 흘러가면 다시 어긋난다. 양쪽을 같이 묶어야 한다.
    """
    raw = (LANGUAGES_DIR / filename).read_text(encoding="utf-8")
    lines = raw.replace("\r\n", "\n").split("\n")

    assert raw.endswith("\n"), f"{filename}이 개행으로 끝나지 않는다"

    indented = [line for line in lines if line.startswith(" ")]
    assert indented, f"{filename}에 들여쓴 줄이 없다 — 구조가 바뀌었는지 확인할 것"
    for line in indented:
        stripped = len(line) - len(line.lstrip(" "))
        assert stripped == 2, (
            f"{filename}의 들여쓰기가 2칸이 아니다 ({stripped}칸): {line[:40]!r}"
        )
