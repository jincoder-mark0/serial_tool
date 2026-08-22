"""
로깅 포맷 결정 모듈

파일 확장자를 기반으로 데이터 로깅에 사용할 LogFormat을 결정하는 순수 로직을
담당합니다 (S-058 — MainPresenter God object 분해 1번 후보).

## WHY
* 기존에는 이 매핑 로직이 MainPresenter._on_logging_start_requested() 내부에
  있어, 확장자->포맷 규칙 하나를 테스트하는 데도 QWidget 스택 전체(Presenter
  생성)가 필요했다.
* Qt/View 의존이 전혀 없는 순수 로직이므로 별도 모듈로 분리해 단위 테스트를
  가볍게 만든다.

## WHAT
* LoggingFormatResolver: 파일 경로 -> LogFormat 결정

## HOW
* os.path.splitext로 확장자를 추출하고 매핑 테이블을 조회한다.
  매칭되지 않는 확장자는 LogFormat.BIN(원본 바이너리)으로 폴백한다.
"""
import os

from common.enums import LogFormat


class LoggingFormatResolver:
    """
    파일 확장자를 기반으로 LogFormat을 결정하는 순수 로직 클래스.

    Model/View/Qt에 의존하지 않으므로 인스턴스 생성 없이 클래스 메서드로만
    사용한다.
    """

    # 확장자(소문자) -> LogFormat 매핑. 매칭되지 않는 확장자는 BIN으로 처리한다.
    _EXTENSION_FORMAT_MAP = {
        '.pcap': LogFormat.PCAP,
        '.txt': LogFormat.HEX,
    }

    @classmethod
    def resolve(cls, file_path: str) -> LogFormat:
        """
        파일 경로의 확장자를 기반으로 LogFormat을 결정합니다.

        Args:
            file_path (str): 사용자가 선택한 로그 파일 경로.

        Returns:
            LogFormat: 확장자에 매칭되는 포맷. 매칭 실패 시 LogFormat.BIN.
        """
        _, ext = os.path.splitext(file_path)
        return cls._EXTENSION_FORMAT_MAP.get(ext.lower(), LogFormat.BIN)
