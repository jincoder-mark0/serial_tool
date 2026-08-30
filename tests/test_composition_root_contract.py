"""
SettingsManager composition root / dependency injection 회귀 테스트.

Production 경로에서는 main.py에서 생성한 SettingsManager 하나가 MainPresenter와
Lifecycle/Port/Command/Packet 구성 요소에 전달되어야 합니다.
"""
import inspect

import main
from presenter.lifecycle_manager import AppLifecycleManager
from presenter.main_presenter import MainPresenter
from presenter.port_presenter import PortPresenter


def test_main_composition_root_injects_settings_manager():
    source = inspect.getsource(main.main)
    assert "settings_mgr = SettingsManager(resource_path)" in source
    assert "settings_manager=settings_mgr" in source


def test_main_presenter_passes_same_settings_to_runtime_components():
    source = inspect.getsource(MainPresenter)
    assert "AppLifecycleManager(self, self.settings_manager)" in source
    assert "self.connection_controller,\n            self.settings_manager" in source
    assert "self.view.packet_view,\n            self.connection_controller,\n            self.settings_manager" in source
    assert "self.view.port_view,\n            self.connection_controller,\n            self.settings_manager" in source


def test_lifecycle_does_not_unconditionally_create_settings_manager():
    source = inspect.getsource(AppLifecycleManager.__init__)
    assert "self.settings_manager = settings_manager" in source
    assert "self.settings_manager = SettingsManager()" not in source


def test_port_presenter_uses_injected_settings_for_packet_configuration():
    source = inspect.getsource(PortPresenter._apply_packet_parser_settings)
    assert "settings = self.settings_manager" in source
    assert "SettingsManager()" not in source
