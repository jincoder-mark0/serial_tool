from typing import Dict, List, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
from model.port_controller import PortController

class SerialManager(QObject):
    """
    애플리케이션 전체의 PortController 인스턴스를 관리하는 중앙 레지스트리 (싱글톤 패턴).
    """
    _instance = None
    _lock = QMutex() # 싱글톤 생성을 위한 락

    # 시그널 정의
    port_added = pyqtSignal(str)    # 포트 컨트롤러 생성됨
    port_removed = pyqtSignal(str)  # 포트 컨트롤러 제거됨

    def __new__(cls):
        if cls._instance is None:
            with QMutexLocker(cls._lock):
                if cls._instance is None:
                    cls._instance = super(SerialManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._controllers: Dict[str, PortController] = {}
        self._initialized = True

    @property
    def active_ports(self) -> List[str]:
        """현재 관리 중인 포트 이름 목록을 반환합니다."""
        return list(self._controllers.keys())

    def get_port(self, port_name: str) -> PortController:
        """
        해당 포트 이름의 PortController를 반환합니다.
        없으면 새로 생성하여 등록합니다.
        """
        if port_name not in self._controllers:
            controller = PortController()
            # 포트 이름 설정 (PortController에 set_port_name 메서드가 있다고 가정하거나, open 시 설정됨)
            # 여기서는 관리 목적으로 딕셔너리에 저장
            self._controllers[port_name] = controller
            self.port_added.emit(port_name)
        
        return self._controllers[port_name]

    def remove_port(self, port_name: str) -> None:
        """
        해당 포트의 컨트롤러를 제거합니다.
        포트가 열려있다면 닫습니다.
        """
        if port_name in self._controllers:
            controller = self._controllers[port_name]
            if controller.is_open:
                controller.close_port()
            
            del self._controllers[port_name]
            self.port_removed.emit(port_name)

    def get_all_ports(self) -> List[PortController]:
        """모든 활성 PortController 목록을 반환합니다."""
        return list(self._controllers.values())

    def close_all_ports(self) -> None:
        """모든 포트를 닫고 정리합니다."""
        for name, controller in list(self._controllers.items()):
            if controller.is_open:
                controller.close_port()
            # 필요하다면 여기서 remove_port 호출 또는 딕셔너리 비우기
        self._controllers.clear()
