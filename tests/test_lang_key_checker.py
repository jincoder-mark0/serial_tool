"""
`tools/check_language_keys.py` 확장 기능 회귀 테스트 모듈 (S-048)

en/ko 키 대칭·[TODO] 검사에 더해 새로 추가된 두 검사(코드 참조 키 실재 여부,
플레이스홀더 개수 일치)가 가짜 JSON·가짜 소스 트리로 실제로 위반을 검출하는지,
그리고 동적 키(f-string/변수)를 오탐으로 실패시키지 않는지 확인한다.

## WHY
* S-020에서 오타 키(`manual_panel_title`)가 전 화면에 원문 노출된 사고가
  재발하지 않도록, 이 검사 로직 자체가 회귀 없이 동작하는지 고정한다.
* `tools/`는 pytest 수집 대상이 아니므로(스크립트 디렉터리) `sys.path`에
  프로젝트 루트를 추가해 직접 import한다(conftest.py가 이미 루트를
  sys.path에 넣어두므로 `from tools.check_language_keys import ...`로 충분).

## HOW
* `LanguageIntegrityChecker(directory, code_root=...)`에 `tmp_path` 아래
  가짜 `en.json`/`ko.json`과 가짜 `view/`·`presenter/` 소스를 주입해
  `run_check()`의 반환값과 `has_error` 플래그로 판정한다.
* 종료 코드(sys.exit) 자체는 `main()` 내부 로직이라 직접 호출하지 않고,
  CI가 의존하는 `run_check() -> bool` 계약만 검증한다(회귀 테스트 범위를
  판정 로직에 한정 — main()의 print/argv 처리는 대상 밖).

pytest tests/test_lang_key_checker.py -v
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.check_language_keys import LanguageIntegrityChecker  # noqa: E402


def _write_lang_files(lang_dir: Path, en_data: dict, ko_data: dict) -> None:
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / "en.json").write_text(json.dumps(en_data, ensure_ascii=False), encoding="utf-8")
    (lang_dir / "ko.json").write_text(json.dumps(ko_data, ensure_ascii=False), encoding="utf-8")


def _write_source(code_root: Path, rel_path: str, content: str) -> None:
    path = code_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def lang_dir(tmp_path):
    return tmp_path / "languages"


@pytest.fixture
def code_root(tmp_path):
    root = tmp_path / "code"
    (root / "view").mkdir(parents=True, exist_ok=True)
    (root / "presenter").mkdir(parents=True, exist_ok=True)
    return root


class TestBaselineValid:
    """오탐 없는 정상 케이스 - 확장 검사 도입 후에도 통과해야 한다."""

    def test_valid_files_and_usage_pass(self, lang_dir, code_root):
        _write_lang_files(
            lang_dir,
            {"btn_ok": "OK", "msg_hello": "Hello {0}"},
            {"btn_ok": "확인", "msg_hello": "안녕 {0}"},
        )
        _write_source(
            code_root, "view/widget.py",
            'language_manager.get_text("btn_ok")\n'
            'language_manager.get_text("msg_hello").format(name)\n',
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is True
        assert checker.has_error is False


class TestKeyUsageCheck:
    """코드 참조 키 실재 여부 검사 (S-048 신규)."""

    def test_typo_literal_key_fails(self, lang_dir, code_root):
        _write_lang_files(lang_dir, {"btn_ok": "OK"}, {"btn_ok": "확인"})
        _write_source(
            code_root, "view/widget.py",
            'language_manager.get_text("btn_0k")\n',  # 오타: 0(zero) vs o
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is False
        assert checker.has_error is True

    def test_typo_key_in_presenter_is_also_scanned(self, lang_dir, code_root):
        _write_lang_files(lang_dir, {"btn_ok": "OK"}, {"btn_ok": "확인"})
        _write_source(
            code_root, "presenter/foo_presenter.py",
            'self.view.set_text(language_manager.get_text("does_not_exist"))\n',
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is False
        assert checker.has_error is True

    def test_dynamic_fstring_key_is_warning_not_failure(self, lang_dir, code_root):
        """
        동적 키(f-string)는 정적으로 값을 알 수 없으므로 실패시키면 안 된다
        (main_menu_theme_{name} 패턴 - 실제 사용 중).
        """
        _write_lang_files(lang_dir, {"btn_ok": "OK"}, {"btn_ok": "확인"})
        _write_source(
            code_root, "view/widget.py",
            'key = f"main_menu_theme_{theme_name.lower()}"\n'
            'language_manager.get_text(key)\n'
            'language_manager.get_text(f"main_menu_theme_{theme_name.lower()}")\n',
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is True
        assert checker.has_error is False

    def test_dynamic_variable_key_is_warning_not_failure(self, lang_dir, code_root):
        _write_lang_files(lang_dir, {"btn_ok": "OK"}, {"btn_ok": "확인"})
        _write_source(
            code_root, "presenter/foo_presenter.py",
            "status_key = compute_key()\n"
            "language_manager.get_text(status_key)\n",
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is True
        assert checker.has_error is False

    def test_unrelated_get_text_method_on_other_object_ignored(self, lang_dir, code_root):
        """`get_text`라는 이름이라도 언어 키 조회가 아닐 수 있음 - 첫 인자만 보므로
        오탐 가능성이 있지만, 리터럴이 실재 안 하면 여전히 실패해야 정책이 일관된다.
        이 테스트는 최소한 예외 없이 정상적으로 스캔이 끝남을 확인한다."""
        _write_lang_files(lang_dir, {"btn_ok": "OK"}, {"btn_ok": "확인"})
        _write_source(
            code_root, "view/widget.py",
            'some_other_object.get_text("btn_ok")\n',
        )
        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is True


class TestPlaceholderCountCheck:
    """en/ko 플레이스홀더 개수 불일치 검사 (S-048 신규)."""

    def test_mismatched_placeholder_count_fails(self, lang_dir, code_root):
        _write_lang_files(
            lang_dir,
            {"msg": "File transfer {0}: {1}"},
            {"msg": "파일 전송 {0}"},  # {1} 누락
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is False
        assert checker.has_error is True

    def test_matched_placeholder_count_passes(self, lang_dir, code_root):
        _write_lang_files(
            lang_dir,
            {"msg": "File transfer {0}: {1}"},
            {"msg": "{1}: 파일 전송 {0}"},  # 순서는 달라도 개수만 같으면 통과
        )

        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is True
        assert checker.has_error is False


class TestExistingChecksStillEnforced:
    """기존 대칭·[TODO] 검사가 확장 이후에도 유지되는지 확인 (회귀 방지)."""

    def test_missing_key_in_ko_still_fails(self, lang_dir, code_root):
        _write_lang_files(lang_dir, {"only_en": "hello"}, {})
        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is False
        assert checker.has_error is True

    def test_todo_marker_still_fails(self, lang_dir, code_root):
        _write_lang_files(
            lang_dir,
            {"btn_ok": "OK"},
            {"btn_ok": "[TODO] 확인"},
        )
        checker = LanguageIntegrityChecker(str(lang_dir), code_root=code_root)
        assert checker.run_check() is False
        assert checker.has_error is True
