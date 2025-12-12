"""
시리얼 매니저 모듈

PortController 인스턴스의 중앙 레지스트리 역할을 수행합니다.

## WHY
* 다중 포트 환경에서 PortController 생명주기 관리
* 포트별 독립적인 Controller 인스턴스 제공
* 전역 포트 상태 추적 및 정리
* Thread-safe한 싱글톤 패턴으로 일관성 보장

## WHAT
* PortController 인스턴스 생성 및 관리
* 포트 추가/제거 이벤트 발행
* 활성 포트 목록 조회
* 전체 포트 일괄 종료

## HOW
* QMutex로 Thread-safe 싱글톤 구현
* Dictionary로 포트명-Controller 매핑
* PyQt Signal로 포트 추가/제거 이벤트 발행
* Lazy initialization으로 필요 시 Controller 생성
"""
from typing import Dict, List, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from model.port_controller import PortController

class SerialManager(QObject):
    """
    PortController 중앙 레지스트리 (Singleton)

    애플리케이션 전체의 PortController 인스턴스를 관리합니다.
    """
    _instance = None
    _lock = QMutex() # Thread-safe 싱글톤을 위한 Mutex

    # Signal 정의
    port_added = pyqtSignal(str)    # PortController 생성됨
    port_removed = pyqtSignal(str)  # PortController 제거됨

    def __new__(cls):
        """Thread-safe 싱글톤 인스턴스 생성"""
        if cls._instance is None:
            with QMutexLocker(cls._lock):
                if cls._instance is None:
                    cls._instance = super(SerialManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """SerialManager 초기화"""
        if self._initialized:
            return
        super().__init__()
        self._controllers: Dict[str, PortController] = {}
        self._initialized = True

    @property
    def active_ports(self) -> List[str]:
        """현재 관리 중인 포트 이름 목록 반환"""
        return list(self._controllers.keys())

    def get_port(self, port_name: str) -> PortController:
        """
        포트 이름에 해당하는 PortController 반환

        Logic:
            - 기존 Controller가 있으면 반환
            - 없으면 새로 생성하여 등록 후 반환
            - port_added Signal 발행

        Args:
            port_name: 포트 이름

        Returns:
            PortController: 해당 포트의 Controller 인스턴스
        """
        if port_name not in self._controllers:
            controller = PortController()
            self._controllers[port_name] = controller
            self.port_added.emit(port_name)

        return self._controllers[port_name]

    def remove_port(self, port_name: str) -> None:
        """
        포트 Controller 제거

        Logic:
            - 포트가 열려있으면 먼저 닫기
            - Dictionary에서 제거
            - port_removed Signal 발행

        Args:
            port_name: 제거할 포트 이름
        """
        if port_name in self._controllers:
            controller = self._controllers[port_name]
            if controller.is_open:
                controller.close_port()

            del self._controllers[port_name]
            self.port_removed.emit(port_name)

    def get_all_ports(self) -> List[PortController]:
        """모든 활성 PortController 목록 반환"""
        return list(self._controllers.values())

    def close_all_ports(self) -> None:
        """
        모든 포트 종료 및 정리

        Logic:
            - 모든 열린 포트 닫기
            - Controller Dictionary 초기화
        """
        for name, controller in list(self._controllers.items()):
            if controller.is_open:
                controller.close_port()
            # 필요하다면 여기서 remove_port 호출 또는 딕셔너리 비우기
        self._controllers.clear()
