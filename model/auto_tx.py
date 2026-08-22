"""
자동 반복 전송 스케줄러 모듈

수동 Command 하나를 지정한 주기(interval_ms)로 반복 전송 요청하는 모듈입니다.

## WHY
* 폴링성 Command(예: 상태 조회 AT 명령)를 일정 주기로 반복 전송할 필요
* MacroRunner는 리스트 순차 실행용이라 "한 명령을 N ms마다" 용도로는 무거움
* 정밀 타이밍이 목적이 아니므로 별도 QThread 없이 UI 스레드 QTimer로 충분

## WHAT
* 지정된 ManualCommand를 interval_ms 주기로 반복 발신 요청(send_requested)
* 시작 즉시 1회 발신 후 타이머 시작, max_runs 도달 시 자동 정지 및 종료 알림
* 진행 상태(progress) 알림 및 중복 시작 시 재시작 처리

## HOW
* UI 스레드 상주 QTimer + pyqtSignal 기반 (실제 I/O는 Presenter가 기존 전송 경로로 수행)
* interval_ms는 MIN_AUTO_TX_INTERVAL_MS로 하한 clamp하여 TX 큐 포화 방지
"""
from typing import Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from common.dtos import ManualCommand
from common.constants import MIN_AUTO_TX_INTERVAL_MS


class AutoTxScheduler(QObject):
    """
    ManualCommand를 일정 주기로 반복 전송 요청하는 스케줄러 클래스

    UI 스레드에 상주하는 QTimer를 사용하며, 실제 전송 처리(prefix/suffix 가공,
    포트 전송)는 상위(Presenter)에 위임합니다(`send_requested` 시그널).
    """

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------
    # 전송 요청 시그널 (ManualCommand DTO 전달, MacroRunner와 동일 패턴)
    send_requested = pyqtSignal(object)

    # 반복 진행 상태 알림 (현재 횟수, 총 횟수 - 총 횟수 0은 무한)
    progress = pyqtSignal(int, int)

    # 종료 알림 (max_runs 도달로 자동 정지된 경우에만 발생 — 사용자 stop()은 발생시키지 않음)
    finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """
        AutoTxScheduler를 초기화합니다.

        Args:
            parent (Optional[QObject]): 부모 QObject. 기본값 None.
        """
        super().__init__(parent)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)

        self._command: Optional[ManualCommand] = None
        self._max_runs = 0
        self._current_run = 0

    @property
    def is_running(self) -> bool:
        """
        현재 반복 전송 중인지 여부를 반환합니다.

        Returns:
            bool: 내부 타이머가 활성 상태이면 True.
        """
        return self._timer.isActive()

    def start(self, command: ManualCommand, interval_ms: int, max_runs: int = 0) -> None:
        """
        반복 전송을 시작합니다.

        Logic:
            1. 이미 실행 중이면 기존 타이머를 정지 후 새 설정으로 재시작(중복 호출 안전 처리)
            2. interval_ms를 MIN_AUTO_TX_INTERVAL_MS로 하한 clamp
            3. 즉시 1회 발신(send_requested) 및 진행 상태(progress) 통지
            4. 1회만으로 max_runs에 도달했다면 타이머를 시작하지 않고 즉시 종료 처리
            5. 그 외에는 clamp된 간격으로 타이머 시작

        Args:
            command (ManualCommand): 반복 전송할 명령어 DTO.
            interval_ms (int): 전송 간격 (ms). 하한 미만이면 clamp됨.
            max_runs (int): 최대 실행 횟수 (0=무한). 기본값 0.
        """
        if self.is_running:
            self._timer.stop()

        self._command = command
        self._max_runs = max_runs
        self._current_run = 1

        # 시작 즉시 1회 발신
        self.send_requested.emit(self._command)
        self.progress.emit(self._current_run, self._max_runs)

        if 0 < self._max_runs <= self._current_run:
            self._finish()
            return

        clamped_interval = max(interval_ms, MIN_AUTO_TX_INTERVAL_MS)
        self._timer.start(clamped_interval)

    def stop(self) -> None:
        """
        반복 전송을 중단합니다.

        사용자/상위 계층의 명시적 중단이므로 `finished` 시그널은 발생하지 않습니다
        (`finished`는 max_runs 도달에 의한 자동 종료 전용).
        """
        self._timer.stop()

    def _on_timeout(self) -> None:
        """
        타이머 만료 시 호출되어 다음 회차를 전송합니다. (QTimer.timeout 슬롯)
        """
        if self._command is None:
            self._timer.stop()
            return

        self._current_run += 1
        self.send_requested.emit(self._command)
        self.progress.emit(self._current_run, self._max_runs)

        if 0 < self._max_runs <= self._current_run:
            self._finish()

    def _finish(self) -> None:
        """
        max_runs 도달로 인한 자동 정지 처리 후 `finished` 시그널을 발신합니다.
        """
        self._timer.stop()
        self.finished.emit()
