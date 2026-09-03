"""stop()이 get()과 state lock 사이에 도착하는 인터리빙을 고정 재현한다.

언제: 2026-09-01, S-084 수정 이후 남은 침묵 경로 조사 (S-085).
증명: 발급한 request 3건 중 1번이 완료도 실패도 없이 사라짐 (LOST request ids: [1]).
      큐에서 꺼낸 뒤라 `_fail_pending_transactions()`의 큐 드레인도 잡지 못한다.
실행: QT_QPA_PLATFORM=offscreen python tools/oneoff/repro_dequeued_transaction_loss.py
"""
import sys
import threading
import time
from pathlib import Path
from queue import Queue

# 승격 시 바꾼 유일한 줄 — 원본은 하드코딩 절대경로였다 (tools/oneoff/README.md).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt5.QtCore import QCoreApplication  # noqa: E402

from core.transport.transaction.control import TransactionOptions  # noqa: E402
from core.transport.transaction.dto import (  # noqa: E402
    SpiTransactionRequest,
    TransactionProtocol,
)
from model.transaction_session_worker import TransactionSessionWorker  # noqa: E402

app = QCoreApplication(sys.argv)


class Ctl:
    def transact(self, request, *, options=None, cancellation=None):
        return "ok"

    def close(self):
        pass


class Handle:
    def open_spi(self, cfg):
        return Ctl()

    def close(self):
        pass


class Registry:
    def resolve(self, i):
        return "desc"

    def open(self, i):
        return Handle()


class Cfg:
    name = "S1"
    protocol = TransactionProtocol.SPI
    spi = object()
    i2c = None
    adapter = "A"


class HookedQueue(Queue):
    """get()이 command를 반환한 직후 stop()이 도착하는 상황."""

    worker = None
    armed = False

    def get(self, *a, **kw):
        item = super().get(*a, **kw)
        if HookedQueue.armed:
            HookedQueue.armed = False
            HookedQueue.worker.stop()   # <- get 이후, state lock 획득 이전
        return item


w = TransactionSessionWorker(Registry(), Cfg())
w._commands = HookedQueue()
HookedQueue.worker = w

answered = []
w.transaction_failed.connect(lambda n, rid, e: answered.append(rid))
w.transaction_completed.connect(lambda n, rid, r: answered.append(rid))
opened = threading.Event()
w.session_opened.connect(lambda *a: opened.set())
w.start()
for _ in range(200):
    app.processEvents()
    if opened.is_set():
        break
    time.sleep(0.01)

req = SpiTransactionRequest(tx_data=b"\x01", rx_length=0)
HookedQueue.armed = True
issued = [rid for rid in (1, 2, 3)
          if w.enqueue_transaction(rid, req, TransactionOptions())]
print("issued:", issued)

w.wait(3000)
for _ in range(50):
    app.processEvents()
    time.sleep(0.01)

print("answered:", sorted(answered))
print("LOST request ids:", sorted(set(issued) - set(answered)))
