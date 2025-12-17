"""
포트 스캐너 모듈

시스템의 시리얼 포트를 검색하는 비동기 워커를 정의합니다.
기존 'presenter/port_presenter.py'에서 Model 계층으로 이동되었습니다.

## WHY
* 포트 검색은 데이터(Resource)를 조회하는 역할이므로 Model 계층이 적합합니다.
* Presenter가 구체적인 스레드 구현이나 라이브러리(pyserial)에 직접 의존하는 것을 방지합니다.

## WHAT
* PortScanWorker: QThread 기반 비동기 포트 스캐너

## HOW
* serial.tools.list_ports 사용
* Natural Sorting 알고리즘 적용
"""
import re
import serial.tools.list_ports
from PyQt5.QtCore import QThread, pyqtSignal
from typing import List, Tuple
from core.logger import logger

class PortScanWorker(QThread):
    """
    비동기 포트 스캔 워커

    시스템의 시리얼 포트 목록을 백그라운드 스레드에서 조회합니다.
    Windows 등에서 포트 스캔 시 발생하는 수백 ms의 지연으로 인한 UI 프리징을 방지합니다.
    """
    # (device, description) 튜플 리스트 전달
    ports_found = pyqtSignal(list)

    def run(self) -> None:
        """
        스캔 실행 (Thread Entry Point)

        Logic:
            1. pyserial을 통해 포트 목록 획득
            2. Natural Sort (COM1 -> COM2 -> COM10) 정렬
            3. 시그널 발행
        """
        try:
            # 1. 포트 정보 수집
            raw_ports = serial.tools.list_ports.comports()
            port_list: List[Tuple[str, str]] = []

            for port in raw_ports:
                port_list.append((port.device, port.description))

            # 2. Natural Sort (자연 정렬) 키 함수
            # 예: ['COM', '1'] vs ['COM', '10'] -> 숫자 비교 가능
            def natural_sort_key(item):
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split('([0-9]+)', item[0])]

            port_list.sort(key=natural_sort_key)

            # 결과 전달
            self.ports_found.emit(port_list)

        except Exception as e:
            logger.error(f"Port scan failed: {e}")
            # 실패 시 빈 리스트 전달
            self.ports_found.emit([])
