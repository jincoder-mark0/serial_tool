"""PyInstaller 배포 spec 계약 테스트.

## WHY
`serial_tool.spec`은 `datas=[('resources', 'resources')]`로 리소스 디렉터리를
**통째로** 담는다. 그래서 git이 추적하지 않는 파일도 artifact에 들어간다.

실제로 그렇게 샜다. `resources/configs/settings.local.json`은 S-043이
"개발자 로컬 세션이 커밋에 섞이는 오염"을 막으려고 분리하고 `.gitignore`에 넣은
파일인데, 그 보호가 git 단계에서만 작동해 **빌드로는 그대로 배포본에 실렸다**
(2026-09-02 P4 artifact smoke에서 발견 — 빌드한 개발자의 창 위치·포트 탭·입력값이
들어 있었다).

번들 실행 시 사용자 설정은 APPDATA를 쓰므로(`ResourcePath.user_settings_file`)
이 파일은 읽히지도 않는다. 순수 유출이고, 빌드하는 사람마다 artifact가 달라져
재현성도 깨진다.

## WHAT
* spec이 개발자 로컬 설정 파일을 번들에서 제외하는가
* 제외 목록의 파일명이 `ResourcePath`가 실제로 쓰는 dev-mode 파일명과 같은가
  — 한쪽만 이름이 바뀌면 유출이 조용히 되살아난다
* 배포 기본값(`settings.json`)은 그대로 담기는가

## HOW
spec은 PyInstaller가 exec하는 Python source다. 여기서는 실행하지 않고
AST로 읽는다 — 테스트가 PyInstaller 설치에 의존하지 않아야 하기 때문이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "serial_tool.spec"


def _spec_source() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def _excluded_basenames() -> set[str]:
    """spec의 EXCLUDED_DATA_BASENAMES 리터럴을 AST로 읽는다."""
    tree = ast.parse(_spec_source(), filename=str(SPEC_PATH))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "EXCLUDED_DATA_BASENAMES":
                return set(ast.literal_eval(node.value))

    raise AssertionError(
        "serial_tool.spec에 EXCLUDED_DATA_BASENAMES가 없다 — "
        "리소스 디렉터리를 통째로 담으므로 제외 목록 없이는 로컬 파일이 새어나간다."
    )


def test_spec_is_valid_python_source():
    """PyInstaller가 exec하는 파일이므로 문법이 깨지면 빌드 자체가 실패한다."""
    ast.parse(_spec_source(), filename=str(SPEC_PATH))


def test_spec_excludes_developer_local_settings():
    assert "settings.local.json" in _excluded_basenames(), (
        "개발자 로컬 설정 파일이 번들 제외 목록에 없다. "
        "빌드한 사람의 창 위치·포트 탭·입력값이 배포본에 실린다."
    )


def test_exclusion_list_is_actually_applied_to_datas():
    """목록만 있고 필터가 없으면 아무것도 막지 못한다."""
    source = _spec_source()

    assert "a.datas" in source and "EXCLUDED_DATA_BASENAMES" in source, (
        "EXCLUDED_DATA_BASENAMES가 a.datas 필터링에 쓰이지 않는다 — "
        "선언만 하고 적용하지 않으면 제외되지 않는다."
    )
    filter_line = next(
        (line for line in source.splitlines() if "EXCLUDED_DATA_BASENAMES" in line and "not in" in line),
        None,
    )
    assert filter_line is not None, (
        "a.datas에서 EXCLUDED_DATA_BASENAMES를 걸러내는 구문을 찾지 못했다."
    )


def test_excluded_name_matches_resource_path_dev_settings_file():
    """
    spec의 제외 파일명과 ResourcePath의 dev-mode 파일명이 같아야 한다.

    한쪽만 바뀌면 spec은 존재하지 않는 이름을 거르고, 실제 로컬 파일은 그대로
    번들에 실린다 — 테스트는 통과하는데 유출은 되살아나는 최악의 형태다.
    """
    from core.resource_path import ResourcePath

    dev_settings_name = ResourcePath(PROJECT_ROOT).user_settings_file.name

    assert dev_settings_name in _excluded_basenames(), (
        f"ResourcePath는 dev-mode 사용자 설정으로 '{dev_settings_name}'을 쓰는데 "
        f"spec 제외 목록은 {sorted(_excluded_basenames())}이다. 이름이 어긋났다."
    )


def test_distribution_default_settings_stays_bundled():
    """배포 기본값까지 제외하면 첫 실행 시 기본 설정을 읽지 못한다."""
    assert "settings.json" not in _excluded_basenames(), (
        "배포 기본 설정(settings.json)을 제외하면 안 된다 — "
        "제외 대상은 개발자 로컬 파일(settings.local.json)뿐이다."
    )
