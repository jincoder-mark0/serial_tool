"""UI 가독성 기계 감사 (다크/라이트 × 한글/영문 × 전 페이지).

눈으로 훑는 대신 실제 렌더 결과에서 결함을 검출한다:

- ``clipped``     : 텍스트가 위젯보다 커서 잘림 (글씨가 안 보임)
- ``overlap``     : 같은 부모의 형제 위젯 사각형이 겹침 (컴포넌트 겹침)
- ``outside``     : 자식이 부모 영역을 벗어남
- ``contrast``    : 화면 픽셀 기준 텍스트/배경 WCAG 대비비 미달 (색조합)
- ``margin``      : 페이지 최상위 레이아웃 여백 부족 (답답함)
- ``untranslated``: 영문 모드인데 한글 문자열이 그대로 (언어 누락)

사용:
    $env:PYTHONPATH="src"; .venv\\Scripts\\python tools/ui_audit.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# main()과 동일한 환경이어야 폰트 크기·잘림 판정이 실제와 일치한다
# (실측 2026-08-20: 이 설정 없이 보면 폰트가 커져 잘림을 과대/과소 평가한다)
os.environ.setdefault("QT_FONT_DPI", "96")
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

from board_provisioner.constants import (
    UI_DEFAULT_WINDOW_H,
    UI_DEFAULT_WINDOW_W,
    UI_MIN_CONTRAST_DISABLED,
    UI_MIN_WINDOW_H,
    UI_MIN_WINDOW_W,
)
from board_provisioner.ui.app import MainShell
from board_provisioner.ui.power_worker import _demo_supply_factory

# --------------------------------------------------------------------- 정책

#: WCAG AA 본문 기준. 굵거나 큰 글씨는 3.0으로 완화 판정한다.
MIN_CONTRAST = 4.5
MIN_CONTRAST_LARGE = 3.0
#: 페이지 최상위 레이아웃의 최소 여백(px)
MIN_PAGE_MARGIN = 12
#: 잘림 판정 허용 오차(px) - 폰트 렌더 반올림으로 1~2px는 잘리지 않는다
CLIP_TOLERANCE = 3
#: 대비 계산에서 무시할 미세 픽셀 비율 (안티에일리어싱 가장자리)
MIN_COLOR_SHARE = 0.005

_HANGUL = re.compile(r"[가-힣]")

#: 의도적으로 겹쳐 그리는 오버레이 (차트 위 배지 등) - 겹침 검사 제외
OVERLAP_EXEMPT_OBJECTS = {"recBadge", "chartOverlay"}
#: 커스텀 페인팅 위젯 - 내부 텍스트를 자체 팔레트로 그린다 (별도 규칙)
CUSTOM_PAINT_CLASSES = {"TrendChart", "StepIndicator", "NoWrapDial", "QDial"}


def _relative_luminance(rgb):
    channels = []
    for value in rgb:
        c = value / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _color_distance(a, b) -> int:
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def sample_text_contrast(image, rect: QRect, inset: int = 0):
    """렌더된 영역에서 (배경, 글자) 색을 추정해 대비비를 계산한다.

    inset: 테두리/둥근 모서리 픽셀을 글자로 오인하지 않도록 안쪽으로 줄일 폭.
    """
    if inset:
        rect = rect.adjusted(inset, inset, -inset, -inset)
    rect = rect.intersected(QRect(0, 0, image.width(), image.height()))
    if rect.width() < 4 or rect.height() < 4:
        return None
    counter: Counter = Counter()
    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            pixel = image.pixelColor(x, y)
            counter[(pixel.red(), pixel.green(), pixel.blue())] += 1
    if not counter:
        return None
    total = sum(counter.values())
    background = counter.most_common(1)[0][0]
    candidates = [
        color
        for color, count in counter.items()
        if count / total >= MIN_COLOR_SHARE and _color_distance(color, background) > 40
    ]
    if not candidates:
        return None
    # 글자색 = 배경과 **명도 차이**가 가장 큰 색. 색상 거리로 고르면 서브픽셀
    # 안티에일리어싱이 만든 색 프린지(획 가장자리의 파랑/주황)를 글자로
    # 오인한다 (감사 2026-08-20: "테마" 라벨에서 실측 확인)
    bg_luminance = _relative_luminance(background)
    foreground = max(
        candidates, key=lambda color: abs(_relative_luminance(color) - bg_luminance)
    )
    return contrast_ratio(background, foreground), _hex(background), _hex(foreground)


def _hex(color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _text_of(widget: QWidget) -> str:
    if isinstance(widget, QLabel | QAbstractButton):
        return widget.text()
    if isinstance(widget, QLineEdit):
        return widget.text() or widget.placeholderText()
    if isinstance(widget, QComboBox):
        return widget.currentText()
    return ""


def _is_large_text(widget: QWidget) -> bool:
    font = widget.font()
    size_px = font.pointSizeF() * 96 / 72 if font.pointSizeF() > 0 else font.pixelSize()
    return size_px >= 24 or (size_px >= 18.7 and font.bold())


def _class_chain(widget: QWidget) -> set:
    names = set()
    klass = type(widget)
    while klass is not object:
        names.add(klass.__name__)
        klass = klass.__bases__[0] if klass.__bases__ else object
    return names


def _describe(widget: QWidget) -> str:
    name = widget.objectName() or type(widget).__name__
    text = _text_of(widget).strip().replace("\n", " ")
    return f"{name}({text[:38]})" if text else name


def _effective_margin_layout(page: QWidget):
    """여백을 판정할 레이아웃. 자식 하나에 위임하는 래퍼 페이지는 그 자식을 본다."""
    layout = page.layout()
    for _ in range(4):  # 페이지 -> 패널 -> 스크롤 내용 (몇 단계든 위임 추적)
        if layout is None:
            return None
        widget_children = [
            layout.itemAt(i).widget() for i in range(layout.count())
            if layout.itemAt(i).widget() is not None
        ]
        margins = layout.contentsMargins()
        outer = max(margins.left(), margins.top(), margins.right(), margins.bottom())
        if len(widget_children) != 1 or outer != 0:
            return layout
        child = widget_children[0]
        if isinstance(child, QScrollArea) and child.widget() is not None:
            child = child.widget()
        if child.layout() is None:
            return layout
        layout = child.layout()
    return layout


def _settle(app, milliseconds: int = 400) -> None:
    """애니메이션·레이아웃이 끝날 때까지 이벤트를 돌린다 (sleep 아님)."""
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < milliseconds:
        app.processEvents()


def audit_page(shell, page: QWidget, page_name: str, theme: str, lang: str,
               size_label: str = "", *, check_contrast: bool = True):
    findings: list = []
    app = QApplication.instance()
    shell.ui.stackedWidget.setCurrentWidget(page)
    # 템플릿이 좌측 패널을 애니메이션으로 여닫는다 - 진행 중에 캡처하면
    # 위젯 좌표와 그려진 픽셀이 어긋나 엉뚱한 색을 읽는다 (감사 2026-08-20)
    _settle(app)
    # 대기 중인 레이아웃 요청을 확정한다 - 크기 변경 직후에는 위젯 좌표가
    # 아직 갱신 전일 수 있어 없는 겹침이 보고된다
    app.sendPostedEvents()
    if page.layout() is not None:
        page.layout().activate()
    shell.repaint()
    app.processEvents()
    pixmap = shell.grab()
    dpr = pixmap.devicePixelRatio() or 1.0
    image = pixmap.toImage()

    def add(kind: str, widget: QWidget, detail: str, severity: str = "high") -> None:
        findings.append(
            {
                "theme": theme, "lang": lang, "size": size_label,
                "page": page_name, "kind": kind, "severity": severity,
                "widget": _describe(widget), "detail": detail,
            }
        )

    # 가로 스크롤을 끈 스크롤 영역은 내용이 넓으면 그대로 잘린다 (§3·§4)
    for area in page.findChildren(QScrollArea):
        content = area.widget()
        if content is None:
            continue
        if area.horizontalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff:
            continue
        needed = content.minimumSizeHint().width()
        available = area.viewport().width()
        if needed > available + CLIP_TOLERANCE:
            add(
                "hclip", area,
                f"content needs {needed}px wide, viewport {available}px "
                "(가로 스크롤 없음 - 내용이 잘린다)",
            )

    layout = _effective_margin_layout(page)
    if layout is not None:
        m = layout.contentsMargins()
        smallest = min(m.left(), m.top(), m.right(), m.bottom())
        if smallest < MIN_PAGE_MARGIN:
            add(
                "margin", page,
                f"page layout margins=({m.left()},{m.top()},{m.right()},{m.bottom()})"
                f" < {MIN_PAGE_MARGIN}", "medium",
            )

    for widget in page.findChildren(QWidget):
        if not widget.isVisible() or widget.width() <= 0 or widget.height() <= 0:
            continue
        if _class_chain(widget) & CUSTOM_PAINT_CLASSES:
            continue
        text = _text_of(widget)

        if text and isinstance(widget, QLabel | QAbstractButton):
            wrapped = isinstance(widget, QLabel) and widget.wordWrap()
            # ElidedLabel = 말줄임 + 툴팁 (규칙이 허용한 해법) - 잘림 아님
            elided = type(widget).__name__ == "ElidedLabel"
            if not wrapped and not elided:
                # 가로: QLabel은 넘치면 그대로 잘린다 -> sizeHint 기준.
                # 버튼/체크박스는 스타일 여백이 커서 글자폭+최소여백으로 본다.
                # 세로: 버튼은 여백이 줄어들 뿐 글자는 남으므로 검사하지 않고,
                # 라벨만 sizeHint 높이로 본다. (오차 허용 TOLERANCE)
                metrics = QFontMetrics(widget.font())
                if isinstance(widget, QAbstractButton):
                    extra = 24 if isinstance(widget, QCheckBox) else 12
                    needed_w = metrics.horizontalAdvance(text) + extra
                    needed_h = None
                else:
                    needed_w = widget.sizeHint().width()
                    needed_h = widget.sizeHint().height()
                if needed_w > widget.width() + CLIP_TOLERANCE:
                    add("clipped", widget, f"needs {needed_w}px, has {widget.width()}px")
                if needed_h is not None and needed_h > widget.height() + CLIP_TOLERANCE:
                    add(
                        "clipped", widget,
                        f"needs {needed_h}px tall, has {widget.height()}px",
                    )

        parent = widget.parentWidget()
        if (
            parent is not None
            and parent is not page
            and parent.objectName() != "qt_scrollarea_viewport"
        ):
            if not parent.rect().contains(widget.geometry()):
                if widget.objectName() not in OVERLAP_EXEMPT_OBJECTS:
                    add(
                        "outside", widget,
                        f"geometry {widget.geometry().getRect()} outside "
                        f"parent {_describe(parent)} {parent.rect().getRect()}",
                    )

        language_picker = widget.objectName() == "languageCombo"
        if lang == "en" and text and not language_picker and _HANGUL.search(text):
            add("untranslated", widget, f"text={text[:40]!r}", "medium")

        visible = widget.visibleRegion().boundingRect()
        fully_visible = visible.size() == widget.size()
        if (
            check_contrast and text.strip() and fully_visible
            and isinstance(widget, QLabel | QAbstractButton)
        ):
            top_left = widget.mapTo(shell, QPoint(0, 0))
            # 화면 배율(devicePixelRatio) 보정 - logical 좌표를 device px로
            device_rect = QRect(
                int(top_left.x() * dpr), int(top_left.y() * dpr),
                int(widget.width() * dpr), int(widget.height() * dpr),
            )
            # 버튼/입력은 테두리·모서리를 제외하고 내부만 본다 (오탐 방지)
            inset = int(4 * dpr) if isinstance(widget, QAbstractButton) else 0
            sampled = sample_text_contrast(image, device_rect, inset)
            if sampled is not None:
                ratio, bg, fg = sampled
                if not widget.isEnabled():
                    floor = UI_MIN_CONTRAST_DISABLED
                elif _is_large_text(widget):
                    floor = MIN_CONTRAST_LARGE
                else:
                    floor = MIN_CONTRAST
                if ratio < floor:
                    add(
                        "contrast", widget,
                        f"ratio={ratio:.2f} (min {floor}) bg={bg} fg={fg}",
                        "high" if ratio < 3.0 else "medium",
                    )

    for container in [page, *page.findChildren(QWidget)]:
        kids = [
            w for w in container.children()
            if isinstance(w, QWidget) and w.isVisible()
            and w.width() > 0 and w.height() > 0
            and w.objectName() not in OVERLAP_EXEMPT_OBJECTS
            and not (_class_chain(w) & CUSTOM_PAINT_CLASSES)
        ]
        for i, first in enumerate(kids):
            for second in kids[i + 1:]:
                overlap = first.geometry().intersected(second.geometry())
                if overlap.width() > 2 and overlap.height() > 2:
                    findings.append({
                        "theme": theme, "lang": lang, "size": size_label,
                        "page": page_name, "kind": "overlap", "severity": "high",
                        "widget": f"{_describe(first)} + {_describe(second)}",
                        "detail": f"overlap {overlap.getRect()}",
                    })
    return findings


PAGES = [
    ("provisioning_serial", "page_provisioning_serial"),
    ("provisioning_prepare", "page_provisioning_prepare"),
    ("provisioning_progress", "page_provisioning_progress"),
    ("prepare_history", "page_prepare_history"),
    ("history", "page_history"),
    ("board_monitor", "page_board_monitor"),
    ("board_temp", "page_board_temp"),
    ("board_vi", "page_board_vi"),
    ("power_general", "page_power_general"),
    ("power_logging", "page_power_logging"),
    ("power_sequential", "page_power_sequential"),
    ("settings_general", "page_settings_general"),
    ("settings_provisioning", "page_settings_provisioning"),
]


#: 감사 창 크기 = 실사용 크기. 임의 크기로 보면 세로 압축을 과소평가한다
#: (실측 사고 2026-08-20: 820으로 봐서 720 기본 크기의 잘림을 놓쳤다)
AUDIT_SIZES = (
    ("default", UI_DEFAULT_WINDOW_W, UI_DEFAULT_WINDOW_H),
    ("min", UI_MIN_WINDOW_W, UI_MIN_WINDOW_H),
)


def _page_variants(page: QWidget):
    """페이지가 보여줄 수 있는 화면들 ``(index, 이름 접미사)``.

    페이지가 QStackedWidget을 품고 있으면 각 장을 차례로 띄운다 (감사 후
    원래 장으로 되돌린다). 없으면 현재 화면 한 장만 본다.
    """
    stacks = page.findChildren(QStackedWidget)
    if not stacks:
        yield 0, ""
        return
    stack = stacks[0]
    original = stack.currentIndex()
    try:
        for index in range(stack.count()):
            stack.setCurrentIndex(index)
            yield index, f"_step{index + 1}"
    finally:
        stack.setCurrentIndex(original)


def run_audit(shell, shots_dir: Path | None = None, sizes=AUDIT_SIZES,
              languages=("ko", "en"), themes=("dark", "light"),
              check_contrast: bool = True):
    """전 조합 감사 실행 - 결과 findings 리스트 반환 (테스트에서도 호출)."""
    app = QApplication.instance()
    findings: list = []
    settings = shell._ui_settings
    # 감사는 언어·테마를 갈아 끼우며 돈다 - 끝나면 원래 설정으로 되돌린다.
    # (전역 i18n 상태를 바꾼 채 두면 다음 테스트가 영문 문구를 보게 된다)
    original = (settings.language, settings.theme)
    for size_label, width, height in sizes:
      shell.resize(width, height)
      _settle(app)
      for lang in languages:
        for theme in themes:
            # 실사용 경로와 동일하게 적용한다 (셸 QSS + 페이지 팔레트 + 번역).
            # 페이지 팔레트만 바꾸면 셸 배경이 그대로라 실제와 다른 화면이 된다.
            shell._on_settings_apply(
                lang, theme, settings.font_family, settings.font_size_pt
            )
            _settle(app)
            for page_name, attr in PAGES:
                page = getattr(shell, attr)
                # 스텝형 페이지(QStackedWidget)는 화면이 여러 장이다 - 보이는
                # 한 장만 보면 나머지 스텝의 겹침·잘림을 놓친다 (준비 4스텝)
                for _index, label in _page_variants(page):
                    name = f"{page_name}{label}"
                    findings += audit_page(
                        shell, page, name, theme, lang, size_label,
                        check_contrast=check_contrast,
                    )
                    if shots_dir is not None:
                        shots_dir.mkdir(parents=True, exist_ok=True)
                        shell.grab().save(
                            str(shots_dir / f"{size_label}_{theme}_{lang}_{name}.png")
                        )
    shell._on_settings_apply(
        original[0], original[1], settings.font_family, settings.font_size_pt
    )
    _settle(app)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="UI 가독성 기계 감사")
    parser.add_argument("--json", default="", help="결과 JSON 저장 경로")
    parser.add_argument("--shots", default="", help="페이지 캡처 저장 폴더")
    parser.add_argument("--data-dir", default="", help="격리 data_dir")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    data_dir = Path(args.data_dir) if args.data_dir else Path("data/ui_audit")
    shell = MainShell(_demo_supply_factory, port_label="(demo)", data_dir=data_dir)
    shell.resize(UI_DEFAULT_WINDOW_W, UI_DEFAULT_WINDOW_H)
    shell.show()
    app.processEvents()

    all_findings = run_audit(shell, Path(args.shots) if args.shots else None)

    by_kind = Counter(f["kind"] for f in all_findings)
    print("=== 요약 ===")
    for kind, count in by_kind.most_common():
        print(f"{kind:14s} {count}")
    print(f"{'TOTAL':14s} {len(all_findings)}")

    print("\n=== 상세 (kind/page/widget별 대표) ===")
    seen: Counter = Counter()
    for f in all_findings:
        key = (f["kind"], f["page"], f["widget"], f.get("size", ""))
        seen[key] += 1
        if seen[key] == 1:
            print(
                f"[{f['kind']}/{f['severity']}] {f.get('size','')}/{f['theme']}"
                f"/{f['lang']} {f['page']} :: {f['widget']} :: {f['detail']}"
            )

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(all_findings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON -> {args.json}")

    shell.page_power_general.shutdown()
    shell.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
