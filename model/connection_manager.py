"""
연결 매니저 모듈

전역 ConnectionController 인스턴스를 관리하는 중앙 레지스트리입니다.

## WHY
* 애플리케이션 전역에서 접근 가능한 연결 관리 포인트 필요
* Thread-safe한 싱글톤 패턴으로 데이터 일관성 보장
* 여러 종류의 연결 컨트롤러 확장을 위한 기반

## WHAT
* ConnectionController 인스턴스 생성 및 수명 주기 관리
* 연결 추가/제거 이벤트 발행
* 전체 연결 일괄 종료 기능

## HOW
* QMutex를 사용한 Thread-safe 싱글톤 구현
* Dictionary를 이용한 컨트롤러 관리
* Lazy Initialization으로 필요 시점 생성
"""
from typing import Dict, List
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from model.connection_controller import ConnectionController

class ConnectionManager(QObject):
    """
    ConnectionController 중앙 레지스트리 (Singleton)

    애플리케이션 전체의 연결 컨트롤러들을 관리합니다.
    """
    _instance = None
    _lock = QMutex()

    # Signal 정의
    controller_added = pyqtSignal(str)    # Controller 생성됨
    controller_removed = pyqtSignal(str)  # Controller 제거됨

    def __new__(cls):
        """Thread-safe 싱글톤 인스턴스 생성"""
        if cls._instance is None:
            with QMutexLocker(cls._lock):
                if cls._instance is None:
                    cls._instance = super(ConnectionManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """ConnectionManager 초기화"""
        if self._initialized:
            return
        super().__init__()
        self._connection_controllers: Dict[str, ConnectionController] = {}
        self._initialized = True

    def get_controller(self, name: str = "default") -> ConnectionController:
        """
        이름에 해당하는 ConnectionController 반환

        Logic:
            - 기존 Controller가 있으면 반환
            - 없으면 새로 생성하여 등록 후 반환
            - controller_added Signal 발행

        Args:
            name: 컨트롤러 식별 이름 (기본값: 'default')

        Returns:
            ConnectionController: 해당 이름의 컨트롤러 인스턴스
        """
        with QMutexLocker(self._lock):
            if name not in self._connection_controllers:
                controller = ConnectionController()
                self._connection_controllers[name] = controller
                self.controller_added.emit(name)

            return self._connection_controllers[name]

    def remove_controller(self, name: str) -> None:
        """
        ConnectionController 제거 및 정리

        Args:
            name: 제거할 컨트롤러 이름
        """
        with QMutexLocker(self._lock):
            if name in self._connection_controllers:
                controller = self._connection_controllers[name]
                # 열려있는 모든 연결 종료
                if controller.has_active_connection:
                    controller.close_connection()

                del self._connection_controllers[name]
                self.controller_removed.emit(name)

    def get_all_controllers(self) -> List[ConnectionController]:
        """
        모든 활성 ConnectionController 목록 반환

        Returns:
            List[ConnectionController]: 컨트롤러 리스트
        """
        with QMutexLocker(self._lock):
            return list(self._connection_controllers.values())

    def close_all_controllers(self) -> None:
        """
        모든 컨트롤러의 연결 종료 및 정리

        Logic:
            - 등록된 모든 컨트롤러 순회
            - 각 컨트롤러의 연결 종료 요청
            - 리스트 초기화
        """
        with QMutexLocker(self._lock):
            for controller in self._connection_controllers.values():
                controller.close_connection()
            self._connection_controllers.clear()

# 전역 인스턴스
connection_manager = ConnectionManager()