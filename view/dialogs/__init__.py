"""
View 다이얼로그 모듈
애플리케이션의 다이얼로그 창들을 포함합니다.
"""
from .font_settings_dialog import FontSettingsDialog
from .about_dialog import AboutDialog
from .preferences_dialog import PreferencesDialog
from .file_transfer_dialog import FileTransferDialog

__all__ = [
    'FontSettingsDialog',
    'AboutDialog',
    'PreferencesDialog',
    'FileTransferDialog',
]
