"""레이아웃 제약을 즉시 재계산하는 세 전략을 같은 조건에서 비교한다.

언제: 2026-09-02, 우측 패널 토글 수정 방법 결정.
증명: A(splitter.updateGeometry + central/mainwindow invalidate+activate 사슬)만 동작.
      B(최소폭 일시 해제)는 실패하고, C(이벤트 루프 통과)는 동작하나 슬롯 안에서 쓸 수 없다.
실행: QT_QPA_PLATFORM=offscreen python tools/oneoff/probe_layout_invalidation_strategies.py
"""
import sys
from pathlib import Path

# 승격 시 바꾼 유일한 줄 — 원본은 하드코딩 절대경로였다 (tools/oneoff/README.md).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from view.main_window import MainWindow  # noqa: E402


def fresh():
    w = MainWindow()
    w.show()
    w.resize(1500, 800)
    w.right_section.setVisible(True)
    for _ in range(10):
        QApplication.processEvents()
    return w


def report(w, tag):
    for _ in range(10):
        QApplication.processEvents()
    print(f"  {tag:34} 창={w.width():5} 좌측={w.left_section.width():5} "
          f"우측={(w.right_section.width() if w.right_section.isVisible() else 0):5}")


def target_of(w):
    m = w.centralWidget().layout().contentsMargins()
    return w.left_section.width() + m.left() + m.right()


print("A) invalidate + activate 체인")
w = fresh()
report(w, "초기")
t = target_of(w)
w.right_section.setVisible(False)
w.splitter.updateGeometry()
w.centralWidget().layout().invalidate()
w.centralWidget().layout().activate()
w.layout().invalidate()
w.layout().activate()
w.resize(t, w.height())
report(w, f"숨김 (목표 {t})")
w.close()

print("B) 최소폭 일시 해제 후 resize")
w = fresh()
report(w, "초기")
t = target_of(w)
w.right_section.setVisible(False)
w.setMinimumWidth(0)
w.resize(t, w.height())
report(w, f"숨김 (목표 {t})")
w.close()

print("C) 레이아웃 정착 후 resize (이벤트 루프 통과)")
w = fresh()
report(w, "초기")
t = target_of(w)
w.right_section.setVisible(False)
for _ in range(10):
    QApplication.processEvents()
w.resize(t, w.height())
report(w, f"숨김 (목표 {t})")
w.close()
