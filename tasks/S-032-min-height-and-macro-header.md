# S-032 — 최소 높이 마무리 + 매크로 테이블 헤더 잘림 수정

- Status: DONE (2026-08-22 — 하위 모델 수행, 상위 리뷰·판정 완료)
- **결과와 상위 판정**:
  - 매크로 헤더: 폰트 메트릭 기반 전역 `setMinimumSectionSize`(전 언어 헤더 최대 폭+패딩=126)
    적용 — Command·Delay 헤더 잘림 해소. 부작용(최소 폭 극단에서 테이블 가로 스크롤바 발생,
    Delay/Send 열이 스크롤 뒤로)은 **허용 판정**: Qt에 컬럼별 최소 폭 API가 없어 전역 하한이
    불가피하고, 기본 크기에서는 전 컬럼 표시되며, 헤더가 읽을 수 없게 잘리는 것보다 표준
    테이블 스크롤이 낫다.
  - PortStats 2열화: **태스크 전제 오류** — 코드는 최초 커밋부터 이미 2열 3행이었다
    (하위 조사로 확인, 상위가 작성 시 미확인 추정 → RULES §8 규칙화·mistakes #4).
    코드 무변경이 옳은 결과.
  - 높이: 최종 **780 (목표 730 미달, 폭 1093/1097 유지)** — 잔여 지배 요인(PortStats 134·
    DataLog 140·ManualControl 183)은 GroupBox chrome·구조 재설계 없이는 못 줄인다.
    **⛔ 보류 판정**: 폭 주결함은 해결됐고 −50px의 효익 대비 재설계 위험이 크다.
    재개 조건: 실사용 1366×768 노트북에서 세로 초과가 실제 문제로 보고될 때.
- Recommended model: **하위(Sonnet) 가능** (확정 설계 기준)
- 선행: S-026 (완료 — 이 태스크는 그 잔여 2건)
- Skills to load: task-done

## 목적 (Why) — S-026 에스컬레이션 2건 (2026-08-22)

1. **높이 780 vs 목표 730**: 1366×768 노트북 가용 높이(작업표시줄 감안 ≈728)에 아직 +50 초과.
   남은 지배 요인은 좌측 열의 `PortStatsWidget`(msh 260×134 — 통계 5행 세로 나열)과
   DataLog 2행화로 늘어난 +34.
2. **매크로 테이블 Command 헤더 잘림**: 새 최소 폭(1093)에서 우측 패널이 좁아지자
   `QHeaderView.Stretch` 컬럼(`view/widgets/macro_list.py:182`)이 헤더 텍스트 폭 이하로
   압축돼 "Command"→"omman"으로 렌더 (기존 잠재 결함이 폭 축소로 표면화).

## 확정 설계

1. **PortStats 2열화** (`view/widgets/port_stats.py` — 높이 134 → 목표 ≤95):
   그리드를 1열 5행 → 2열 3행으로 재배치: (RX | TX) / (오류 | 가동 시간) / (마지막 RX — 2열 span).
   라벨·refresh 헬퍼·retranslate 로직 불변, 그리드 add 위치만 변경. `LAYOUT_SPACING_DEFAULT` 유지.
2. **매크로 헤더 최소 섹션 폭** (`view/widgets/macro_list.py`):
   `header.setMinimumSectionSize(...)`를 헤더 폰트 메트릭 기반으로 부여
   (가장 긴 헤더 텍스트 폭 + 여백 — en/ko 중 넓은 쪽. 하드코딩 픽셀 금지, ui_guide §3).
   이로 인해 우측 최소 폭이 커지면 그 수치를 보고 (폭 여유가 1093→1280까지 187px 있음).
3. 목표 재확인: 최종 minimumSizeHint 높이 ≤730이면 성공. 미달이면 남은 지배 요인 계측값과
   함께 보고하고 중단 (추가 축약은 상위 재설계).

## 검증 방법

전체 pytest(offscreen, 기준선 122) + `tools/ux_capture.py` 8조합 캡처(육안: 통계 2열
가독성·매크로 헤더 완전 표시·회귀 없음) + minimumSizeHint 전/후 표 + 캡처 후
`git checkout -- resources/configs/settings.json`.

## Acceptance criteria (DoD)

- [ ] 매크로 Command 헤더가 최소 폭에서 완전히 표시된다 (ko/en).
- [ ] minimumSizeHint 높이 ≤730 또는 실측+사유 보고. 폭은 ≤1280 유지.
- [ ] 통계 라벨·refresh·retranslate 동작 불변, pytest 122 통과.
