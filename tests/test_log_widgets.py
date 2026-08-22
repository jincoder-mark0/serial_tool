"""
로그 위젯(DataLogWidget/SystemLogWidget) 특성화 테스트

## WHY
* S-049(로그 위젯 중복 공통화) 착수 전, 두 위젯을 직접 exercise하는 테스트가
  0건이었다(`tests/test_data_logger.py`는 `core/data_logger.py`(파일 I/O)를,
  `tests/test_log_view.py`는 `QSmartListView` 자체만 검증 — 상위 위젯의 검색/필터/
  REC 토글/상태 저장 동작은 아무 테스트도 덮지 않았다).
* 공통화 리팩토링이 동작을 바꾸지 않았음을 보장하려면 리팩토링 *전* 동작을
  먼저 고정해야 한다 — 이 파일이 그 특성화(characterization) 테스트다.
* 절대 조건: 시그널 이름/시그니처(`logging_start_requested()`,
  `logging_stop_requested()`, `sys_logging_started(str)`, `sys_logging_stopped()`)와
  `get_state()`/`apply_state()`의 저장 키 문자열은 리팩토링 후에도 동일해야 한다
  (Presenter 배선, 사용자 설정 호환) — 이를 회귀 감지 가능한 형태로 고정한다.

## WHAT
* 검색 다음/이전 이동 (wrap-around 포함)
* 필터 체크박스 토글 시 QSmartListView 표시 행 수 변화
* REC 스타일 전환의 두 가지 상반된 제어 흐름:
  - DataLog = "Presenter 권위": 버튼 토글은 시그널만 내보내고, 실제 스타일 전환은
    외부에서 `set_logging_active()`를 호출해야 일어난다.
  - SystemLog = "자기 권위": 버튼 토글 즉시 위젯 스스로 파일 다이얼로그를 띄우고
    스타일을 전환한다 (QFileDialog는 monkeypatch로 대체).
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


class TestSystemLogRecordingIsSelfAuthority:
    """
    SystemLog: 버튼 토글 즉시 위젯 스스로 파일 다이얼로그를 띄우고
    (승인 시) 스타일을 자체 전환한다 — 외부 호출이 필요 없다.
    """

    def test_toggle_on_shows_dialog_and_self_applies_style(self, qapp, monkeypatch):
        widget = SystemLogWidget()
        inactive_text = widget.sys_log_toggle_logging_btn.text()

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: ("C:/tmp/fake.bin", "")),
        )

        received = []
        widget.sys_logging_started.connect(received.append)

        widget.sys_log_toggle_logging_btn.setChecked(True)

        assert received == ["C:/tmp/fake.bin"]
        # Presenter 개입 없이 위젯 스스로 스타일을 바꾼다 (자기 권위).
        assert widget.sys_log_toggle_logging_btn.property("state") == "recording"
        assert widget.sys_log_toggle_logging_btn.text() == "\u25cf REC"

        widget.sys_log_toggle_logging_btn.setChecked(False)
        assert widget.sys_log_toggle_logging_btn.property("state") is None
        assert widget.sys_log_toggle_logging_btn.text() == inactive_text

    def test_toggle_on_cancelled_dialog_reverts_without_signal(self, qapp, monkeypatch):
        widget = SystemLogWidget()

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )

        received = []
        widget.sys_logging_started.connect(received.append)

        widget.sys_log_toggle_logging_btn.setChecked(True)

        assert received == []
        assert widget.sys_log_toggle_logging_btn.isChecked() is False
        assert widget.sys_log_toggle_logging_btn.property("state") != "recording"


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

    def test_apply_state_then_get_state_round_trips(self, qapp):
        # 주의(특성화로 확인된 기존 동작): 생성 직후 내부 변수
        # `tx_broadcast_allowed_enabled`는 True이지만 체크박스 위젯 자체는
        # 기본 unchecked(False)로 만들어져 있다 — 초기화 시 두 값이 어긋난 채로
        # 시작한다. apply_state({"tx_broadcast_allowed_enabled": False, ...})를
        # 생성 직후 바로 호출하면 체크박스가 이미 False라 setChecked(False)가
        # 아무 신호도 내지 않고, 내부 변수는 초기값 True에 머문 채 get_state()가
        # True를 반환한다(왕복 실패). 리팩토링 대상이 아니므로 고치지 않고,
        # 실제로 상태가 바뀌는 전이만 왕복시켜 회귀를 감지한다.
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
