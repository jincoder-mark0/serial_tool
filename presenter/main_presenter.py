from PyQt5.QtCore import QObject
from view.main_window import MainWindow
from model.port_controller import PortController
from .port_presenter import PortPresenter

class MainPresenter(QObject):
    """
    애플리케이션을 조율하는 메인 Presenter 클래스입니다.
    하위 Presenter들을 초기화하고 전역 상태를 관리합니다.
    """
    def __init__(self, view: MainWindow) -> None:
        """
        MainPresenter를 초기화합니다.
        
        Args:
            view (MainWindow): 메인 윈도우 인스턴스.
        """
        super().__init__()
        self.view = view
        
        # 모델 초기화 (Initialize Models)
        self.port_controller = PortController()
        
        # 하위 Presenter 초기화 (Initialize Sub-Presenters)
        self.port_presenter = PortPresenter(self.view.left_panel, self.port_controller)
        
        # 데이터 수신 시그널을 로그 뷰에 연결
        self.port_controller.data_received.connect(self.on_data_received)
        
        # 수동 전송 버튼 연결
        self.view.left_panel.manual_control.send_btn.clicked.connect(self.on_manual_send)
        
    def on_data_received(self, data: bytes) -> None:
        """
        수신된 시리얼 데이터를 처리합니다.
        현재 활성 포트 패널의 ReceivedArea로 데이터를 전달합니다.
        
        Args:
            data (bytes): 수신된 바이트 데이터.
        """
        # 현재 활성 포트 패널을 가져와서 ReceivedArea로 데이터 전달
        index = self.view.left_panel.port_tabs.currentIndex()
        if index >= 0:
            widget = self.view.left_panel.port_tabs.widget(index)
            if hasattr(widget, 'received_area'):
                widget.received_area.append_data(data)
                
    def on_manual_send(self) -> None:
        """
        수동 전송 버튼 클릭을 처리합니다.
        입력 필드의 텍스트를 가져와 포트로 전송합니다.
        """
        text = self.view.left_panel.manual_control.input_field.text()
        if text and self.port_controller.is_open:
            # 텍스트를 바이트로 변환
            # TODO: HEX 모드, 라인 엔딩 등을 처리해야 함
            data = text.encode('utf-8')
            self.port_controller.send_data(data)
            # 전송 후 입력 필드 초기화
            self.view.left_panel.manual_control.input_field.clear()
        elif not self.port_controller.is_open:
            print("Port not open")
