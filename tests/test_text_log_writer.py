"""
텍스트 로그 라이터(TextLogWriter) 및 시스템 로그 실제 파일 기록 테스트 모듈

## WHY
* S-052는 시스템 로그 REC 토글의 제어 흐름(누가 다이얼로그를 열고 상태를 바꾸는가)만
  통일했고, 실제 파일 기록은 기능 격차로 남아 있었다(S-055 조사 결과) — 토글을 켜도
  파일에는 아무것도 기록되지 않았다.
* 이 파일은 그 격차를 메운 세 가지를 고정한다:
  1. `core/text_log_writer.py`의 TextLogWriter 자체 (open/write_line/close, 실패 표면화)
  2. `SystemLogWidget.append_log()`가 화면에 추가되는 순간 실제로 시그널을 내보내는지,
     화면 필터가 걸려 있을 때 필터링된 라인은 신호를 내보내지 않는지
  3. `MainPresenter`가 토글 ON→라인 기록→토글 OFF(닫힘)→앱 종료(닫힘) 전체 배선을
     실제 파일 시스템에 대해 올바르게 수행하는지

## WHAT
* TextLogWriter: 실제 임시 디렉터리에 대한 open/write_line/close, 실패 케이스
* SystemLogWidget: append_log()의 시그널 발행 여부(필터 반영)
* MainPresenter: 시작~중지~종료까지 실제 파일 산출물 검증

## HOW
* `tmp_path`(pytest 기본 제공)로 실제 파일 I/O를 검증한다 — Mock으로 대체하지 않는다
  (이 태스크의 핵심이 "파일에 실제로 기록되는가"이므로).
* MainPresenter는 `tests/test_presenter_init.py`와 동일한 방식으로 View를 MagicMock으로
  대체하되, `settings_manager`는 conftest의 `mock_settings_manager`(실제 임시 경로를 쓰는
  진짜 SettingsManager)를 사용해 종료 시퀀스(`on_close_requested`)가 실제로 끝까지
  실행되도록 한다.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.text_log_writer import TextLogWriter
from view.widgets.system_log import SystemLogWidget
from common.dtos import SystemLogEvent, MainWindowState
from presenter.main_presenter import MainPresenter


# -----------------------------------------------------------------------------
# 1. TextLogWriter — 실제 파일 I/O
# -----------------------------------------------------------------------------

class TestTextLogWriter:
    """TextLogWriter의 open/write_line/close가 실제 파일에 대해 동작함을 고정한다."""

    def test_write_line_appends_to_real_file(self, tmp_path):
        """열고 두 줄을 쓰면 실제 파일에 개행으로 구분된 두 줄이 남는다."""
        file_path = tmp_path / "syslog.txt"
        writer = TextLogWriter()

        writer.open(str(file_path))
        writer.write_line("first line")
        writer.write_line("second line")
        writer.close()

        content = file_path.read_text(encoding="utf-8")
        assert content == "first line\nsecond line\n"

    def test_write_line_appends_across_open_sessions(self, tmp_path):
        """append 모드이므로 재오픈 시 기존 내용을 보존한 채 뒤에 이어 쓴다."""
        file_path = tmp_path / "syslog.txt"

        writer = TextLogWriter()
        writer.open(str(file_path))
        writer.write_line("session 1")
        writer.close()

        writer2 = TextLogWriter()
        writer2.open(str(file_path))
        writer2.write_line("session 2")
        writer2.close()

        content = file_path.read_text(encoding="utf-8")
        assert content == "session 1\nsession 2\n"

    def test_write_line_before_open_raises_oserror(self):
        """열지 않고 쓰면 조용히 무시하지 않고 예외로 실패를 알린다(S-039/S-045 원칙)."""
        writer = TextLogWriter()
        with pytest.raises(OSError):
            writer.write_line("should fail")

    def test_open_creates_missing_parent_directory(self, tmp_path):
        """상위 디렉터리가 없어도 자동 생성 후 정상적으로 연다."""
        file_path = tmp_path / "nested" / "dir" / "syslog.txt"
        writer = TextLogWriter()

        writer.open(str(file_path))
        writer.write_line("line")
        writer.close()

        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "line\n"

    def test_is_open_reflects_state(self, tmp_path):
        """is_open 프로퍼티가 open/close 상태를 정확히 반영한다."""
        writer = TextLogWriter()
        assert writer.is_open is False

        writer.open(str(tmp_path / "syslog.txt"))
        assert writer.is_open is True

        writer.close()
        assert writer.is_open is False

    def test_close_is_idempotent(self, tmp_path):
        """이미 닫힌 상태에서 close()를 다시 호출해도 예외가 나지 않는다."""
        writer = TextLogWriter()
        writer.open(str(tmp_path / "syslog.txt"))
        writer.close()

        writer.close()  # 두 번째 호출 — 예외 없이 통과해야 함

    def test_reopen_closes_previous_file_handle(self, tmp_path):
        """open()이 이미 열린 파일을 두고 다시 호출되면 이전 파일을 먼저 닫는다."""
        file_a = tmp_path / "a.txt"
        file_b = tmp_path / "b.txt"
        writer = TextLogWriter()

        writer.open(str(file_a))
        writer.write_line("in a")
        writer.open(str(file_b))  # a를 닫고 b를 새로 연다
        writer.write_line("in b")
        writer.close()

        assert file_a.read_text(encoding="utf-8") == "in a\n"
        assert file_b.read_text(encoding="utf-8") == "in b\n"
        assert writer.file_path == ""


# -----------------------------------------------------------------------------
# 2. SystemLogWidget — 화면에 추가되는 지점에서의 시그널 발행 (필터 반영)
# -----------------------------------------------------------------------------

class TestSystemLogWidgetLineAppendedSignal:
    """append_log()가 화면 추가 시점에 system_log_line_appended를 내보냄을 고정한다."""

    def test_append_log_emits_plain_text_without_html(self, qapp, qtbot):
        """방출되는 텍스트는 색상 HTML 마크업이 섞이지 않은 순수 텍스트여야 한다."""
        widget = SystemLogWidget()
        widget.set_color_rules([])  # 색상 규칙 없음 -> 그래도 순수 텍스트 확인

        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True) as blocker:
            widget.append_log(SystemLogEvent(message="hello world", level="INFO"))

        emitted_text = blocker.args[0]
        assert "[INFO] hello world" in emitted_text
        assert "<" not in emitted_text  # HTML 태그가 섞이지 않음

    def test_filter_disabled_emits_every_line(self, qapp, qtbot):
        """필터 체크박스가 꺼져 있으면 검색어와 무관하게 모든 라인이 방출된다."""
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("NOMATCH")
        widget.filter_enabled = False

        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True):
            widget.append_log(SystemLogEvent(message="does not contain the word", level="INFO"))

    def test_filter_enabled_blocks_non_matching_line(self, qapp, qtbot):
        """필터가 켜져 있고 검색어가 라인에 없으면 화면에서 숨겨지는 것과 동일하게
        방출도 되지 않는다 — 저장 대상은 '화면에 표시되는 라인 그대로'(S-055 결정)."""
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("TARGET")
        widget.filter_enabled = True

        received = []
        widget.system_log_line_appended.connect(received.append)

        widget.append_log(SystemLogEvent(message="no match here", level="INFO"))
        qapp.processEvents()

        assert received == []

    def test_filter_enabled_allows_matching_line(self, qapp, qtbot):
        """필터가 켜져 있어도 검색어가 라인에 포함되면(화면에 보이면) 방출된다."""
        widget = SystemLogWidget()
        widget.sys_log_search_input.setText("TARGET")
        widget.filter_enabled = True

        with qtbot.waitSignal(widget.system_log_line_appended, timeout=1000, raising=True) as blocker:
            widget.append_log(SystemLogEvent(message="this has TARGET inside", level="INFO"))

        assert "TARGET" in blocker.args[0]


# -----------------------------------------------------------------------------
# 3. MainPresenter — 시작/중지/종료 전 구간의 실제 파일 산출물
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_main_window():
    """
    MainPresenter 초기화에 필요한 최소 MainWindow Mock.

    `tests/test_presenter_init.py`의 fixture와 동일한 패턴 — View 내부 구조를
    MagicMock으로 대체해 GUI 의존성 없이 Presenter 로직만 검증한다.
    """
    view = MagicMock()

    view.left_section = MagicMock()
    view.right_section = MagicMock()
    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()
    view.left_section.manual_control_panel = MagicMock()
    view.left_section.system_log_widget = MagicMock()
    view.right_section.packet_panel = MagicMock()
    view.macro_view = MagicMock()
    view.port_view = MagicMock()

    # ManualControlPresenter.get_state()가 on_close_requested()에서 실제로 호출되어
    # SettingsManager.save_settings()의 JSON 직렬화 대상이 되므로, 원시 타입을
    # 반환하도록 명시한다(그렇지 않으면 MagicMock이 그대로 값으로 들어가 직렬화 실패).
    view.manual_control_view = MagicMock()
    view.manual_control_view.get_input_text.return_value = ""
    view.manual_control_view.is_hex_mode.return_value = False
    view.manual_control_view.is_prefix_enabled.return_value = False
    view.manual_control_view.is_suffix_enabled.return_value = False
    view.manual_control_view.is_rts_enabled.return_value = False
    view.manual_control_view.is_dtr_enabled.return_value = False
    view.manual_control_view.is_broadcast_enabled.return_value = False

    view.settings_save_requested = MagicMock()
    view.font_settings_changed = MagicMock()
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.port_tab_added = MagicMock()

    view.get_port_tabs_count.return_value = 0

    # on_close_requested()가 실제로 SettingsManager.save_settings()까지 실행되므로
    # (S-055: 종료 시퀀스에서 라이터를 닫는 경로를 실제로 검증하기 위함),
    # get_window_state()는 JSON 직렬화 가능한 실제 DTO를 반환해야 한다.
    view.get_window_state.return_value = MainWindowState(
        left_section_state={}, right_section_state={}
    )

    return view


@pytest.fixture
def presenter(mock_main_window, mock_settings_manager):
    """실제(임시 경로) SettingsManager를 주입한 MainPresenter 인스턴스."""
    with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
        return MainPresenter(mock_main_window)


class TestMainPresenterSystemLogPersistence:
    """토글 ON → 기록 → 토글 OFF/종료 시 닫힘까지 실제 파일 시스템으로 검증한다."""

    def test_start_then_line_then_stop_writes_and_closes_real_file(self, presenter, tmp_path):
        """토글 ON 후 들어온 줄이 파일에 쓰이고, 토글 OFF 후 더 이상 쓰이지 않는다."""
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)

        # 1. REC 시작
        presenter._on_sys_logging_start_requested()
        presenter.view.port_view.set_logging_active.assert_any_call(True)
        assert presenter._sys_log_writer is not None
        assert presenter._sys_log_writer.is_open is True

        # 2. 화면에 추가되는 시점과 동일한 경로로 라인 전달 (View가 실제로 emit하는 시그널을
        #    직접 호출해 시뮬레이션 — Presenter 쪽 배선만 검증)
        presenter._on_system_log_line_appended("[12:00:00] [INFO] hello")

        # 3. REC 중지 전에는 이미 파일에 반영되어 있어야 한다(줄마다 flush).
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] hello\n"

        # 4. REC 중지 -> 파일이 닫힌다.
        presenter._on_sys_logging_stop_requested()
        assert presenter._sys_log_writer is None

        # 5. 중지 후 들어오는 라인은 더 이상 기록되지 않는다.
        presenter._on_system_log_line_appended("[12:00:01] [INFO] should not be written")
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] hello\n"

    def test_open_failure_surfaces_error_and_leaves_recording_off(self, presenter, tmp_path):
        """파일 열기 실패는 조용히 삼키지 않고 ERROR로 표면화하며 REC를 켜지 않는다."""
        # 존재할 수 없는 경로(파일을 디렉터리로 취급하게 만들어 open 실패를 유도)
        blocking_file = tmp_path / "not_a_dir"
        blocking_file.write_text("x", encoding="utf-8")
        bad_path = blocking_file / "system_log.txt"  # 부모가 디렉터리가 아님 -> OSError

        presenter.view.port_view.show_save_log_dialog.return_value = str(bad_path)

        presenter._on_sys_logging_start_requested()

        assert presenter._sys_log_writer is None
        presenter.view.port_view.set_logging_active.assert_any_call(False)
        # ERROR 레벨 시스템 로그로 실패가 표면화되었는지 확인
        error_calls = [
            call for call in presenter.view.log_system_message.call_args_list
            if call.args[0].level == "ERROR"
        ]
        assert len(error_calls) >= 1

    def test_write_failure_stops_recording_and_surfaces_error(self, presenter, tmp_path):
        """쓰기 실패 시 라이터를 닫고 REC를 끈 뒤 ERROR로 표면화하며, 무한 재귀로 이어지지
        않는다(라이터를 먼저 정리하므로 재귀 호출은 즉시 반환된다)."""
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)
        presenter._on_sys_logging_start_requested()
        assert presenter._sys_log_writer is not None

        with patch.object(TextLogWriter, "write_line", side_effect=OSError("disk full")):
            # 예외가 밖으로 전파되지 않아야 한다(내부에서 처리)
            presenter._on_system_log_line_appended("[12:00:00] [INFO] boom")

        assert presenter._sys_log_writer is None
        presenter.view.port_view.set_logging_active.assert_any_call(False)
        error_calls = [
            call for call in presenter.view.log_system_message.call_args_list
            if call.args[0].level == "ERROR"
        ]
        assert len(error_calls) >= 1

    def test_cancel_dialog_does_not_create_writer(self, presenter):
        """다이얼로그 취소(빈 경로 반환) 시 라이터가 생성되지 않는다."""
        presenter.view.port_view.show_save_log_dialog.return_value = ""

        presenter._on_sys_logging_start_requested()

        assert presenter._sys_log_writer is None
        presenter.view.port_view.set_logging_active.assert_any_call(False)

    def test_app_shutdown_closes_open_writer_without_data_loss(self, presenter, tmp_path):
        """REC 중 앱이 종료되어도(on_close_requested) 파일이 닫혀 유실이 없어야 한다."""
        file_path = tmp_path / "system_log.txt"
        presenter.view.port_view.show_save_log_dialog.return_value = str(file_path)

        presenter._on_sys_logging_start_requested()
        presenter._on_system_log_line_appended("[12:00:00] [INFO] before shutdown")
        writer = presenter._sys_log_writer
        assert writer.is_open is True

        presenter.on_close_requested()

        assert presenter._sys_log_writer is None
        assert writer.is_open is False
        assert file_path.read_text(encoding="utf-8") == "[12:00:00] [INFO] before shutdown\n"

    def test_app_shutdown_without_active_recording_does_not_raise(self, presenter):
        """REC 중이 아닐 때 종료해도(라이터가 None) 예외 없이 통과한다."""
        assert presenter._sys_log_writer is None
        presenter.on_close_requested()  # 예외 없이 완료되어야 함
        assert presenter._sys_log_writer is None
