"""
패킷 인스펙터 위젯 모듈

수신된 패킷 데이터를 트리 형태로 시각화하여 보여줍니다.

## WHY
* 패킷 단위의 구조화된 데이터 표시 필요
* Raw 데이터와 메타데이터(타임스탬프, 타입 등) 구분 표시
* 사용자 편의 기능(자동 스크롤, 버퍼 제한) 제공

## WHAT
* QTreeWidget 기반 패킷 리스트 표시
* 패킷 추가, 초기화, 버퍼 관리 기능
* UI 업데이트 (View 역할)

## HOW
* QTreeWidget에 QTreeWidgetItem 추가
* MVP 준수를 위해 로직 없이 UI 조작 메서드만 제공
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem
from PyQt5.QtCore import Qt
from typing import Optional
from view.managers.language_manager import language_manager
from common.dtos import PacketViewData

class PacketWidget(QWidget):
    """
    패킷 구조를 트리 형태로 시각화하여 보여주는 위젯 클래스입니다.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        PacketInspector를 초기화합니다.

        Args:
            parent (Optional[QWidget]): 부모 위젯. 기본값은 None.
        """
        super().__init__(parent)
        self.tree = None
        self.title_lbl: Optional[QLabel] = None
        self.buffer_size = 100 # 기본 버퍼 크기
        self.auto_scroll = True
        self.init_ui()

        # 언어 변경 시 UI 업데이트 연결
        language_manager.language_changed.connect(self.retranslate_ui)

    def init_ui(self) -> None:
        """UI 컴포넌트 및 레이아웃을 초기화합니다."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(language_manager.get_text("packet_grp_title"))
        layout.addWidget(self.title_lbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            language_manager.get_text("packet_col_field"), # 예: Time, Type
            language_manager.get_text("packet_col_value")  # 예: Data
        ])
        self.tree.setColumnWidth(0, 150)
        self.tree.setRootIsDecorated(False)

        layout.addWidget(self.tree)
        self.setLayout(layout)

    def retranslate_ui(self) -> None:
        """언어 변경 시 UI 텍스트를 업데이트합니다."""
        self.title_lbl.setText(language_manager.get_text("packet_grp_title"))
        self.tree.setHeaderLabels([
            language_manager.get_text("packet_col_field"),
            language_manager.get_text("packet_col_value")
        ])

    def append_packet(self, data: PacketViewData) -> None:
        """
        패킷 데이터를 트리에 추가합니다.

        Logic:
            - 루트 아이템 생성 (시간, 타입 표시)
            - 자식 아이템 생성 (Hex 데이터, ASCII 데이터)
            - 버퍼 크기 제한 적용 (오래된 항목 삭제)
            - 자동 스크롤 처리

        Args:
            data (PacketViewData): 표시할 패킷 데이터 객체
        """
        # 루트 아이템 (요약 정보)
        root = QTreeWidgetItem(self.tree)
        root.setText(0, f"[{data.time_str}] {data.packet_type}")
        root.setText(1, data.data_ascii)

        # 상세 정보 (자식 아이템)
        child_hex = QTreeWidgetItem(root)
        child_hex.setText(0, "HEX")
        child_hex.setText(1, data.data_hex)

        child_ascii = QTreeWidgetItem(root)
        child_ascii.setText(0, "ASCII")
        child_ascii.setText(1, data.data_ascii)

        # 버퍼 관리
        if self.tree.topLevelItemCount() > self.buffer_size:
            # 가장 오래된 항목(0번 인덱스) 삭제
            self.tree.takeTopLevelItem(0)

        # 자동 스크롤
        if self.auto_scroll:
            self.tree.scrollToItem(root)

    def clear(self) -> None:
        """트리 내용을 모두 지웁니다."""
        self.tree.clear()

    def set_buffer_size(self, size: int) -> None:
        """
        버퍼 크기(최대 표시 패킷 수)를 설정합니다.

        Args:
            size (int): 최대 패킷 수
        """
        self.buffer_size = size

    def set_auto_scroll(self, enabled: bool) -> None:
        """
        자동 스크롤 여부를 설정합니다.

        Args:
            enabled (bool): True면 자동 스크롤 활성화
        """
        self.auto_scroll = enabled
