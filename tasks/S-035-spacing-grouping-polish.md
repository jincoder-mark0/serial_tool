# S-035 — 마진·구획 정비 (그룹 경계·제목 간격·체크박스 그루핑)

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (확정 설계 기준)
- 선행: **S-033·S-034 커밋 후** (constants.py·view 파일 충돌 회피)
- Skills to load: task-done, lang-keys

## 목적 (Why) — 사용자 보고 + 캡처 판정 (2026-08-22, 마진·배치 UX 점검)

"컴포넌트 간 마진 부족·배치 불편" 보고를 캡처+코드로 판정한 결과:
- 그룹 테두리가 배경과 대비 1.1:1(dark)/1.5:1(light)로 **사실상 보이지 않아** 구획감 부재.
- 섹션 제목→내용 간격이 QGroupBox 계열 ~20px vs section-title 계열 2px로 **10배 차이**.
- 체크박스 행의 항목 간 간격(5px)이 체크박스 내부 간격(QSS spacing 5px)과 동일해
  **인디케이터가 어느 라벨 소속인지 혼동**.

## 확정 설계 (상위 판정: 저위험 처방 채택 — 전 섹션 플랫 통일 재설계는 보류)

1. **그룹 테두리 대비 상향** (QSS 3테마): `QGroupBox` border-color를 배경 대비 **3:1 이상**으로 —
   dark `#404040`→`#5f5f5f` 부근, light `#c0c0c0`→`#9e9e9e` 부근, dracula도 동일 원칙.
   대비는 S-022의 계산식으로 확인해 값 조정.
2. **제목-내용 간격 통일**: `common/constants.py`에 `LAYOUT_SPACING_TITLE: int = 8` 신설 →
   `resources/themes/common.qss`의 `QLabel[class="section-title"] { margin-bottom: 2px }`를 8px로
   (QSS는 상수를 못 읽으므로 값 일치 주석을 양쪽에 남기고, `tests/test_ui_guidelines.py`의
   상수 존재 테스트에 추가).
3. **체크박스 그루핑 간격**: `LAYOUT_SPACING_GROUP: int = 10` 신설 →
   `view/widgets/manual_control.py`의 옵션 행 레이아웃 spacing에 적용
   (내부 5px < 항목 간 10px — 소속 신호 회복).
4. **Auto 행 단위 라벨**: `manual_control.py` Auto 간격 입력 뒤에 "ms" 라벨 추가
   (언어 키 — 기존 `macro_control_lbl_repeat_interval` 계열 어휘 확인 후 재사용/신설,
   lang-keys 절차). 입력 정렬도 실행 제어와 통일(우측 정렬 — SmartNumberEdit에
   정렬 API가 없으면 가능한 방법 확인, 무리면 보류·보고).
5. **실행 제어 행 구분**: `view/widgets/macro_control.py` — row1(저장/불러오기)과
   row2(반복 버튼) 사이 `addSpacing(LAYOUT_SPACING_GROUP)`; 하드코딩 마진 `(2,2,2,2)`는
   사유 주석 유지 또는 `LAYOUT_SPACING_TIGHT` 재사용으로 정리.
6. **보류 기록**: 전 섹션 플랫(section-title+HLine) 통일과 매크로 컬럼 정책 재조정은
   효익 대비 위험으로 보류 — 이 파일에 사유 남김.

## 검증 방법

전체 pytest(offscreen) + check_language_keys + 대비 계산(항목 1) +
캡처 8조합 육안(그룹 경계 가시성·제목 간격 통일감·체크박스 그루핑·회귀 없음) +
**캡처 후 `git checkout -- resources/configs/settings.json`**.

## Acceptance criteria (DoD)

- [ ] 3테마 GroupBox 테두리 대비 ≥3:1 (계산 출력 첨부).
- [ ] section-title 아래 간격 8px 통일, 체크박스 행 간격 10px.
- [ ] Auto 행에 ms 라벨(en/ko), 정렬 통일(또는 보류 사유).
- [ ] 전체 pytest 통과, 캡처 회귀 없음. minimumSizeHint 변화 보고.
