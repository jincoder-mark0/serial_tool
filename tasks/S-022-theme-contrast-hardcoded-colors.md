# S-022 — 테마 대비 미달·하드코딩 색 수정

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰 승인. 8항목 전부 반영: 위젯 코드
  색 리터럴 제거(QSS 동적 속성 방식), 3테마 QSS 규칙 신설, 대비 전 조합 ≥4.5 계산 검증.
  하위 모델이 지정 색 2건의 미달을 계산으로 발견해 대체(light 연결색 #2e7d32→#1b5e20 4.499
  미달, dracula danger #ff5555→#c62828 텍스트 대비 미달) — 근거 주석 명기.
  에스컬레이션 처리: constants.py LOG_COLOR_DARK_ERROR도 #FF6B6B로 정합(상위 수정) —
  color_rules.json 재생성 시 구값 복귀 드리프트 차단. pytest 85 passed, 캡처 4조합 확인)
- Recommended model: **하위(Sonnet) 가능** (목표 색은 상위가 확정해 둠 — 대비 계산으로 검증)
- 선행: 없음 (근거: doc/ux_audit_20260822.md 높음 #8~#10, 중간 에러색, 낮음 QSS 상태)
- Skills to load: task-done

## 목적 (Why)

핵심 상태 표시(녹화중 REC, 포트 연결 ●, 에러 로그색)가 WCAG AA(4.5:1) 미달이고,
일부 다이얼로그가 테마를 우회한 고정 색이라 라이트 테마에서 다크 조각이 남는다.

## 수정 목록

1. **REC 표시** — `view/widgets/data_log.py:415`, `view/widgets/system_log.py:297`:
   인라인 `setStyleSheet("color: red;")` 제거. 대신 버튼에 동적 속성
   `setProperty("state", "recording")`(해제 시 속성 제거+style repolish)을 주고, 3개 QSS
   (`resources/themes/dark|light|dracula_theme.qss`)에 `QPushButton[state="recording"]:checked`
   규칙 신설 — dark/dracula: 배경 `#5a1d1d`·글자 `#ff8a80`, light: 배경 `#ffcdd2`·글자 `#b71c1c`
   (각 조합 대비 4.5:1 이상 — 아래 검증 스크립트로 확인).
2. **light 섹션 제목** — `light_theme.qss:251-253` `#2196F3` → `#1565C0`.
3. **상태바 연결 ●/○** — `view/sections/main_status_bar.py:101-105` 하드코딩 `#4CAF50`/`#9E9E9E`:
   테마별 색을 ThemeManager/ColorManager 경유로 받도록 변경 (기존 다른 위젯이 테마 색을 받는
   패턴을 먼저 찾아 동일하게 — 없으면 QSS 동적 속성 방식). light에서 4.5:1 이상 색으로
   (예: 연결 `#2e7d32`, 해제 `#616161`).
4. **파일 전송 라벨** — `view/dialogs/file_transfer_dialog.py:81-83` 하드코딩 다크 박스 제거 →
   QSS 클래스로 이전 (3테마 QSS에 규칙 추가).
5. **About 라벨** — `view/dialogs/about_dialog.py:43,52` `#888`/`#666` 제거 → QSS 보조 텍스트
   클래스(3테마) 사용.
6. **에러 로그색** — `resources/configs/color_rules.json` AT_ERROR/SYS_ERROR dark_color
   `#F44336` → `#FF6B6B` (dark `#1e1e1e`·dracula `#21222c` 배경 모두 4.5:1 이상 확인).
7. **QSS 상태 보강 (3테마 동일 패턴)** — QComboBox/QCheckBox::indicator/QTabBar::tab에
   `:disabled` 규칙, `QPushButton[state="disconnected"]`에 `:hover` 추가.
8. **경고 빨강 톤 통일** — `main_status_bar.py:128` `#FF5252`, `file_progress.py:157` `red` →
   테마 danger 색과 동일 값으로 (QSS 또는 상수 경유 — 색 리터럴을 위젯 코드에 남기지 않는 방향).

## 대비 검증 스크립트 (수정 후 필수 실행)

```powershell
.venv\Scripts\python -c "
def lum(h):
    h=h.lstrip('#'); r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def ratio(a,b):
    la,lb=sorted([lum(a),lum(b)],reverse=True); print(f'{a} on {b}: {(la+0.05)/(lb+0.05):.2f}')
ratio('#ff8a80','#5a1d1d'); ratio('#b71c1c','#ffcdd2'); ratio('#1565C0','#f5f5f5')
ratio('#2e7d32','#f0f0f0'); ratio('#FF6B6B','#1e1e1e'); ratio('#FF6B6B','#21222c')
"
# 전 조합 4.5 이상이어야 통과. 색을 바꿨으면 이 스크립트의 값도 같이 바꿔 재실행.
```

## Acceptance criteria (DoD)

- [ ] 위 8항목 반영, 위젯 코드의 색 리터럴 제거(§8 포함).
- [ ] 대비 스크립트 전 조합 ≥ 4.5.
- [ ] 8조합 캡처(특히 light)에서 다크 잔존 조각·저대비 상태 표시 없음 (육안 확인 보고).
- [ ] 전체 pytest 통과.

## 검증 방법

위 대비 스크립트 + `tools/ux_capture.py` 8조합 캡처 육안 확인 + 전체 pytest.
