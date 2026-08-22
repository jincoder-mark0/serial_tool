# S-030 — serial.flowctrl 죽은 키 부활 차단

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-028 (같은 결함 계열 — defaults가 마이그레이션이 개명한 옛 키를 보유)
- Skills to load: task-done

## 목적 (Why) — S-028 수행 중 발견 (2026-08-22)

`resources/configs/settings.json`의 `serial` 블록에 `flowctrl`(옛 키)과 `flow_control`(개명 키)이
공존한다. 1.0 마이그레이션이 `flowctrl`→`flow_control` 개명을 하지만,
`common/defaults.py`의 `DEFAULT_SERIAL_SETTINGS`가 여전히 `"flowctrl": "None"`을 기본값으로
갖고 있어 `_merge_settings`의 fallback-base 병합에서 옛 키가 되살아난다 —
S-027/S-028과 동일한 "defaults ↔ 마이그레이션 불일치" 계열.

## Steps

1. **정본 확인**: `serial.flow_control`과 `serial.flowctrl`의 reader를 각각 Grep 전수 확인
   (`common/ core/ model/ presenter/ view/`). 마이그레이션 개명 방향(flow_control)이 실사용과
   일치하는지 검증 — 불일치하면 중단·보고.
2. `common/defaults.py`의 `DEFAULT_SERIAL_SETTINGS`에서 `flowctrl` → `flow_control`로 교정
   (값 "None" 유지).
3. 마이그레이션 보강: 1.2 체인(S-028의 6단계 뒤)에 `serial.flowctrl` 잔존 키 제거 추가
   (`flow_control` 부재 시 값 이어받기 — S-028의 보전 패턴 그대로). CURRENT_VERSION은
   1.2 유지(같은 1.2 마이그레이션 단계에 편입 — 이미 1.2로 이관된 파일을 위해
   `_needs_migration` 없이도 잔존 키가 남을 수 있으니, 테스트로 1.2 재로드 시 동작 확인).
   판단이 갈리면(버전 1.3 승격 필요 여부) 중단·보고.
4. 테스트: defaults에 옛 키 부재 / 1.0 파일 이관 후 flowctrl 소멸·flow_control 보전 /
   현행 settings.json 로드 후 flowctrl 부재.
5. **재발 차단 테스트 (자가 진화 — 동일 원인 3회째의 기계적 차단, doc/mistakes.md #2)**:
   `create_fallback_settings()` 산출물에 `_migrate_settings`를 적용해도 **무변경(no-op)**임을
   고정하는 테스트 추가 — defaults가 옛 키를 갖는 순간 이 테스트가 깨진다.
   (`_needs_migration(defaults)` False 확인 포함.)
6. `resources/configs/settings.json` 정리 결과는 커밋 대상.

## Acceptance criteria (DoD)

- [ ] defaults·마이그레이션·실사용 코드가 같은 키(`flow_control`)를 가리킨다.
- [ ] settings.json에 `flowctrl` 부재, 전체 pytest 통과 (기준선 112+신규).
