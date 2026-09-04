"""우측 패널 토글 시 창/좌측/우측 폭과 레이아웃 최소 크기를 실측한다.

언제: 2026-09-02, 사용자 보고 "창 크기가 변해야 하는데 컴포넌트 크기가 변한다" 조사.
증명: 숨김 시 창 폭이 3838로 유지되고 좌측이 3244 -> 3828로 늘어남. 창 최소 폭이
      setVisible(False) 직후에도 3838이라 resize가 클램프되는 것이 원인.
실행: QT_QPA_PLATFORM=offscreen python tools/oneoff/probe_right_panel_geometry.py
"""
import sys
from pathlib import Path

# 승격 시 바꾼 유일한 줄 — 원본은 하드코딩 절대경로였다 (tools/oneoff/README.md).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
from view.main_window import MainWindow  # noqa: E402
from view.managers.color_manager import ColorManager  # noqa: E402
from view.managers.theme_manager import ThemeManager  # noqa: E402

w = MainWindow(ThemeManager(), ColorManager())
w.show()
w.resize(1500, 800)
w.right_section.setVisible(True)
for _ in range(10):
    QApplication.processEvents()


def snap(tag):
    for _ in range(10):
        QApplication.processEvents()
    print(f"{tag:12} 창={w.width():5}  좌측={w.left_section.width():5}  "
          f"우측={(w.right_section.width() if w.right_section.isVisible() else 0):5}  "
          f"창최소={w.minimumSizeHint().width():5}  "
          f"중앙최소={w.centralWidget().layout().minimumSize().width():5}")


snap("초기")
w.toggle_right_section(False)
snap("숨김")
w.toggle_right_section(True)
snap("표시")
print()
print("우측섹션 minimumWidth:", w.right_section.minimumWidth())
print("좌측섹션 minimumWidth:", w.left_section.minimumWidth(),
      " minimumSizeHint:", w.left_section.minimumSizeHint().width())
