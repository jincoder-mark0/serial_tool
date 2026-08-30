"""Selected Packet snapshot을 UI thread 밖에서 파일로 저장하는 export manager."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from common.packet_records import PacketRecord


class PacketExportError(ValueError):
    """지원하지 않는 export format 또는 invalid request."""


class _PacketExportWorker(QThread):
    completed = pyqtSignal(str, int)
    failed = pyqtSignal(str)

    def __init__(
        self,
        records: tuple[PacketRecord, ...],
        path: Path,
        export_format: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._records = records
        self._path = path
        self._export_format = export_format

    def run(self) -> None:
        try:
            PacketExportManager.write_records(
                self._records,
                self._path,
                self._export_format,
            )
            self.completed.emit(str(self._path), len(self._records))
        except Exception as exc:
            self.failed.emit(str(exc))


class PacketExportManager(QObject):
    """Packet export worker lifecycle owner."""

    export_completed = pyqtSignal(str, int)
    export_failed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workers: set[_PacketExportWorker] = set()

    def export_async(
        self,
        records: Iterable[PacketRecord],
        path: str,
        export_format: str,
    ) -> bool:
        snapshot = tuple(records)
        if not snapshot:
            self.export_failed.emit("No packets selected for export")
            return False

        target = Path(path)
        if not str(target):
            self.export_failed.emit("Export path must not be empty")
            return False

        normalized_format = export_format.strip().lower()
        if normalized_format not in {"csv", "json", "hex", "raw"}:
            self.export_failed.emit(f"Unsupported packet export format: {export_format}")
            return False

        worker = _PacketExportWorker(snapshot, target, normalized_format, self)
        self._workers.add(worker)
        worker.completed.connect(self.export_completed.emit)
        worker.failed.connect(self.export_failed.emit)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        worker.start()
        return True

    def _on_worker_finished(self, worker: _PacketExportWorker) -> None:
        self._workers.discard(worker)
        worker.deleteLater()

    def stop(self, timeout_ms: int = 1000) -> None:
        """Owned export workers가 종료할 시간을 bounded wait합니다."""
        workers = tuple(self._workers)
        for worker in workers:
            worker.requestInterruption()
        for worker in workers:
            worker.wait(timeout_ms)

    @property
    def has_pending_exports(self) -> bool:
        return any(worker.isRunning() for worker in self._workers)

    @staticmethod
    def write_records(
        records: Iterable[PacketRecord],
        path: Path,
        export_format: str,
    ) -> None:
        """Snapshot을 temporary file에 쓴 뒤 atomic replace합니다."""
        snapshot = tuple(records)
        if not snapshot:
            raise PacketExportError("No packets selected for export")

        export_format = export_format.strip().lower()
        if export_format not in {"csv", "json", "hex", "raw"}:
            raise PacketExportError(f"Unsupported packet export format: {export_format}")

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            if export_format == "csv":
                PacketExportManager._write_csv(snapshot, temp_path)
            elif export_format == "json":
                PacketExportManager._write_json(snapshot, temp_path)
            elif export_format == "hex":
                PacketExportManager._write_hex(snapshot, temp_path)
            else:
                PacketExportManager._write_raw(snapshot, temp_path)
            os.replace(temp_path, path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _checksum_text(value) -> str:
        if value is True:
            return "OK"
        if value is False:
            return "FAIL"
        return ""

    @staticmethod
    def _write_csv(records: tuple[PacketRecord, ...], path: Path) -> None:
        with open(path, "w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["time", "port", "type", "hex", "ascii", "checksum", "annotation"]
            )
            for record in records:
                writer.writerow(
                    [
                        record.time_str,
                        record.port,
                        record.packet_type,
                        record.data_hex,
                        record.data_ascii,
                        PacketExportManager._checksum_text(record.checksum_ok),
                        record.annotation,
                    ]
                )

    @staticmethod
    def _write_json(records: tuple[PacketRecord, ...], path: Path) -> None:
        payload = [
            {
                "packet_id": record.packet_id,
                "time": record.time_str,
                "port": record.port,
                "type": record.packet_type,
                "raw_hex": record.raw_data.hex().upper(),
                "ascii": record.data_ascii,
                "checksum": PacketExportManager._checksum_text(record.checksum_ok),
                "annotation": record.annotation,
            }
            for record in records
        ]
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    @staticmethod
    def _write_hex(records: tuple[PacketRecord, ...], path: Path) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            for record in records:
                prefix = f"{record.time_str}\t{record.port}\t{record.packet_type}\t"
                suffix = f"\t{record.annotation}" if record.annotation else ""
                file.write(f"{prefix}{record.data_hex}{suffix}\n")

    @staticmethod
    def _write_raw(records: tuple[PacketRecord, ...], path: Path) -> None:
        with open(path, "wb") as file:
            for record in records:
                file.write(record.raw_data)
