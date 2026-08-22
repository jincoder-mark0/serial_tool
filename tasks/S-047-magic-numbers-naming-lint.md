# S-047 — [P3] 매직 넘버 상수화 + 명명 규칙 정리 + lint 도입

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (S-049와는 파일이 겹치므로 **S-049보다 먼저** 수행)
- Skills to load: task-done, lang-keys
- 근거: `doc/refactor_audit_20260822.md` D

## 목적 (Why)

프로젝트는 `common/constants.py`로 상수를 잘 관리하는 편인데 일부가 누락됐고, 명명 규칙에
어긋난 이름이 타입을 오도하며, lint 설정이 아예 없어 dead code·미사용 import가 쌓인다.

## Steps

### 1. 매직 넘버 상수화 (`common/constants.py`에 추가 후 치환)

- `view/custom_qt/smart_list_view.py` 필터 디바운스 `300`ms
- `presenter/lifecycle_manager.py` 상태바 갱신 타이머 `1000`ms
  (`DEFAULT_MACRO_INTERVAL_MS`와 값만 같고 의미가 다르므로 **재사용하지 말고 새 상수**)
- `model/file_transfer_service.py` backpressure 대기 `0.01`s
- 다이얼로그/위젯 고정 크기: `about_dialog`(400×300, spacing 20, width 100),
  `file_transfer_dialog`(450×250, width 100), `font_settings_dialog`(spacing 15),
  `port_settings`(40/40/45), `main_status_bar`(100), `file_progress`(60), `data_log`(100)
  → 성격별로 묶어 상수화(예: `DIALOG_SIZE_*`, `CONTROL_WIDTH_*`). **값은 그대로 유지**.
- 이미 사유 주석이 달린 기존 리터럴(2px 마진 등)은 건드리지 말 것.

### 2. 명명 규칙 정리 (`.agent/rules/naming_convention_guide.md` 기준)

- **`view/dialogs/preferences_dialog.py`의 `log_path_edit`가 실제로는 `QLabel`** — 타입을
  오도하므로 `log_path_lbl`로 개명(가장 시급).
- `_edit` 접미사 위젯 5곳을 가이드 표기로 개명: `data_log_search_edit`,
  `sys_log_search_edit`, `repeat_interval_ms_edit`(→ `_input`),
  `command_edit`, `auto_tx_interval_edit`(→ `_txt` 또는 `_input`, 위젯 타입에 맞게).
  ⚠ **`get_state`/`apply_state`의 저장 키 문자열은 바꾸지 말 것** — 기존 사용자 설정 호환이
  깨진다. 변수명만 바꾸고 저장 키는 유지(불일치가 생기면 주석으로 사유를 남긴다).
- 언어 키의 `edit` 토큰 6개는 **개명하지 않는다**(S-046이 가이드 표에 `edit`를 추가해
  정합을 맞췄고, 키 개명은 사용자 설정과 무관하나 변경 범위가 커서 효익이 낮다).
  이 판단을 보고에 적어라.

### 3. lint 도입 (ruff)

- `.venv`에 ruff 설치, `pyproject.toml`(또는 `ruff.toml`)에 최소 설정:
  line-length는 현재 코드에 맞춰 잡고(`.agent/rules/code_style_guide.md`는 79/최대 100을
  말하지만 실제 코드가 더 길 수 있으니 **현행 코드 기준으로 정하고 근거 보고**),
  규칙은 `E`(pycodestyle), `F`(pyflakes) 정도로 시작.
- `ruff check .` 실행 → 위반이 많으면 **자동 수정(`--fix`)은 하지 말고** 유형별 개수를
  보고한 뒤, 명백히 안전한 것(미사용 import 등)만 수동 정리.
- `.github/workflows/ci.yml`에 lint job 추가(실패해도 전체를 막지 않도록 할지 여부는
  위반 개수를 보고 판단해 근거와 함께 결정).
- `requirements.txt`에는 넣지 말 것(런타임 의존성 아님) — README 개발 도구 절에 설치 명령만.

## 검증 방법

전체 pytest(offscreen, **기준선 227**) + `check_language_keys` + 캡처 4조합(dark/light ×
ko/en) 육안(개명·상수화로 인한 UI 회귀 없음 확인). 캡처 후 `git status`에서
`resources/configs/settings.json`이 변경되지 않아야 정상.

## Acceptance criteria (DoD)

- [ ] 매직 넘버가 상수로 이동(값 불변), 사유 주석 있는 기존 리터럴은 그대로.
- [ ] `log_path_edit` 등 타입 오도 이름 정리, **저장 키 호환 유지**.
- [ ] ruff 설정·실행 결과 보고, CI에 lint job 추가.
- [ ] 전체 pytest 통과, 캡처 회귀 없음.
