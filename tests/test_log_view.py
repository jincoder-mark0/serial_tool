"""
로그 뷰(QSmartListView) 동작 및 중복 정의 회귀 테스트

## WHY
* `append_bytes`는 수신/송신 데이터가 화면에 표시되는 유일한 경로인데
  테스트가 한 건도 없어, 클래스 내 메서드 중복 정의로 이 경로가 통째로
  깨진 상태(AttributeError)가 134개 테스트를 모두 통과한 채 방치됐다 (S-038).
* 같은 유형(같은 클래스에 동일 메서드가 두 번 정의되어 뒤엣것이 앞엣것을
  조용히 덮어씀)은 눈으로 리뷰하기 어려우므로 기계적으로 막는다.

## WHAT
* QSmartListView의 실제 데이터 표시 경로 검증 (기본 / 색 규칙 / HEX / 타임스탬프)
* 프로젝트 전체 소스의 클래스 내 중복 메서드 정의 검출 (AST 기반)

## HOW
* offscreen Qt 위젯을 직접 만들어 append_bytes 호출 후 모델 행 수를 확인
* ast.parse로 ClassDef별 FunctionDef 이름 중복을 스캔 (@overload/@property setter 제외)
"""
import ast
from pathlib import Path
from typing import List, Tuple

import pytest

from common.dtos import ColorRule
from view.custom_qt.smart_list_view import QSmartListView

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("common", "core", "model", "presenter", "view", "tools")


class TestLogViewAppend:
    """QSmartListView가 실제로 데이터를 표시하는지 검증합니다."""

    def test_append_bytes_displays_line(self, qapp):
        """기본 상태에서 수신 바이트가 모델에 추가되어야 합니다."""
        view = QSmartListView()
        view.append_bytes(b"hello world\n")

        assert view.model().rowCount() > 0, "append_bytes 후 표시된 행이 없습니다"

    def test_append_bytes_with_color_rules(self, qapp):
        """색상 규칙이 주입된 상태(실사용 경로)에서도 표시되어야 합니다."""
        view = QSmartListView()
        view.set_color_rules([ColorRule(name="OK", pattern="OK", color="#00FF00")])
        view.append_bytes(b"OK\n")

        assert view.model().rowCount() > 0

    def test_append_bytes_hex_mode(self, qapp):
        """HEX 모드에서도 예외 없이 표시되어야 합니다."""
        view = QSmartListView()
        view.set_hex_mode_enabled(True)
        view.append_bytes(b"\x01\x02\x03")

        assert view.model().rowCount() > 0

    def test_append_bytes_with_timestamp(self, qapp):
        """타임스탬프 모드에서도 예외 없이 표시되어야 합니다."""
        view = QSmartListView()
        view.set_timestamp_enabled(True)
        view.append_bytes(b"data\n")

        assert view.model().rowCount() > 0


def _duplicate_methods(path: Path) -> List[Tuple[str, str, int]]:
    """
    한 파일에서 '같은 클래스에 같은 이름으로 두 번 정의된 메서드'를 찾습니다.

    Args:
        path: 검사할 파이썬 소스 경로.

    Returns:
        (클래스명, 메서드명, 재정의된 줄 번호) 목록.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: List[Tuple[str, str, int]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        seen: dict = {}
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # property setter/deleter, overload 등은 같은 이름 재정의가 정상이다.
            decorators = {
                d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", "")
                for d in item.decorator_list
            }
            if decorators & {"setter", "deleter", "overload"}:
                continue

            if item.name in seen:
                found.append((node.name, item.name, item.lineno))
            seen[item.name] = item.lineno

    return found


def test_no_duplicate_method_definitions():
    """
    같은 클래스에 동일 메서드가 두 번 정의되면 뒤엣것이 앞엣것을 조용히
    덮어써 앞 구현이 죽은 코드가 된다 (S-038에서 실제 기능 파손으로 이어짐).
    """
    violations: List[str] = []

    for scan_dir in SCAN_DIRS:
        for path in (PROJECT_ROOT / scan_dir).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for class_name, method_name, lineno in _duplicate_methods(path):
                rel = path.relative_to(PROJECT_ROOT)
                violations.append(f"{rel}:{lineno} — {class_name}.{method_name} 중복 정의")

    assert not violations, "클래스 내 중복 메서드 정의:\n" + "\n".join(violations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
