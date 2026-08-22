# mistakes.md — 실수 대장 (자가 진화 기록)

형식: `YYYY-MM-DD | 증상 | 원인 | 일회성: 예/아니오 | 조치`
동일 원인 2회 반복 시 규칙화한다 (RULES.md §1). 규칙화된 항목에는 `→ 규칙화됨` 표시.

| # | 날짜 | 증상 | 원인 | 일회성 | 조치 |
|---|---|---|---|---|---|
| 1 | 2026-08-22 | CLAUDE.md/.claude/tools 등이 타 프로젝트(Board Provisioner·STOM·Persephone) 내용으로 채워져 있어 세션 규칙·훅이 오작동 소지 | 프로젝트 부트스트랩 시 다른 프로젝트의 에이전트 설정을 통째로 복사 | 예 | SerialTool 기준으로 전면 재작성. 새 프로젝트 시작 시 설정 파일은 복사하지 않고 프로젝트 파악 후 새로 작성한다 |
| 2 | 2026-08-22 | 마이그레이션이 제거·개명한 설정 키가 파일에 되살아남 (3회: ui 폰트 키 S-027, right_section_width S-028, serial.flowctrl S-030) | defaults(create_fallback_settings)가 옛 키를 계속 보유 — fallback-base 병합이 마이그레이션 결과를 덮음 | 아니오 | → 규칙화됨: S-030 Step 5에 기계적 차단 테스트(마이그레이션을 defaults에 적용하면 no-op이어야 함) 추가. 이후 마이그레이션 변경 시 defaults를 반드시 함께 갱신 |
| 3 | 2026-08-22 | 타 프로젝트(Board Provisioner) 문서 doc/ui-guidelines.md가 리뷰 없이 커밋에 딸려 들어감 (54cab4a) | 에이전트 병렬 작업 중 출처 불명 파일이 생겼는데 리뷰어가 `git add -A`로 스테이징 — RULES §5 pathspec 규율 위반 | 예(재발 시 규칙화) | 파일 제거 커밋. 다중 에이전트 세션에서는 커밋 직전 `git status` 확인 + pathspec `git add`만 사용 |
