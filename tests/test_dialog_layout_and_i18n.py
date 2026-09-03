"""
서브 윈도우(다이얼로그) 레이아웃·다국어 회귀 테스트 (S-076)

## WHY
사용자 요청: "sub window(preference, font setting, ...)들도 열어서 언어팩 및 테마 점검."

열어 보니 두 가지가 나왔다.

1. **파일 전송 다이얼로그가 뭉개져 있었다.** `setFixedSize(450, 250)`인데 내용이
   요구하는 높이는 266px(offscreen 실측, 네이티브는 더 크다)라, 파일 선택 행과
   전송 버튼·진행률이 25px 남짓에 겹쳐 그려졌다. 4테마 x 2언어 전부에서 같았다.
2. **폰트 설정의 OK/Cancel/Apply가 한국어에서도 영문이었다.** `QDialogButtonBox`의
   표준 버튼은 Qt 기본 문구를 쓰는데, Preferences는 직접 번역해 넣고 있었고 폰트
   설정만 빠져 있었다.

## WHAT
* 다이얼로그가 **내용보다 작게 고정**돼 있지 않은가 (뭉개짐 방지)
* 표준 버튼(OK/Cancel/Apply)이 번역돼 있는가

## HOW
`offscreen`은 폰트가 없어 실제 픽셀이 네이티브보다 **작게** 나온다. 즉 여기서
"내용이 안 들어간다"고 나오면 네이티브에서는 더 심하다 — 보수적인 방향이라 검사로
쓸 수 있다. 반대로 여기서 통과한다고 네이티브가 안전하다는 뜻은 아니므로,
고정 크기 자체를 금지하는 쪽으로 검사한다.
"""
import pytest
from PyQt5.QtWidgets import QApplication, QDialogButtonBox

from common.dtos import PreferencesState
from view.managers.theme_manager import ThemeManager


def _dialogs(theme_manager):
    """점검 대상 다이얼로그 팩토리 목록."""
    from view.dialogs.about_dialog import AboutDialog
    from view.dialogs.file_transfer_dialog import FileTransferDialog
    from view.dialogs.font_settings_dialog import FontSettingsDialog
    from view.dialogs.preferences_dialog import PreferencesDialog

    return [
        ("preferences", lambda: PreferencesDialog(ThemeManager(), state=PreferencesState())),
        ("font_settings", lambda: FontSettingsDialog(theme_manager=theme_manager)),
        ("about", AboutDialog),
        ("file_transfer", FileTransferDialog),
    ]


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_dialogs_are_not_smaller_than_their_content(qapp, theme_manager, lang):
    """
    다이얼로그가 내용이 요구하는 크기보다 작게 잡혀 있으면 안 된다.

    작으면 위젯이 서로 겹쳐 그려진다 — 파일 전송 다이얼로그가 실제로 그랬다.
    """
    from view.managers.language_manager import language_manager

    language_manager.set_language(lang)
    problems = []

    for name, factory in _dialogs(theme_manager):
        dlg = factory()
        dlg.show()
        for _ in range(6):
            QApplication.processEvents()
        try:
            # **높이만** 본다. offscreen에는 시스템 폰트가 없어 텍스트 위젯
            # (미리보기 QTextEdit 등)의 폭 힌트가 비정상적으로 크게 나온다
            # (실측: font_settings 999px — 네이티브 캡처에서는 600px로 멀쩡하다).
            # 높이는 행 수로 결정되어 그런 왜곡이 없고, 실제 결함(파일 전송
            # 다이얼로그가 250px에 266px를 담으려 함)도 높이 쪽이었다.
            need = dlg.minimumSizeHint()
            if dlg.height() < need.height():
                problems.append(
                    f"{name}[{lang}]: 창 높이 {dlg.height()} < 최소 {need.height()}"
                )
        finally:
            dlg.close()
            QApplication.processEvents()

    assert not problems, (
        "내용보다 작은 다이얼로그 (위젯이 겹쳐 그려진다):\n  " + "\n  ".join(problems)
        + "\n\n`setFixedSize()` 대신 `resize()` + 최소 폭을 쓰면 레이아웃이 요구하는 "
        "크기 아래로 클램프되지 않는다 (ui_guide: 고정 크기로 인한 잘림 금지)."
    )


def test_dialogs_do_not_use_fixed_size(qapp, theme_manager):
    """
    다이얼로그에 고정 크기를 박지 않는다.

    번역 길이·폰트 크기·테마 여백이 달라지면 내용이 커지는데, 고정 크기는 그것을
    수용하지 못하고 겹쳐 그린다. 지금 당장 들어맞더라도 다음 번역에서 깨진다.
    """
    fixed = []
    for name, factory in _dialogs(theme_manager):
        dlg = factory()
        try:
            # 고정 크기는 최소 == 최대로 나타난다
            if (
                dlg.minimumWidth() == dlg.maximumWidth()
                and dlg.minimumHeight() == dlg.maximumHeight()
            ):
                fixed.append(f"{name}: {dlg.minimumWidth()}x{dlg.minimumHeight()}")
        finally:
            dlg.close()
            QApplication.processEvents()

    assert not fixed, (
        "고정 크기가 박힌 다이얼로그: " + ", ".join(fixed)
        + " — `resize()`로 초기 크기만 제안하고 최소 크기는 레이아웃에 맡겨라."
    )


@pytest.mark.parametrize("lang", ["ko", "en"])
def test_standard_dialog_buttons_are_translated(qapp, theme_manager, lang):
    """
    `QDialogButtonBox`의 표준 버튼이 언어팩을 거쳐야 한다.

    Qt 기본 문구를 그대로 두면 한국어 화면에 OK/Cancel/Apply가 영문으로 남는다.
    폰트 설정 다이얼로그가 실제로 그랬다(Preferences는 이미 번역하고 있었다).
    """
    from view.managers.language_manager import language_manager

    language_manager.set_language(lang)
    untranslated = []

    for name, factory in _dialogs(theme_manager):
        dlg = factory()
        dlg.show()
        for _ in range(6):
            QApplication.processEvents()
        try:
            for box in dlg.findChildren(QDialogButtonBox):
                for btn in box.buttons():
                    text = btn.text().replace("&", "")
                    if lang == "ko" and text in ("OK", "Cancel", "Apply", "Close"):
                        untranslated.append(f"{name}: '{text}'")
                    assert text, f"{name}[{lang}]: 빈 버튼 문구"
        finally:
            dlg.close()
            QApplication.processEvents()

    assert not untranslated, (
        "한국어 화면에 Qt 기본 영문 버튼이 남아 있다: " + ", ".join(untranslated)
        + " — `box.button(QDialogButtonBox.Ok).setText(language_manager.get_text(...))` "
        "형태로 직접 넣어라."
    )
