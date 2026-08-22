"""
S-058 신규 테스트: LoggingFormatResolver (presenter/logging_format_resolver.py)

## WHY
* 기존에는 확장자->LogFormat 매핑 로직이 MainPresenter 내부에 있어 QWidget
  스택 전체(Presenter 생성)가 있어야만 검증할 수 있었다. 분리 후에는 Qt/View
  의존이 전혀 없는 순수 함수이므로 이를 고정한다.

## WHAT
* `.pcap` -> LogFormat.PCAP, `.txt` -> LogFormat.HEX, 그 외(미확장자 포함) ->
  LogFormat.BIN 매핑을 검증한다.
* 대소문자 무관(확장자 case-insensitive) 동작을 검증한다.

## HOW
* Qt import 없이 순수 함수 호출만으로 검증 (QApplication/QWidget 생성 불필요).
"""
from presenter.logging_format_resolver import LoggingFormatResolver
from common.enums import LogFormat


class TestLoggingFormatResolver:
    """LoggingFormatResolver.resolve()의 확장자 매핑 규칙을 고정한다."""

    def test_pcap_extension_resolves_to_pcap_format(self):
        assert LoggingFormatResolver.resolve("C:/logs/capture.pcap") == LogFormat.PCAP

    def test_txt_extension_resolves_to_hex_format(self):
        assert LoggingFormatResolver.resolve("C:/logs/capture.txt") == LogFormat.HEX

    def test_unknown_extension_falls_back_to_bin_format(self):
        assert LoggingFormatResolver.resolve("C:/logs/capture.bin") == LogFormat.BIN
        assert LoggingFormatResolver.resolve("C:/logs/capture.log") == LogFormat.BIN

    def test_no_extension_falls_back_to_bin_format(self):
        assert LoggingFormatResolver.resolve("C:/logs/capture") == LogFormat.BIN

    def test_extension_matching_is_case_insensitive(self):
        assert LoggingFormatResolver.resolve("C:/logs/CAPTURE.PCAP") == LogFormat.PCAP
        assert LoggingFormatResolver.resolve("C:/logs/CAPTURE.TXT") == LogFormat.HEX
