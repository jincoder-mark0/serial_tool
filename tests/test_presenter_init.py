import sys
import unittest
from PyQt5.QtWidgets import QApplication
from view.main_window import MainWindow
from presenter.main_presenter import MainPresenter
from resource_path import ResourcePath

# QApplication instance needed for widgets
app = QApplication(sys.argv)

class TestPresenterInit(unittest.TestCase):
    def test_main_presenter_init(self):
        """MainPresenter 초기화 테스트"""
        resource_path = ResourcePath()
        window = MainWindow(resource_path=resource_path)
        presenter = MainPresenter(window)
        
        self.assertIsNotNone(presenter.port_controller)
        self.assertIsNotNone(presenter.macro_runner)
        self.assertIsNotNone(presenter.event_router)
        self.assertIsNotNone(presenter.port_presenter)
        self.assertIsNotNone(presenter.macro_presenter)
        self.assertIsNotNone(presenter.file_presenter)
        
        print("MainPresenter initialized successfully")

if __name__ == '__main__':
    unittest.main()
