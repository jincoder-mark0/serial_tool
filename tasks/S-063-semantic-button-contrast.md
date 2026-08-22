# S-063 — 의미색 버튼(accent/danger/warning) 텍스트 대비 미달

- Status: DOING (2026-08-22 — 하위 모델 수행 중)
- Recommended model: **하위(Sonnet) 가능** (목표값 확정 — 벗어나면 중단·보고)
- 선행: S-060 (클래식 테마 추가 시 드러남)
- Skills to load: task-done
- 근거: S-060 에스컬레이션 + 상위 실측 (2026-08-22)

## 목적 (Why) — 실사용에서 글씨가 안 보인다

의미색 버튼(전송=accent, 반복 중지=danger, 반복 일시정지=warning)이 **흰 글씨 + 밝은
배경** 조합이라 텍스트가 읽히지 않는다. 클래식 테마 캡처에서 육안으로 확인됐고,
**기존 3테마에도 있던 문제**다(S-060이 대칭성을 위해 그대로 복사하며 발견·보고).

### 실측 (상위 모델 계산, WCAG 상대 휘도)

```
light/classic accent   #ffffff on #4CAF50:  2.78  FAIL
light/classic danger   #ffffff on #F44336:  3.68  FAIL
light/classic warning  #ffffff on #FF9800:  2.16  FAIL  ← 가장 심각
dark warning           #ffffff on #EF6C00:  3.08  FAIL
dark accent            #ffffff on #2E7D32:  5.13  OK
dark danger            #ffffff on #C62828:  5.62  OK
dracula accent         #282a36 on #50fa7b: 10.38  OK   ← 어두운 글씨가 정답인 사례
```

**dracula가 이미 정답을 보여준다**: 밝은 배경에는 어두운 글씨를 쓴다.

## 확정 설계

**원칙: 배경 밝기에 따라 글자색을 고른다.** 배경색(의미색)은 최대한 유지하고 글자색을
바꾸는 쪽을 우선한다 — 의미색은 브랜드/관습(녹=실행, 빨=중지, 주황=일시정지)이라
바꾸면 인지가 흔들린다.

검증된 대안(상위 계산):
```
#1b1b1b on #4CAF50 (accent, 밝은 녹):   6.20  OK
#1b1b1b on #FF9800 (warning, 주황):     7.99  OK
#ffffff on #C62828 (danger, 어두운 빨): 5.62  OK
```

1. **light / classic**: accent·warning은 **어두운 글씨**(`#1b1b1b` 계열)로.
   danger는 배경을 `#C62828`로 낮추고 흰 글씨 유지(빨강은 어두운 글씨보다 이쪽이 자연스럽다).
2. **dark**: warning만 미달 — 배경을 더 낮추거나 글자를 어둡게 해 ≥4.5 달성.
3. **dracula**: 현재 방식(어두운 글씨) 유지. 다른 의미색도 같은 기준을 만족하는지 **확인**하라.
4. **hover/pressed 상태도 함께 검증**한다 — 배경이 밝아지는 hover에서 대비가 더 나빠질 수 있다.
   각 상태의 배경색으로 계산해 ≥4.5(비활성은 ≥3.0)를 만족시켜라.
5. 4테마 모두 **같은 규칙**을 적용해 일관성을 유지한다(S-022/S-060의 대칭 원칙).

## 검증 방법

- **대비 계산 출력 첨부**(각 테마 × accent/danger/warning × 기본·hover·pressed·disabled).
  계산 스크립트 패턴은 `tasks/S-022-theme-contrast-hardcoded-colors.md` 참조.
- 캡처 4테마(dark/light/classic × ko, dracula는 임시 스크립트나 도구 확장으로) —
  **"전송", "반복 시작/중지/일시정지" 버튼 글씨가 읽히는지 육안 확인**이 이 태스크의 핵심이다.
- 전체 pytest(offscreen, 기준선은 직전 커밋 값) + **ruff 0건**.
- 캡처 후 `git status`에서 `settings.json` 무변경 확인.

## Acceptance criteria (DoD)

- [ ] 4테마의 의미색 버튼 텍스트가 모든 상태에서 대비 기준을 만족한다(계산 첨부).
- [ ] 캡처에서 버튼 글씨가 명확히 읽힌다(육안 확인 보고).
- [ ] 의미색(녹/빨/주황)의 인지가 유지된다 — 색상 자체를 크게 바꾸지 않았음을 보고.
- [ ] 전체 pytest·ruff 통과.
