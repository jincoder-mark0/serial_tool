"""
로그 위젯(DataLogWidget/SystemLogWidget) 특성화 테스트

## WHY
* S-049(로그 위젯 중복 공통화) 착수 전, 두 위젯을 직접 exercise하는 테스트가
  0건이었다(`tests/test_data_logger.py`는 `core/data_logger.py`(파일 I/O)를,
  `tests/test_log_view.py`는 `QSmartListView` 자체만 검증 — 상위 위젯의 검색/필터/
  REC 토글/상태 저장 동작은 아무 테스트도 덮지 않았다).
* 공통화 리팩토링이 동작을 바꾸지 않았음을 보장하려면 리팩토링 *전* 동작을
  먼저 고정해야 한다 — 이 파일이 그 특성화(characterization) 테스트다.
* 절대 조건: `get_state()`/`apply_state()`의 저장 키 문자열은 리팩토링 후에도
  동일해야 한다(사용자 설정 호환) — 이를 회귀 감지 가능한 형태로 고정한다.
* S-052(제어 흐름 통일)에서 SystemLog의 시그널 계약이 변경되었다:
  `sys_logging_started(str)`/`sys_logging_stopped()` → 인자 없는 요청 시그널
  `sys_logging_start_requested()`/`sys_logging_stop_requested()`로 DataLog와
  대칭이 되도록 정리(계약 변경은 이번 태스크에서 명시적으로 허용됨).

## WHAT
* 검색 다음/이전 이동 (wrap-around 포함)
* 필터 체크박스 토글 시 QSmartListView 표시 행 수 변화
* REC 스타일 전환 — 두 위젯 모두 "Presenter 권위"로 통일됨(S-052):
  버튼 토글은 요청 시그널만 내보내고, 실제 파일 다이얼로그 표시와 스타일 전환은
  외부에서 `show_save_log_dialog()`/`set_logging_active()`를 호출해야 일어난다.
  SystemLog가 토글 시 QFileDialog를 직접 호출하지 않음을 monkeypatch 감시로 고정.
* `get_state()`/`apply_state()` 왕복 및 저장 키 문자열 고정.

## HOW
* offscreen QApplication(`qapp`) 위에서 위젯을 직접 생성.
* `QSmartListView.append()`로 로그 라인을 직접 주입해 검색/필터 대상을 만든다.
* `QFileDialog.getSaveFileName`은 monkeypatch로 대체해 모달 다이얼로그를 우회한다.
"""
import pytest
from PyQt5.QtWidgets import QFileDialog

from view.widgets.data_log import DataLogWidget
from view.widgets.system_log import SystemLogWidget
from common.enums import NewlineMode


# -----------------------------------------------------------------------------
# 검색 다음/이전 이동
# -----------------------------------------------------------------------------

class TestDataLogSearchNavigation:
    """DataLogWidget의 검색 다음/이전 버튼 동작을 고정합니다."""

    def _seed(self, widget: DataLogWidget) -> None:
        for line in ("no match 1", "TARGET line 2", "no match 3", "TARGET line 4"):
            widget.data_log_list.append(line)

    def test_search_next_moves_through_matches_and_wraps(self, qapp):
        widget = DataLogWidget()
        self._seed(widget)
        widget.data_log_search_input.setText("TARGET")

        widget.on_data_log_search_next_clicked()
        assert widget.data_log_list.currentIndex().row() == 1

        widget.on_data_log_search_next_clicked()
        assert widget.data_log_list.currentIndex().row() == 3

        # wrap-around: 다음 매치가 없으므로 처음(1)으로 되돌아간다.
        widget.on_data_log_search_next_clicked()
        assert widget.data_log_list.currentIndex().row() == 1

    def test_search_prev_from_start_wraps_to_last_match(self, qapp):
        widget = DataLogWidget()
        self._seed(widget)
        widget.data_log_search_input.setText("TARGET")

        widget.on_data_log_search_prev_clicked()
        assert widget.data_log_list.currentIndex().row() == 3

    def test_search_empty_text_does_nothing(self, qapp):
        widget = DataLogWidget()
        self._seed(widget)
        widget.data_log_search_input.setText("")

        widget.on_data_log_search_next_clicked()
        assert widget.data_log_list.currentIndex().row() == -1


class TestSystemLogSearchNavigation:
    """SystemLogWidget의 검색 다음/이전 버튼 동작을 고정합니다 (DataLog와 동일 계약)."""

    def _seed(self, widget: SystemLogWidget) -> None:
        for line in ("no match 1", "TARGET line 2", "no match 3", "TARGET line 4"):
            widget.sys_log_list.append(line)

    def test_search_next_moves_through_matches_and_wraps(self, qapp):
        widget = SystemLogWidget()
        self._seed(widget)
        widget.sys_log_search_input.setText("TARGET")

        widget.on_sys_log_search_next_clicked()
        assert widget.sys_log_list.currentIndex().row() == 1

        widget.on_sys_log_search_next_clicked()
        assert widget.sys_log_list.currentIndex().row() == 3

        widget.on_sys_log_search_next_clicked()
        assert widget.sys_log_list.currentIndex().row() == 1

    def test_search_prev_from_start_wraps_to_last_match(self, qapp):
        widget = SystemLogWidget()
        self._seed(widget)
        widget.sys_log_search_input.setText("TARGET")

        widget.on_sys_log_search_prev_clicked()
        assert widget.sys_log_list.currentIndex().row() == 3


# -----------------------------------------------------------------------------
# 필터 체크박스 토글
# -----------------------------------------------------------------------------

class TestDataLogFilterToggle:
    def test_filter_checkbox_hides_non_matching_rows(self, qapp):
        widget = DataLogWidget()
        widget.data_log_list.append("keep me")
        widget.data_log_list.append("drop me")

        widget.data_log_search_input.setText("keep")
        assert widget.data_log_list.model().rowCount() == 2  # 필터 비활성: 전부 보임

        widget.data_log_filter_chk.setChecked(True)
        assert widget.filter_enabled is True
        assert widget.data_log_list.model().rowCount() == 1  # 필터 활성: 매치만 보임

        widget.data_log_filter_chk.setChecked(False)
        assert widget.filter_enabled is False
        assert widget.data_log_list.model().rowCount() == 2


class TestSystemLogFilterToggle:
    def test_filter_checkbox_hides_non_matching_rows(self, qapp):
        widget = SystemLogWidget()
        widget.sys_log_list.append("keep me")
        widget.sys_log_list.append("drop me")

        widget.sys_log_search_input.setText("keep")
        assert widget.sys_log_list.model().rowCount() == 2

        widget.sys_log_filter_chk.setChecked(True)
        assert widget.filter_enabled is True
        assert widget.sys_log_list.model().rowCount() == 1

        widget.sys_log_filter_chk.setChecked(False)
        assert widget.filter_enabled is False
        assert widget.sys_log_list.model().rowCount() == 2


# -----------------------------------------------------------------------------
# REC 스타일 전환 — 상반된 제어 흐름 (통일하지 않고 각각 고정)
# -----------------------------------------------------------------------------

class TestDataLogRecordingIsPresenterAuthority:
    """
    DataLog: 버튼 토글은 의도(시그널)만 전달하고, 실제 스타일 전환은
    Presenter가 `set_logging_active()`를 호출해야 일어난다.
    """

    def test_toggle_emits_signal_without_changing_style(self, qapp, qtbot):
        widget = DataLogWidget()
        original_text = widget.data_log_toggle_logging_btn.text()

        with qtbot.waitSignal(widget.logging_start_requested, timeout=1000, raising=True):
            widget.data_log_toggle_logging_btn.setChecked(True)

        # 시그널만 나갔을 뿐 버튼 스타일/텍스트는 아직 그대로다 (Presenter 응답 전).
        assert widget.data_log_toggle_logging_btn.property("state") != "recording"
        assert widget.data_log_toggle_logging_btn.text() == original_text

    def test_stop_toggle_emits_signal(self, qapp, qtbot):
        widget = DataLogWidget()
        widget.data_log_toggle_logging_btn.setChecked(True)

        with qtbot.waitSignal(widget.logging_stop_requested, timeout=1000, raising=True):
            widget.data_log_toggle_logging_btn.setChecked(False)

    def test_set_logging_active_true_then_false_changes_style(self, qapp):
        widget = DataLogWidget()
        inactive_text = widget.data_log_toggle_logging_btn.text()

        widget.set_logging_active(True)
        assert widget.data_log_toggle_logging_btn.property("state") == "recording"
        assert widget.data_log_toggle_logging_btn.text() == "\u25cf REC"
        assert widget.data_log_toggle_logging_btn.isChecked() is True

        widget.set_logging_active(False)
        assert widget.data_log_toggle_logging_btn.property("state") is None
        assert widget.data_log_toggle_logging_btn.text() == inactive_text
        assert widget.data_log_toggle_logging_btn.isChecked() is False


class TestSystemLogRecordingIsPresenterAuthority:
    """
    SystemLog: DataLog와 동일한 "Presenter 권위" 제어 흐름으로 통일됨(S-052).
    버튼 토글은 요청 시그널만 내보내고, 실제 파일 다이얼로그 표시와 스타일
    전환은 외부(Presenter)가 `show_save_log_dialog()`/`set_logging_active()`를
    호출해야 일어난다.
    """

    def test_toggle_emits_signal_without_changing_style(self, qapp, qtbot):
        widget = SystemLogWidget()
        original_text = widget.sys_log_toggle_logging_btn.text()

        with qtbot.waitSignal(widget.sys_logging_start_requested, timeout=1000, raising=True):
            widget.sys_log_toggle_logging_btn.setChecked(True)

        # 시그널만 나갔을 뿐 버튼 스타일/텍스트는 아직 그대로다 (Presenter 응답 전).
        assert widget.sys_log_toggle_logging_btn.property("state") != "recording"
        assert widget.sys_log_toggle_logging_btn.text() == original_text

    def test_stop_toggle_emits_signal(self, qapp, qtbot):
        widget = SystemLogWidget()
        widget.sys_log_toggle_logging_btn.setChecked(True)

        with qtbot.waitSignal(widget.sys_logging_stop_requested, timeout=1000, raising=True):
            widget.sys_log_toggle_logging_btn.setChecked(False)

    def test_set_logging_active_true_then_false_changes_style(self, qapp):
        widget = SystemLogWidget()
        inactive_text = widget.sys_log_toggle_logging_btn.text()

        widget.set_logging_active(True)
        assert widget.sys_log_toggle_logging_btn.property("state") == "recording"
        assert widget.sys_log_toggle_logging_btn.text() == "\u25cf REC"
        assert widget.sys_log_toggle_logging_btn.isChecked() is True

        widget.set_logging_active(False)
        assert widget.sys_log_toggle_logging_btn.property("state") is None
        assert widget.sys_log_toggle_logging_btn.text() == inactive_text
        assert widget.sys_log_toggle_logging_btn.isChecked() is False

    def test_show_save_log_dialog_delegates_to_qfiledialog(self, qapp, monkeypatch):
        """Presenter가 명시적으로 호출하는 `show_save_log_dialog()`는 여전히
        QFileDialog를 사용한다 — 자기 권위였던 기존 동작을 메서드로 옮겼을 뿐,
        기능 자체(파일 선택 UI)는 사라지지 않았음을 확인한다."""
        widget = SystemLogWidget()

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: ("C:/tmp/fake.bin", "")),
        )

        assert widget.show_save_log_dialog() == "C:/tmp/fake.bin"

    def test_toggle_does_not_call_qfiledialog_directly(self, qapp, monkeypatch):
        """
        신규(S-052): 위젯이 토글 시 QFileDialog를 직접 호출하지 않음을 고정한다.
        DataLog와 동일하게, 다이얼로그는 오직 Presenter가 `show_save_log_dialog()`를
        명시적으로 호출했을 때만 열려야 한다.
        """
        widget = SystemLogWidget()

        call_count = {"n": 0}

        def _spy_get_save_file_name(*a, **k):
            call_count["n"] += 1
            return ("C:/tmp/fake.bin", "")

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(_spy_get_save_file_name),
        )

        widget.sys_log_toggle_logging_btn.setChecked(True)
        widget.sys_log_toggle_logging_btn.setChecked(False)

        assert call_count["n"] == 0


# -----------------------------------------------------------------------------
# get_state()/apply_state() — 저장 키 문자열 고정 + 왕복
# -----------------------------------------------------------------------------

class TestDataLogStateContract:
    EXPECTED_KEYS = {
        "tx_broadcast_allowed_enabled", "hex_mode", "timestamp", "is_paused",
        "search_text", "filter_enabled", "newline_mode",
    }

    def test_get_state_keys_are_fixed(self, qapp):
        widget = DataLogWidget()
        assert set(widget.get_state().keys()) == self.EXPECTED_KEYS

    def test_initial_internal_state_matches_checkbox(self, qapp):
        # S-051: 생성 직후 내부 변수(tx_broadcast_allowed_enabled)와 체크박스
        # 초기 상태가 어긋나 있으면, apply_state가 체크박스의 stateChanged 신호에
        # 의존하는 구조상 "이미 같은 값이라 신호가 안 나는" 왕복 실패로 이어진다.
        widget = DataLogWidget()
        assert widget.tx_broadcast_allowed_enabled == widget.data_log_tx_broadcast_allowed_chk.isChecked()

    def test_apply_state_immediately_after_init_restores_broadcast_off(self, qapp):
        # S-051 재현: 생성 직후(신호가 한 번도 발생하지 않은 상태)
        # apply_state({"tx_broadcast_allowed_enabled": False, ...})를 호출해도
        # 체크박스가 이미 초기값과 같으면 stateChanged가 발생하지 않아 내부 변수가
        # 갱신되지 않던 결함을 고정한다(저장된 False가 True로 되살아나면 안 된다).
        widget = DataLogWidget()
        state_off = {
            "tx_broadcast_allowed_enabled": False,
            "hex_mode": False,
            "timestamp": False,
            "is_paused": False,
            "search_text": "",
            "filter_enabled": False,
            "newline_mode": NewlineMode.RAW.value,
        }
        widget.apply_state(state_off)
        assert widget.tx_broadcast_allowed_enabled is False
        assert widget.get_state()["tx_broadcast_allowed_enabled"] is False

    def test_apply_state_then_get_state_round_trips(self, qapp):
        widget = DataLogWidget()
        state_on = {
            "tx_broadcast_allowed_enabled": True,
            "hex_mode": True,
            "timestamp": True,
            "is_paused": True,
            "search_text": "abc",
            "filter_enabled": True,
            "newline_mode": NewlineMode.LF.value,
        }
        widget.apply_state(state_on)
        assert widget.get_state() == state_on

        state_off = {
            "tx_broadcast_allowed_enabled": False,
            "hex_mode": False,
            "timestamp": False,
            "is_paused": False,
            "search_text": "",
            "filter_enabled": False,
            "newline_mode": NewlineMode.RAW.value,
        }
        widget.apply_state(state_off)
        assert widget.get_state() == state_off

    def test_apply_state_handles_empty_dict(self, qapp):
        widget = DataLogWidget()
        # 예외 없이 무시되어야 한다 (기존 상태 유지).
        widget.apply_state({})
        widget.apply_state(None)


class TestSystemLogStateContract:
    EXPECTED_KEYS = {"filter_enabled", "search_text"}

    def test_get_state_keys_are_fixed(self, qapp):
        widget = SystemLogWidget()
        assert set(widget.get_state().keys()) == self.EXPECTED_KEYS

    def test_apply_state_then_get_state_round_trips(self, qapp):
        widget = SystemLogWidget()
        state = {"filter_enabled": True, "search_text": "xyz"}

        widget.apply_state(state)

        assert widget.get_state() == state

    def test_apply_state_handles_empty_dict(self, qapp):
        widget = SystemLogWidget()
        widget.apply_state({})
        widget.apply_state(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
