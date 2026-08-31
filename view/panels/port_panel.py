"""Unified connection-tab View facade.

The Port tab remains one UI surface for Serial/SPI/I2C. Protocol-specific
configuration is encapsulated by ConnectionSettingsWidget and runtime routing
stays outside the View.
"""
from typing import List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from common.constants import LAYOUT_MARGIN_NONE, LAYOUT_SPACING_TIGHT
from common.dtos import ColorRule, PortInfo, PortStatistics
from core.transport.transaction.dto import AdapterDescriptor
from view.managers.language_manager import language_manager
from view.widgets.connection_settings import ConnectionSettingsWidget
from view.widgets.data_log import DataLogWidget
from view.widgets.port_stats import PortStatsWidget


class PortPanel(QWidget):
    """Serial/SPI/I2C가 공유하는 하나의 연결 탭."""

    tab_title_changed = pyqtSignal(str)
    connect_requested = pyqtSignal(object)
    disconnect_requested = pyqtSignal()
    port_scan_requested = pyqtSignal()
    endpoint_refresh_requested = pyqtSignal(str)
    protocol_changed = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

    tx_broadcast_allowed_changed = pyqtSignal(bool)
    logging_start_requested = pyqtSignal()
    logging_stop_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._data_log_widget: Optional[DataLogWidget] = None
        self._port_stats_widget: Optional[PortStatsWidget] = None
        self._port_settings_widget: Optional[ConnectionSettingsWidget] = None
        self.custom_name = language_manager.get_text("port_tab_default_name")
        self.init_ui()
        self._port_settings_widget.endpoint_changed.connect(self.update_tab_title)

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
            LAYOUT_MARGIN_NONE,
        )
        layout.setSpacing(LAYOUT_SPACING_TIGHT)

        self._port_settings_widget = ConnectionSettingsWidget()
        self._port_stats_widget = PortStatsWidget()
        self._data_log_widget = DataLogWidget()

        self._port_settings_widget.connect_requested.connect(self.connect_requested.emit)
        self._port_settings_widget.disconnect_requested.connect(
            self.disconnect_requested.emit
        )
        self._port_settings_widget.port_scan_requested.connect(
            self.port_scan_requested.emit
        )
        self._port_settings_widget.endpoint_refresh_requested.connect(
            self.endpoint_refresh_requested.emit
        )
        # endpoint refresh carries the selected protocol. Relaying it as a
        # protocol hint keeps Presenter/View coupling at the facade boundary.
        self._port_settings_widget.endpoint_refresh_requested.connect(
            self.protocol_changed.emit
        )
        self._port_settings_widget.port_connection_changed.connect(
            self.connection_changed.emit
        )

        self._data_log_widget.tx_broadcast_allowed_changed.connect(
            self.tx_broadcast_allowed_changed.emit
        )
        self._data_log_widget.logging_start_requested.connect(
            self.logging_start_requested.emit
        )
        self._data_log_widget.logging_stop_requested.connect(
            self.logging_stop_requested.emit
        )

        layout.addWidget(self._port_settings_widget)
        layout.addWidget(self._port_stats_widget)
        layout.addWidget(self._data_log_widget, 1)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Connection facade
    # ------------------------------------------------------------------
    def get_port_config(self):
        """Legacy name: returns Serial or transaction connection config."""
        return self._port_settings_widget.get_current_config()

    def get_connection_config(self):
        return self._port_settings_widget.get_current_config()

    def current_protocol(self) -> str:
        return self._port_settings_widget.current_protocol()

    def set_port_list(self, ports: List[PortInfo]) -> None:
        self._port_settings_widget.set_port_list(ports)

    def set_adapter_descriptors(self, descriptors: List[AdapterDescriptor]) -> None:
        self._port_settings_widget.set_adapter_descriptors(descriptors)

    def set_connected(self, connected: bool) -> None:
        self._port_settings_widget.set_connected(connected)

    def toggle_connection(self) -> None:
        self._port_settings_widget.toggle_connection()

    def is_connected(self) -> bool:
        return self._port_settings_widget.is_connected()

    def get_port_name(self) -> str:
        return self._port_settings_widget.get_connection_display_name()

    def get_connection_display_name(self) -> str:
        return self._port_settings_widget.get_connection_display_name()

    # ------------------------------------------------------------------
    # Log / stats facade
    # ------------------------------------------------------------------
    def append_log_data(self, data: bytes) -> None:
        self._data_log_widget.append_data(data)

    def clear_data_log(self) -> None:
        self._data_log_widget.on_clear_data_log_clicked()

    def trigger_log_save(self) -> None:
        self._data_log_widget.on_data_log_logging_toggled(True)

    def set_max_log_lines(self, max_lines: int) -> None:
        self._data_log_widget.set_max_lines(max_lines)

    def update_statistics(self, stats: PortStatistics) -> None:
        self._port_stats_widget.update_statistics(stats)

    def set_logging_active(self, active: bool) -> None:
        self._data_log_widget.set_logging_active(active)

    def show_save_log_dialog(self) -> str:
        return self._data_log_widget.show_save_log_dialog()

    def set_data_log_color_rules(self, rules: List[ColorRule]) -> None:
        self._data_log_widget.set_color_rules(rules)

    # ------------------------------------------------------------------
    # Tab facade
    # ------------------------------------------------------------------
    def get_custom_name(self) -> str:
        return self.custom_name

    def set_custom_name(self, name: str) -> None:
        self.custom_name = name
        self.update_tab_title()

    def get_tab_title(self) -> str:
        endpoint = self.get_connection_display_name()
        return f"{self.custom_name}:{endpoint}" if endpoint else self.custom_name

    def update_tab_title(self, *_args) -> None:
        title = self.get_tab_title()
        self._data_log_widget.set_tab_name(title)
        self.tab_title_changed.emit(title)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def get_state(self) -> dict:
        return {
            "custom_name": self.custom_name,
            "port_settings_widget": self._port_settings_widget.get_state(),
            "data_log_widget": self._data_log_widget.get_state(),
        }

    def apply_state(self, state: dict) -> None:
        if not state:
            return
        self.custom_name = state.get(
            "custom_name",
            language_manager.get_text("port_tab_default_name"),
        )
        self._port_settings_widget.apply_state(
            state.get("port_settings_widget", {})
        )
        self._data_log_widget.apply_state(state.get("data_log_widget", {}))
        self.update_tab_title()
