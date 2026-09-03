"""전체 테스트 스위트를 같은 프로세스에서 돌린 뒤 전역 기본값 오염을 검사한다.

언제: 2026-09-01, 기본값 오염이 테스트 격리까지 깨는지 확인.
증명: 스위트 1회 실행만으로 DEFAULT_MANUAL_CONTROL_STATE의
      prefix_enabled/suffix_enabled/broadcast_enabled가 False -> True로 바뀜.
실행: QT_QPA_PLATFORM=offscreen python tools/oneoff/check_defaults_leak_after_suite.py
"""
import copy
import sys
from pathlib import Path

# 승격 시 바꾼 유일한 줄 — 원본은 하드코딩 절대경로였다 (tools/oneoff/README.md).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from common import defaults  # noqa: E402

pristine = copy.deepcopy({
    "manual_control": defaults.DEFAULT_MANUAL_CONTROL_STATE,
    "macro_list": defaults.DEFAULT_MACRO_LIST_STATE,
    "packet": defaults.DEFAULT_PACKET_SETTINGS,
    "ports": defaults.DEFAULT_PORTS_STATE,
    "ui": defaults.DEFAULT_UI_SETTINGS,
    "settings": defaults.DEFAULT_SETTINGS_BLOCK,
})

pytest.main(["-q", "--no-header", "-p", "no:cacheprovider", "tests"])

after = {
    "manual_control": defaults.DEFAULT_MANUAL_CONTROL_STATE,
    "macro_list": defaults.DEFAULT_MACRO_LIST_STATE,
    "packet": defaults.DEFAULT_PACKET_SETTINGS,
    "ports": defaults.DEFAULT_PORTS_STATE,
    "ui": defaults.DEFAULT_UI_SETTINGS,
    "settings": defaults.DEFAULT_SETTINGS_BLOCK,
}
print("\n===== 테스트 실행 후 모듈 전역 기본값 오염 검사 =====")
dirty = False
for k in pristine:
    if pristine[k] != after[k]:
        dirty = True
        print(f"[오염] DEFAULT {k}")
        for kk in pristine[k]:
            if pristine[k][kk] != after[k][kk]:
                print(f"    {kk}: {pristine[k][kk]!r}  ->  {after[k][kk]!r}")
if not dirty:
    print("오염 없음")
