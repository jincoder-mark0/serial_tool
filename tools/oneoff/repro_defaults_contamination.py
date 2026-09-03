"""사용자 설정 로드가 모듈 전역 기본값을 덮어쓰는지 실제 로드 경로로 확인한다.

언제: 2026-09-01, create_fallback_settings()의 얕은 복사 조사.
증명: 로드 1회로 DEFAULT_MANUAL_CONTROL_STATE가 변조되고, 손상 설정 복구가
      진짜 기본값이 아니라 직전 사용자 값('AT+USER_SECRET')을 되살린다.
실행: QT_QPA_PLATFORM=offscreen python tools/oneoff/repro_defaults_contamination.py
"""
import json
import sys
import tempfile
from pathlib import Path

# 승격 시 바꾼 유일한 줄 — 원본은 하드코딩 절대경로였다 (tools/oneoff/README.md).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common.defaults import (  # noqa: E402
    DEFAULT_MANUAL_CONTROL_STATE,
    create_fallback_settings,
)
from core.resource_path import ResourcePath  # noqa: E402
from core.settings_manager import SettingsManager  # noqa: E402

print("공유 여부(두 fallback이 같은 중첩 객체인가):",
      create_fallback_settings()["manual_control"]["manual_control_widget"]
      is create_fallback_settings()["manual_control"]["manual_control_widget"])

print("로드 전 기본값 input_text:",
      repr(DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]["input_text"]),
      "/ hex_mode:", DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]["hex_mode"])

tmp = Path(tempfile.mkdtemp())
rp = ResourcePath(tmp)
rp.config_dir.mkdir(parents=True, exist_ok=True)

user = create_fallback_settings()
user["manual_control"]["manual_control_widget"] = {
    **DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"],
    "input_text": "AT+USER_SECRET",
    "hex_mode": True,
}
rp.user_settings_file.write_text(json.dumps(user), encoding="utf-8")

SettingsManager(rp)   # 사용자 설정 로드 1회

print("로드 후 기본값 input_text:",
      repr(DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]["input_text"]),
      "/ hex_mode:", DEFAULT_MANUAL_CONTROL_STATE["manual_control_widget"]["hex_mode"])

fresh = create_fallback_settings()["manual_control"]["manual_control_widget"]
print("새 fallback이 돌려주는 값:", repr(fresh["input_text"]),
      "/ hex_mode:", fresh["hex_mode"])

tmp2 = Path(tempfile.mkdtemp())
rp2 = ResourcePath(tmp2)
rp2.config_dir.mkdir(parents=True, exist_ok=True)
rp2.user_settings_file.write_text("{ this is corrupted", encoding="utf-8")
sm2 = SettingsManager(rp2)
print("손상된 설정 -> fallback 복구 결과:",
      repr(sm2.settings["manual_control"]["manual_control_widget"]["input_text"]))
