"""
포트 설정 첫 열 정렬 회귀 테스트 (S-075)

## WHY
사용자 보고 두 건이 같은 원인이었다.

* "포트 설정 프로토콜과 보드레이트 박스가, 프로토콜이 조금 앞에 있는 것을 좋아하지 않는다"
* "언어를 한글/영어로 전환할 때 UI 컴포넌트 위치가 변한다"

라벨이 제 글자 폭을 갖고 필드가 바로 뒤에 붙는데, 행마다 첫 라벨 길이가 달라
필드의 시작 x가 어긋났다. 언어를 바꾸면 라벨 길이가 통째로 달라져 같은 이유로
필드가 이동했다(네이티브 실측: 보드레이트 콤보 ko 86 → en 45, 41px 이동).

## WHAT
* 첫 열 라벨 폭이 서로 맞춰졌는가 (필드가 같은 선에서 시작하도록)
* 언어를 바꾸면 그 언어 기준으로 다시 맞춰지는가
* 보이지 않는 페이지의 라벨이 기준에 끼어들어 여백을 낭비하지 않는가

## HOW — 픽셀이 아니라 동작을 검사한다
처음에는 콤보의 x 좌표를 직접 비교하도록 썼다. 그런데 **정렬 코드를 통째로 지워도
테스트가 통과했다.** pytest 하네스(offscreen, 테마 미적용)의 폰트 메트릭이 네이티브와
달라 x 비교가 변별력을 잃은 것이다. 같은 함수를 독립 스크립트로 부르면 어긋남이
보이는데(ko 81 vs 98) pytest 안에서는 보이지 않았다.

그래서 픽셀 대신 **정렬이 실제로 수행됐는지**(첫 열 라벨 폭이 가장 넓은 라벨에 맞춰
같게 강제됐는지)를 본다. 이건 폰트와 무관하게 참/거짓이 갈린다. 픽셀 효과는 네이티브
실측으로 확인했고 그 수치를 테스트 docstring에 남겼다.
"""
import pytest
from PyQt5.QtWidgets import QApplication



def _make_widget(lang):
    """지정한 언어로 PortSettingsWidget을 새로 만든다 (언어를 먼저 정한다)."""
    from view.managers.language_manager import language_manager
    from view.widgets.port_settings import PortSettingsWidget

    language_manager.set_language(lang)
    widget = PortSettingsWidget()
    widget.show()
    widget.resize(800, 120)
    for _ in range(6):
        QApplication.processEvents()
    return widget


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_first_column_labels_are_width_matched(qapp, lang):
    """
    첫 열 라벨들의 폭이 서로 맞춰져야 한다 (필드가 같은 선에서 시작하도록).

    픽셀 x를 직접 비교하지 않는 이유: pytest 하네스(offscreen, 테마 미적용)에서는
    폰트 메트릭이 네이티브와 달라 x 비교가 변별력을 잃는다 — 정렬 코드를 통째로
    지워도 통과했다. 대신 **정렬이 실제로 수행됐는지**(라벨 폭이 같게 강제됐는지)를
    본다. 이건 폰트와 무관하게 참/거짓이 갈린다.

    네이티브 실측(2026-08-23)으로 확인한 효과:
        수정 전  ko 프로토콜 콤보 x=71 / 보드레이트 x=86   (15px 어긋남)
                 en 프로토콜 콤보 x=67 / 보드레이트 x=45   (22px 어긋남)
        수정 후  ko 둘 다 x=86 / en 둘 다 x=85            (정렬)
    """
    widget = _make_widget(lang)
    try:
        labels = widget._first_column_labels()
        assert len(labels) >= 2, "정렬 대상 라벨이 2개 미만이다 — 구조가 바뀌었는지 확인"

        widths = [lbl.minimumWidth() for lbl in labels]
        assert len(set(widths)) == 1, (
            f"[{lang}] 첫 열 라벨 폭이 서로 다르다: {widths} — "
            f"필드 시작 위치가 어긋난다. `_align_first_column_labels()` 확인."
        )
        assert widths[0] > 0, (
            f"[{lang}] 라벨 폭 하한이 0이다 — 정렬이 수행되지 않았다. "
            f"`_align_first_column_labels()`가 호출되는지 확인하라."
        )
        assert widths[0] == max(lbl.sizeHint().width() for lbl in labels), (
            f"[{lang}] 라벨 폭이 가장 넓은 라벨에 맞춰지지 않았다 — "
            f"짧은 쪽에 맞추면 긴 라벨이 잘린다."
        )
    finally:
        widget.close()
        QApplication.processEvents()


def test_language_switch_keeps_the_column_matched(qapp):
    """
    언어를 바꿔도 첫 열 폭이 **그 언어 기준으로** 다시 맞춰져야 한다.

    한 번만 계산하면 전환 후 옛 언어 기준 폭이 남아, 긴 번역이 잘리거나 짧은
    번역에서 빈 공간이 생긴다.
    """
    from view.managers.language_manager import language_manager
    from view.widgets.port_settings import PortSettingsWidget

    language_manager.set_language("ko")
    widget = PortSettingsWidget()
    widget.show()
    widget.resize(800, 120)
    for _ in range(6):
        QApplication.processEvents()

    try:
        language_manager.set_language("en")
        for _ in range(6):
            QApplication.processEvents()

        labels = widget._first_column_labels()
        widths = [lbl.minimumWidth() for lbl in labels]
        assert len(set(widths)) == 1, (
            f"언어 전환 후 첫 열 폭이 어긋났다: {widths}"
        )
        assert widths[0] == max(lbl.sizeHint().width() for lbl in labels), (
            "언어 전환 후 폭이 새 언어 기준으로 다시 계산되지 않았다 — "
            "`retranslate_ui`에서 `_align_first_column_labels()`를 부르는지 확인하라."
        )
    finally:
        widget.close()
        QApplication.processEvents()


def test_hidden_page_label_does_not_widen_the_visible_column(qapp):
    """
    보이지 않는 페이지(SPI)의 라벨이 정렬 기준에 끼어들면 안 된다.

    숨은 라벨이 더 넓으면 그 폭에 끌려가 **보이지도 않는 것 때문에 여백이 낭비된다**
    (실측: SPI 라벨이 가장 넓어 Serial 화면에서 ko 기준 ~50px 손해).
    """
    widget = _make_widget("ko")
    try:
        assert widget.settings_stack.currentIndex() == 0, "기본 페이지는 Serial이어야 한다"
        labels = widget._first_column_labels()
        spi_label = widget.spi_controls_ui.get("speed_lbl")
        assert spi_label is not None, "SPI 첫 라벨을 찾지 못했다 — 구조가 바뀌었는지 확인"
        assert spi_label not in labels, (
            "Serial 페이지가 보이는데 SPI 라벨이 정렬 기준에 포함돼 있다 — "
            "보이지 않는 라벨 폭만큼 여백이 낭비된다."
        )
    finally:
        widget.close()
        QApplication.processEvents()
