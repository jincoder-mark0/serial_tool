"""Selected Packet snapshot을 UI thread 밖에서 파일로 저장하는 export manager."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Callable, Iterable, Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from common.packet_records import PacketRecord
from core.logger import logger


class PacketExportError(ValueError):
    """지원하지 않는 export format 또는 invalid request."""


class PacketExportAborted(RuntimeError):
    """종료 요청으로 export가 완료 전에 중단됐다.

    조용히 사라지지 않도록 별도 예외로 둔다 — 사용자는 export를 요청했는데
    파일이 없는 이유를 알아야 한다.
    """


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
            written = PacketExportManager.write_records(
                self._records,
                self._path,
                self._export_format,
                # 종료 요청을 record 단위로 확인한다. 이것이 없으면
                # `requestInterruption()`은 아무 일도 하지 않는다.
                should_abort=self.isInterruptionRequested,
            )
            self.completed.emit(str(self._path), written)
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

        # 빈 경로는 Path로 감싸기 **전에** 본다.
        # `Path("")`는 `.`이 되어 `str()`이 항상 비어 있지 않으므로, 과거의
        # `if not str(target)` 가드는 한 번도 걸리지 않았다. 그 결과 빈 경로는
        # 이 메시지 대신 worker 안에서 `ValueError: WindowsPath('.') has an
        # empty name`으로 터졌다.
        if not path or not path.strip():
            self.export_failed.emit("Export path must not be empty")
            return False

        target = Path(path)

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

    def stop(self, timeout_ms: int = 1000) -> bool:
        """Owned export workers가 종료할 시간을 bounded wait합니다.

        Returns:
            bool: 모든 worker가 상한 안에 종료됐으면 True.

        Note:
            과거에는 `None`을 돌려주고 상한을 넘겨도 아무것도 알리지 않았다.
            종료 중 export가 끝나지 않으면 사용자는 요청한 파일이 없는 이유를
            알 수 없었다. 형제 매니저(`PortScanManager`/`MacroScriptManager`)와
            같은 계약(bool 반환 + 경고)으로 맞춘다.
        """
        workers = tuple(self._workers)
        for worker in workers:
            worker.requestInterruption()

        all_finished = True
        for worker in workers:
            if not worker.wait(timeout_ms):
                logger.warning(
                    f"Packet export did not finish within {timeout_ms} ms; "
                    f"the target file was not written."
                )
                all_finished = False

        return all_finished

    @property
    def has_pending_exports(self) -> bool:
        return any(worker.isRunning() for worker in self._workers)

    @staticmethod
    def write_records(
        records: Iterable[PacketRecord],
        path: Path,
        export_format: str,
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> int:
        """Snapshot을 temporary file에 쓴 뒤 atomic replace합니다.

        Args:
            should_abort: record 사이마다 확인하는 중단 조건. True를 돌려주면
                `PacketExportAborted`를 올린다. None이면 끝까지 쓴다.

        Returns:
            int: 실제로 기록한 record 수.

        Raises:
            PacketExportAborted: `should_abort`가 중단을 요청한 경우. 이때 대상
                파일은 **교체되지 않고** temporary file만 지워진다 — 부분 결과가
                완성본으로 남지 않는다.
        """
        snapshot = tuple(records)
        if not snapshot:
            raise PacketExportError("No packets selected for export")

        export_format = export_format.strip().lower()
        if export_format not in {"csv", "json", "hex", "raw"}:
            raise PacketExportError(f"Unsupported packet export format: {export_format}")

        writers = {
            "csv": PacketExportManager._write_csv,
            "json": PacketExportManager._write_json,
            "hex": PacketExportManager._write_hex,
            "raw": PacketExportManager._write_raw,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            written = writers[export_format](snapshot, temp_path, should_abort)
            os.replace(temp_path, path)
            return written
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _iter_records(
        records: tuple[PacketRecord, ...],
        should_abort: Optional[Callable[[], bool]],
    ):
        """중단 요청을 record 단위로 확인하며 순회합니다.

        단일 blocking write로 두면 `requestInterruption()`이 아무 일도 하지
        않는다 — 종료 시 export가 조용히 사라지는 원인이었다.
        """
        total = len(records)
        for index, record in enumerate(records):
            if should_abort is not None and should_abort():
                raise PacketExportAborted(
                    f"Packet export aborted before completion: "
                    f"{index} of {total} packet(s) written"
                )
            yield record

    @staticmethod
    def _checksum_text(value) -> str:
        if value is True:
            return "OK"
        if value is False:
            return "FAIL"
        return ""

    @staticmethod
    def _write_csv(
        records: tuple[PacketRecord, ...],
        path: Path,
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> int:
        written = 0
        with open(path, "w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                ["time", "port", "type", "hex", "ascii", "checksum", "annotation"]
            )
            for record in PacketExportManager._iter_records(records, should_abort):
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
                written += 1
        return written

    @staticmethod
    def _write_json(
        records: tuple[PacketRecord, ...],
        path: Path,
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> int:
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
            for record in PacketExportManager._iter_records(records, should_abort)
        ]
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)
        return len(payload)

    @staticmethod
    def _write_hex(
        records: tuple[PacketRecord, ...],
        path: Path,
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> int:
        written = 0
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            for record in PacketExportManager._iter_records(records, should_abort):
                prefix = f"{record.time_str}\t{record.port}\t{record.packet_type}\t"
                suffix = f"\t{record.annotation}" if record.annotation else ""
                file.write(f"{prefix}{record.data_hex}{suffix}\n")
                written += 1
        return written

    @staticmethod
    def _write_raw(
        records: tuple[PacketRecord, ...],
        path: Path,
        should_abort: Optional[Callable[[], bool]] = None,
    ) -> int:
        written = 0
        with open(path, "wb") as file:
            for record in PacketExportManager._iter_records(records, should_abort):
                file.write(record.raw_data)
                written += 1
        return written
