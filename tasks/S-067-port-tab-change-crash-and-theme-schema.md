# S-067 — 포트 탭 전환 시 AttributeError + 클래식 테마 저장 불가

- Status: DONE (2026-08-22 — 상위 모델이 사용자 보고를 받아 직접 조사·수정. 실행 로그의
  traceback으로 원인 특정, 실제 창으로 전후 확인. pytest 395 passed, ruff 0건)
- Recommended model: **상위 전용** (사용자 보고 대응 — 이미 완료, 기록용 문서)
- 선행: 없음 (S-060이 스키마 누락의 원인)
- Skills to load: task-done
- 근거: 사용자 보고 "포트 탭을 추가할 때마다 오류가 나는 이유는?" (2026-08-22)

## 목적 (Why)

사용자가 포트 탭을 추가할 때마다 오류가 난다고 보고했다. `logs/serial_tool_20260822.log`에
원인이 그대로 남아 있었다.

    presenter/manual_control_presenter.py:125, in set_enabled
      self.panel.set_enabled(enabled)
    AttributeError: 'ManualControlPanel' object has no attribute 'set_enabled'.
    Did you mean: 'setEnabled'?

패널의 실제 메서드는 `set_controls_enabled()`다. 탭 변경이
`_on_port_tab_changed` -> `_update_controls_state_for_current_tab` -> `set_enabled`
경로를 타므로 탭을 추가하거나 전환할 때마다 예외가 났다.

조사 중 **클래식 테마가 저장되지 않는 결함**도 드러났다. `core/settings_schema.py`의
theme enum이 `["dark", "light", "dracula"]`라 classic이 빠져 있었다(S-060이 테마·QSS·
메뉴는 만들었으나 스키마를 갱신하지 않음). 고를 수는 있는데 저장 시 검증에 걸려
폴백으로 되돌아가는 상태였다.

## 왜 393개 테스트가 못 잡았나 (핵심 교훈)

패널 Mock이 `spec` 없는 `MagicMock`이라 **존재하지 않는 메서드 이름도 조용히 통과**한다.
게다가 `set_enabled()`를 호출하는 테스트 자체가 없었다. 스키마 enum을 보는 테스트도
없었다. 프로젝트 전체에 `spec=`/`autospec` 사용이 **0건**이다.

## 수행 결과

- `manual_control_presenter.py`: `set_enabled` -> `set_controls_enabled` 교정.
- `settings_schema.py`: theme enum에 `"classic"` 추가.
- `tests/test_presenter_manual_control.py`: 패널 Mock에 `spec=ManualControlPanel` 지정 +
  `set_enabled()` 경로를 실제로 호출하는 테스트 추가. 결함을 되돌려
  `Mock object has no attribute 'set_enabled'`로 실패하는 것을 확인.
- `tests/test_theme_color_managers.py`: 스키마 enum과 `ThemeType`을 기계적으로 묶는
  테스트 추가. 결함을 되돌려 어느 테마가 빠졌는지 짚어 실패하는 것을 확인.
- 검증: 실제 창을 띄워(Mock 아님) 포트 탭 2개 -> 6개 추가 + 전 구간 전환에서 예외 0건.

## 남은 것

Mock `spec` 부재는 프로젝트 전역 문제다 -> S-070으로 분리.
