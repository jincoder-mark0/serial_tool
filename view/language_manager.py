import json
import os
from typing import Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal

class LanguageManager(QObject):
    """
    애플리케이션 다국어 지원을 관리하는 클래스입니다.
    JSON 파일에서 언어 리소스를 로드하고, 언어 변경 시그널을 발생시킵니다.
    """
    
    language_changed = pyqtSignal(str)  # 언어 코드 (예: 'ko', 'en')

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self.current_language = "ko"
        self.resources: Dict[str, Dict[str, str]] = {}
        self.load_resources()

    def load_resources(self) -> None:
        """
        언어 리소스 파일을 로드합니다.
        기본적으로 'en'과 'ko'를 지원합니다.
        실제 파일이 없으면 하드코딩된 기본값을 사용합니다.
        """
        # TODO: 추후 외부 JSON 파일에서 로드하도록 확장 가능
        self.resources = {
            "en": {
                # App
                "app_title": "SerialTool",
                
                # Menu
                "file": "File",
                "view": "View", 
                "help": "Help",
                "new_port_tab": "New Port Tab",
                "exit": "Exit",
                "theme": "Theme",
                "dark_theme": "Dark Theme",
                "light_theme": "Light Theme",
                "font": "Font",
                "preferences": "Preferences",
                "about": "About",
                
                # Status
                "ready": "Ready",
                "connected": "Connected",
                "disconnected": "Disconnected",
                "error": "Error",
                
                # Port Settings
                "port": "Port",
                "scan": "Scan",
                "baudrate": "Baud",
                "data_bits": "Data",
                "parity": "Parity",
                "stop_bits": "Stop",
                "flow_control": "Flow",
                "open_port": "Open",
                "close_port": "Close",
                
                # Manual Control
                "send": "Send",
                "hex_mode": "HEX",
                "add_enter": "Enter",
                "select_file": "Select File",
                "send_file": "Send File",
                
                # Received Area
                "rx_log": "RX Log",
                "timestamp": "TS",
                "pause": "Pause",
                "clear": "Clear",
                "save": "Save",
                "search": "Search (Regex supported)...",
                
                # Command List
                "select_all": "Select All",
                "prefix": "Prefix",
                "command": "Command",
                "suffix": "Suffix",
                "delay": "Delay",
                
                # Command Control
                "run": "Run",
                "run_all": "Run All",
                "auto_run": "Auto Run",
                "stop": "Stop",
                "pause_cmd": "Pause",
                "script": "Script",
                "load_script": "Load",
                "save_script": "Save",
                "interval": "Interval (ms)",
                "max_runs": "Max Runs",
                
                # Status Area
                "status_log": "Status Log",
                
                # Preferences Dialog
                "general": "General",
                "serial": "Serial",
                "logging": "Logging",
                "ui_appearance": "UI Appearance",
                "language": "Language",
                "font_size": "Font Size",
                "default_parameters": "Default Parameters",
                "default_baudrate": "Default Baudrate",
                "auto_scan_interval": "Auto Scan Interval",
                "file_logging": "File Logging",
                "log_directory": "Log Directory",
                "max_log_lines": "Max Log Lines (UI)",
                "browse": "Browse...",
                "ok": "OK",
                "cancel": "Cancel",
                "apply": "Apply",
                
                # About Dialog
                "about_title": "About SerialTool",
                "version": "Version",
                "copyright": "© 2025 SerialTool Team. All rights reserved.",
                "description": "SerialTool is a professional serial communication utility\\ndesigned for high-performance logging and automation.",
                "license": "Licensed under MIT License",
                "close": "Close",
                
                # File Progress
                "progress": "Progress",
                "speed": "Speed",
                "eta": "ETA",
                "sending": "Sending...",
                "completed": "Completed",
                "failed": "Failed",
                "transfer_finished": "Transfer Finished",
            },
            "ko": {
                # App
                "app_title": "시리얼 툴",
                
                # Menu
                "file": "파일",
                "view": "보기",
                "help": "도움말",
                "new_port_tab": "새 포트 탭",
                "exit": "종료",
                "theme": "테마",
                "dark_theme": "다크 테마",
                "light_theme": "라이트 테마",
                "font": "폰트",
                "preferences": "환경설정",
                "about": "정보",
                
                # Status
                "ready": "준비",
                "connected": "연결됨",
                "disconnected": "연결 해제됨",
                "error": "오류",
                
                # Port Settings
                "port": "포트",
                "scan": "스캔",
                "baudrate": "보레이트",
                "data_bits": "데이터",
                "parity": "패리티",
                "stop_bits": "정지",
                "flow_control": "흐름",
                "open_port": "열기",
                "close_port": "닫기",
                
                # Manual Control
                "send": "전송",
                "hex_mode": "HEX",
                "add_enter": "Enter",
                "select_file": "파일 선택",
                "send_file": "파일 전송",
                
                # Received Area
                "rx_log": "수신 로그",
                "timestamp": "TS",
                "pause": "일시정지",
                "clear": "지우기",
                "save": "저장",
                "search": "검색 (정규식 지원)...",
                
                # Command List
                "select_all": "전체 선택",
                "prefix": "접두사",
                "command": "명령어",
                "suffix": "접미사",
                "delay": "지연",
                
                # Command Control
                "run": "실행",
                "run_all": "전체 실행",
                "auto_run": "자동 실행",
                "stop": "정지",
                "pause_cmd": "일시정지",
                "script": "스크립트",
                "load_script": "불러오기",
                "save_script": "저장",
                "interval": "간격 (ms)",
                "max_runs": "최대 실행",
                
                # Status Area
                "status_log": "상태 로그",
                
                # Preferences Dialog
                "general": "일반",
                "serial": "시리얼",
                "logging": "로그",
                "ui_appearance": "UI 외관",
                "language": "언어",
                "font_size": "폰트 크기",
                "default_parameters": "기본 매개변수",
                "default_baudrate": "기본 보레이트",
                "auto_scan_interval": "자동 스캔 간격",
                "file_logging": "파일 로깅",
                "log_directory": "로그 디렉토리",
                "max_log_lines": "최대 로그 라인 (UI)",
                "browse": "찾아보기...",
                "ok": "확인",
                "cancel": "취소",
                "apply": "적용",
                
                # About Dialog
                "about_title": "SerialTool 정보",
                "version": "버전",
                "copyright": "© 2025 SerialTool Team. All rights reserved.",
                "description": "SerialTool은 고성능 로깅 및 자동화를 위해\\n설계된 전문 시리얼 통신 유틸리티입니다.",
                "license": "MIT 라이선스로 배포됨",
                "close": "닫기",
                
                # File Progress
                "progress": "진행률",
                "speed": "속도",
                "eta": "예상 시간",
                "sending": "전송 중...",
                "completed": "완료",
                "failed": "실패",
                "transfer_finished": "전송 완료",
            }
        }

    def set_language(self, lang_code: str) -> None:
        """
        현재 언어를 설정합니다.
        
        Args:
            lang_code (str): 언어 코드 ('en', 'ko' 등)
        """
        if lang_code in self.resources and lang_code != self.current_language:
            self.current_language = lang_code
            self.language_changed.emit(lang_code)

    def get_text(self, key: str) -> str:
        """
        현재 언어에 해당하는 텍스트를 반환합니다.
        
        Args:
            key (str): 텍스트 키
            
        Returns:
            str: 번역된 텍스트. 키가 없으면 키 자체를 반환.
        """
        lang_dict = self.resources.get(self.current_language, {})
        return lang_dict.get(key, key)

# 전역 인스턴스
language_manager = LanguageManager()
