# S-053 — ThemeManager 분해 (FontManager + ThemeResourceLoader)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (분해 후보 확정 — 벗어나면 중단·보고)
- 선행: **S-050**(특성화 테스트 21건이 안전망 — 이미 완료)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-7 / S-050 보고의 분해 후보

## 목적 (Why)

`view/managers/theme_manager.py`(833줄)가 6가지 관심사를 한 클래스에 담고 있다
(S-050 조사 결과): 싱글톤 수명, 정적 팔레트·폰트 테이블, 아이콘 해석, 테마 파일 탐색,
폰트 서브시스템, QSS 조립(216줄 폴백 포함), `apply_theme` 오케스트레이션.

폰트 하나를 테스트하려 해도 QApplication·아이콘·QSS 로직이 전부 딸려온다.
**이제 S-050의 특성화 테스트 21건이 있으므로 안전하게 쪼갤 수 있다.**

## 확정 설계 (S-050 보고의 후보 채택)

1. **`FontManager`** (가장 깨끗한 분리 — 나머지에 의존하지 않는다):
   - `set/get_proportional_font`, `set/get_fixed_font`, `get_font_settings`,
     `restore_fonts_from_settings`, `_generate_font_stylesheet`, 플랫폼별 폰트 테이블.
   - 폰트 변경 시 테마 재적용이 필요하므로 **콜백(또는 시그널)로 트리거**만 넘긴다 —
     FontManager가 ThemeManager를 역참조하면 안 된다(S-050에서 없앤 순환을 되살리지 말 것).
2. **`ThemeResourceLoader`**: 아이콘 해석(`get_icon`, 테마 suffix 라우팅), 테마 파일 탐색
   (`get_available_themes`, `_get_theme_file_path`), QSS 로드·폴백·팔레트 생성.
   - ⚠ S-050이 발견한 함정을 **이번에 함께 고친다**: `ThemeManager.__init__`이
     `self._theme_dir`를 생성 시점에 캐시해, `_resource_path`만 재주입하면 테마 경로
     리다이렉트가 무효가 된다. 새 로더는 **`ResourcePath`를 그때그때 참조**하도록 만들 것.
3. **`ThemeManager`는 얇은 오케스트레이터로**: `theme_state` 보유, 위 둘을 조합,
   `apply_theme`에서 QSS 조립 → 적용 → `color_manager.apply_theme` 호출.
4. **외부 계약 절대 보존**: 앱 전역이 `theme_manager` 싱글톤의 공개 메서드를 직접 부른다
   (`main.py`, `view/` 다수). **공개 API 이름·시그니처를 바꾸지 말 것** — 내부만 위임으로
   바꾼다. 바꿔야 할 이유가 생기면 중단·보고.

## 검증 방법

- **S-050의 `tests/test_theme_color_managers.py`가 수정 없이 그대로 통과해야 한다** —
  이것이 이 리팩토링의 안전 판정이다. 테스트를 고쳐야 통과한다면 계약이 깨진 것이므로
  중단하고 보고하라(테스트를 리팩토링에 맞추지 말 것).
- 신규 클래스 각각에 단위 테스트 추가(FontManager는 QApplication 없이도 상당 부분 가능).
- 전체 pytest(offscreen, **기준선 284**) 2회 연속 + 캡처 4조합 육안(테마·폰트·아이콘이
  이전과 동일) + `ruff check` 클린. 캡처 후 `settings.json` 무변경 확인.

## Acceptance criteria (DoD)

- [ ] `FontManager`/`ThemeResourceLoader` 분리, `ThemeManager`는 오케스트레이터.
- [ ] **S-050 특성화 테스트가 무수정 통과**.
- [ ] `_theme_dir` 캐싱 함정 해소.
- [ ] 공개 API 불변, 순환 참조 재도입 없음, 전체 pytest 통과.
