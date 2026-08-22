# S-021 — 하드코딩 사용자 메시지·라벨 언어팩 전환

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 신설 키 32개, 상태바·통계는
  값 캐시+refresh 헬퍼로 retranslate 연동. Presenter는 기존 main_presenter의
  language_manager 직접 import 패턴을 일관 적용. about 버전은 app_info 단일 원천화.
  check_language_keys SUCCESS, pytest 85 passed, ko 캡처에서 상태바·통계 한국어 확인)
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-020 권장 (언어팩 정리 후)
- Skills to load: task-done, lang-keys

## 목적 (Why)

상시 노출되는 상태바·통계 라벨과 실행 중 피드백(오류 다이얼로그·상태 메시지)이
언어팩을 완전히 우회해 언어 설정과 무관하게 항상 영어다
(근거: doc/ux_audit_20260822.md 높음 #6·#7).

## 수정 목록 (전수 — 각각 en/ko 키 신설 후 교체, lang-keys 절차)

**A. 상시 라벨 (retranslate 대상에 포함시킬 것)**
- `view/sections/main_status_bar.py:62-159` — "Port:", "RX:", "TX:", "BPS:" 등 f-string 접두 라벨.
- `view/widgets/port_stats.py:45-121` — "RX:", "TX:", "Errors:", "Uptime:", "Last RX:", "Buffer:" —
  `retranslate_ui()`가 그룹 제목만 갱신하므로 접두 라벨 갱신 로직 추가.

**B. 실행 중 메시지 (다이얼로그·상태 표시)**
- `presenter/lifecycle_manager.py:118-119` "Settings Reset" 계열
- `presenter/main_presenter.py:373` "Settings updated", `:502` "Macro Running...",
  `:507` "Macro Finished", `:596-597` "Macro Stopped:/Macro Error",
  `:609-617` "Completed"/"Failed"/"File Transfer..."
- `presenter/macro_presenter.py:167` "Success/Script saved successfully.",
  `:170` "Save Error", `:228` "Load Error"
- `presenter/port_presenter.py:362` "Error"/"Port Error (...)"
- `view/panels/macro_panel.py:284-287` "No Commands Selected"/"Please select..."
- `view/panels/port_tab_panel.py:140-141` QInputDialog "Edit Tab Name"/"Enter custom name:"
- `view/dialogs/preferences_dialog.py:212` QLabel("Default ResourcePath")

주의: Presenter는 View가 아니므로 LanguageManager 접근 방식을 기존 코드에서 먼저 확인한다 —
presenter가 이미 language_manager를 쓰는 곳이 있으면 그 패턴을 따르고, 없으면 **문자열을
View 계층으로 내려 View가 키를 해석**하게 한다 (MVP: Presenter가 키 이름을 전달하는 방식 허용).
판단이 갈리면 중단·보고.

**C. 부수**: `about_lbl_version` 값이 실제 `common/app_info.py:20 __version__`과 이중 관리 —
AboutDialog가 버전 숫자를 app_info에서 읽어 포맷하도록 (언어 키에는 "Version {0}" 형태만).

## Acceptance criteria (DoD)

- [ ] 위 목록 전부 언어 키 경유. ko 모드 캡처에서 상태바·통계 라벨이 한국어(또는 결정된 표기).
- [ ] check_language_keys·전체 pytest 통과.
- [ ] 언어 전환 시 상태바 라벨 즉시 갱신 (retranslate 경로 확인 보고).

## 검증 방법

```powershell
.venv\Scripts\python tools\check_language_keys.py
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
.venv\Scripts\python tools\ux_capture.py --theme dark --lang ko --out <스크래치패드>\after_s021   # 육안 확인
```
