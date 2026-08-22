"""
텍스트 로그 라이터 모듈 (Text Log Writer)

시스템 로그처럼 줄(line) 단위 텍스트로 구성된 로그를 파일에 append 방식으로 기록합니다.

## WHY
* `core/data_logger.py`(DataLogger)는 시리얼 RX 바이트 스트림(BIN/HEX/PCAP) 전용이라
  시스템 로그 같은 줄 단위 텍스트에는 맞지 않는다.
* S-052에서 시스템 로그 REC 토글의 제어 흐름(Presenter 권위)만 통일했고, 실제 파일
  기록은 기능 격차로 남아 있었다(S-055) — 토글을 켜도 파일에 아무것도 쓰이지 않았다.
* 실패를 조용히 삼키지 않는다(S-039/S-045와 동일 원칙) — 파일 열기/쓰기 실패는 예외로
  호출자(Presenter)에 전달해 사용자에게 표면화할 수 있게 한다.

## WHAT
* TextLogWriter: 단일 텍스트 로그 파일을 열고/줄 단위로 쓰고/닫는 얇은 래퍼.

## HOW
* 시스템 로그는 RX 데이터에 비해 발생 빈도가 낮고 대용량도 아니므로 DataLogger처럼
  Queue+백그라운드 스레드를 두지 않고, 호출 스레드(UI 스레드)에서 동기적으로
  open/write/flush 한다. 줄마다 flush하여 비정상 종료 시에도 유실을 최소화한다.
* 실패는 예외를 그대로 전파한다 — 성공/실패를 조용히 bool로만 반환하면 호출자가
  실패를 무시하기 쉬워지므로, 명시적으로 처리하도록 강제한다.
"""
import os


class TextLogWriter:
    """
    줄 단위 텍스트 로그를 파일에 append하는 라이터.

    열기 실패/쓰기 실패는 예외로 전파되므로, 호출자가 반드시 처리해야 한다
    (조용히 삼키지 않는다는 원칙 — S-039/S-045/S-055).
    """

    def __init__(self) -> None:
        """TextLogWriter 초기화."""
        self._file = None
        self.file_path: str = ""

    @property
    def is_open(self) -> bool:
        """현재 파일이 열려 있는지 여부."""
        return self._file is not None

    def open(self, file_path: str) -> None:
        """
        로그 파일을 append 모드로 엽니다.

        Logic:
            - 이미 열려 있으면 먼저 닫는다(중복 open 방지).
            - 상위 디렉터리가 없으면 생성한다.
            - 텍스트 모드(UTF-8, 개행 변환 없음)로 append open.

        Args:
            file_path: 저장할 파일 경로.

        Raises:
            OSError: 디렉터리 생성 또는 파일 열기에 실패한 경우.
        """
        if self._file is not None:
            self.close()

        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # newline=''로 자동 개행 변환을 막고, write_line에서 명시적으로 '\n'을 붙인다.
        self._file = open(file_path, 'a', encoding='utf-8', newline='')
        self.file_path = file_path

    def write_line(self, text: str) -> None:
        """
        한 줄을 기록하고 즉시 flush합니다.

        Args:
            text: 기록할 한 줄(개행 문자는 내부에서 추가하므로 포함하지 않는다).

        Raises:
            OSError: 파일이 열려 있지 않거나 쓰기/flush에 실패한 경우.
        """
        if self._file is None:
            raise OSError("TextLogWriter.write_line() called before open()")
        self._file.write(text + "\n")
        self._file.flush()

    def close(self) -> None:
        """
        파일을 닫습니다.

        Logic:
            - 이미 닫혀 있으면 아무 동작도 하지 않는다(중복 close 안전).
            - flush/close 실패(예: 디스크 오류 후 정리 과정)가 나더라도 예외를
              전파하지 않는다 — close()는 정리(cleanup) 목적이라 실패해도
              호출자(예: 쓰기 실패 처리 중, 앱 종료 시퀀스 중)를 막지 않아야
              한다. 실질적으로 남길 수 있는 조치가 없으므로 상태만 리셋한다.
        """
        if self._file is None:
            return
        try:
            self._file.flush()
        except OSError:
            pass
        finally:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
            self.file_path = ""
