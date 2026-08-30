"""
파일 전송 Presenter.

FileTransferDialog와 FileTransferManager를 연결합니다. 전송 엔진 생성/스케줄링,
포트 검증, 속도/ETA 계산은 Model/Application manager가 소유합니다.
"""
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import FileCompletionEvent, FileErrorEvent, FileProgressState
from model.file_transfer_manager import FileTransferManager
from view.dialogs.file_transfer_dialog import FileTransferDialog


class FilePresenter(QObject):
    """파일 전송 dialog의 사용자 입력과 manager 상태를 중재합니다."""

    transfer_completed = pyqtSignal(object)
    transfer_error = pyqtSignal(object)

    def __init__(self, transfer_manager: FileTransferManager) -> None:
        super().__init__()
        self.transfer_manager = transfer_manager
        self.file_transfer_dialog: Optional[FileTransferDialog] = None
        self.target_port: Optional[str] = None

        self.transfer_manager.progress_updated.connect(self._on_progress)
        self.transfer_manager.transfer_completed.connect(self._on_completed)
        self.transfer_manager.error_occurred.connect(self._on_error)

    def on_file_transfer_dialog_opened(
        self,
        dialog: FileTransferDialog,
        target_port: str,
    ) -> None:
        """열린 dialog를 현재 View context로 등록하고 사용자 요청을 연결합니다."""
        self.file_transfer_dialog = dialog
        self.target_port = target_port

        dialog.send_requested.connect(self.start_transfer)
        dialog.cancel_requested.connect(self.cancel_transfer)
        dialog.finished.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        """Dialog 참조만 정리합니다. 진행 중 전송 생명주기는 manager가 유지합니다."""
        self.file_transfer_dialog = None
        self.target_port = None

    def start_transfer(self, file_path: str) -> None:
        """현재 dialog의 target port를 manager에 전달합니다."""
        self.transfer_manager.start_transfer(
            file_path,
            self.target_port or "",
        )

    def cancel_transfer(self) -> None:
        """활성 전송 취소를 manager에 위임합니다."""
        self.transfer_manager.cancel_transfer()

    def _on_progress(self, state: FileProgressState) -> None:
        """manager가 계산한 progress DTO를 현재 dialog에 표시합니다."""
        if self.file_transfer_dialog:
            self.file_transfer_dialog.update_progress(state)

    def _on_completed(self, event: FileCompletionEvent) -> None:
        """완료 상태를 dialog에 반영하고 상위 조정자에 재발행합니다."""
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(event.success, event.message)
        self.transfer_completed.emit(event)

    def _on_error(self, event: FileErrorEvent) -> None:
        """오류 상태를 dialog에 반영하고 상위 조정자에 재발행합니다."""
        if self.file_transfer_dialog:
            self.file_transfer_dialog.set_complete(False, event.message)
        self.transfer_error.emit(event)
