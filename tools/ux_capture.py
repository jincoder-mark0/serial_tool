"""
UX 스크린샷 캡처 도구 (테마 x 언어 x 창 크기 조합별 실행 화면 저장)

UI/UX 점검·완료 판정용 실측 도구입니다. offscreen 플랫폼은 폰트를 렌더하지
않아 텍스트 잘림·번역 노출을 잡지 못하므로, 네이티브 플랫폼에서 창을 잠깐
띄워 실제 렌더 결과를 PNG로 저장합니다 (RULES.md §7).

## WHY
* 코드 정독만으로는 실제 렌더 결함(잘림·대비·번역 누락)을 놓친다
* 테마 2 x 언어 2 x 창 크기 2 = 8조합을 사람 손 없이 반복 캡처

## WHAT
* main.py와 동일한 초기화 순서로 앱을 구성 (Settings -> Lang/Theme/Color -> MainWindow)
* 지정한 테마·언어를 적용해 기본(1400x900)·축소(1000x640) 크기로 grab() 저장
* minimumSizeHint를 함께 출력 (최소 창 크기 회귀 감시)

## HOW
* 1회 실행 = 1조합 (프로세스 격리로 싱글톤 매니저 상태 오염 방지)
* 사용: python tools/ux_capture.py --theme dark --lang ko --out <dir>
* 전체 조합: 테마(dark/light) x 언어(ko/en) 루프로 4회 호출
* 캡처 중 창이 1초 미만 잠깐 표시된다 (offscreen 사용 금지 — 폰트 미렌더)
"""
import argparse
import os
import sys
from pathlib import Path

# 네이티브 플랫폼 강제 (offscreen이 환경에 설정돼 있어도 해제)
os.environ.pop("QT_QPA_PLATFORM", None)

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.chdir(PROJECT)


def main() -> None:
    """조합 1건을 캡처한다."""
    ap = argparse.ArgumentParser(description="SerialTool UX 스크린샷 캡처")
    ap.add_argument("--theme", required=True, choices=["dark", "light"])
    ap.add_argument("--lang", required=True, choices=["ko", "en"])
    ap.add_argument("--out", required=True, help="PNG 저장 디렉터리")
    args = ap.parse_args()

    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt

    from core.resource_path import ResourcePath
    from core.logger import logger
    from core.settings_manager import SettingsManager
    from view.managers.theme_manager import ThemeManager
    from view.managers.language_manager import LanguageManager
    from view.managers.color_manager import ColorManager

    resource_path = ResourcePath()
    logger.configure(resource_path)
    SettingsManager(resource_path)
    language_manager = LanguageManager(resource_path)
    theme_manager = ThemeManager(resource_path)
    ColorManager(resource_path)

    language_manager.set_language(args.lang)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)

    theme_manager.apply_theme(args.theme)

    from view.main_window import MainWindow
    from presenter.main_presenter import MainPresenter

    window = MainWindow()
    presenter = MainPresenter(window)  # noqa: F841 - 상태바 등 실제 배선 포함 렌더
    window.show()

    os.makedirs(args.out, exist_ok=True)
    msh = window.minimumSizeHint()
    print(f"minimumSizeHint: {msh.width()}x{msh.height()}")
    for label, (w, h) in {"default": (1400, 900), "small": (1000, 640)}.items():
        window.resize(w, h)
        for _ in range(5):
            app.processEvents()
        pix = window.grab()
        path = os.path.join(args.out, f"main_{args.theme}_{args.lang}_{label}.png")
        pix.save(path)
        print(f"saved {path} ({pix.width()}x{pix.height()})")

    window.close()
    app.processEvents()


if __name__ == "__main__":
    main()
