# S-030 — 루트 serial 고아 블록 정리 (flowctrl 부활의 근본 원인)

- Status: DONE (2026-08-22 — 하위 조사가 태스크 전제 오류를 잡아 중단·에스컬레이션 →
  상위 재결정(고아 블록 제거) → 같은 에이전트 재개로 완결. 1.3 승격, 루트 serial 소멸,
  죽은 개명 매핑 제거, defaults 정리. **재발 차단 no-op 가드 테스트** 포함(테스트 +3) →
  기준선 118. 탭별 ports.tabs[*].serial.flowctrl 불변을 테스트로 고정.
  후속 검토 후보(범위 밖 보고): ports.default_config 블록도 고아 가능성 — 필요 시 별도 태스크)
- Recommended model: **하위(Sonnet) 가능** (개정된 확정 결정 기준)
- 선행: S-028
- Skills to load: task-done

## 경위

당초 "defaults의 `flowctrl` 오타를 `flow_control`로 교정"으로 정의했으나, 하위 모델의
Step 1 전수 조사(2026-08-22)로 전제가 틀렸음이 확인됐다:

- 루트 `settings.json["serial"]` 블록은 **어떤 코드도 읽지 않는 고아 블록 전체**다
  (`flowctrl`/`flow_control` 포함 전 필드 reader 0건). 실제 "새 포트 기본값"은
  `settings.port_*`(ConfigKeys)에서 읽는다.
- 실사용 `flowctrl`은 **다른 데이터 경로**다: `PortConfig.flowctrl`(dtos.py:96)과
  탭별 상태 `ports.tabs[i]["serial"]["flowctrl"]`(port_settings.py) — 코드 전역이
  `flowctrl` 명명을 쓰고 `flow_control`은 어디에도 없다.
- 즉 1.0 마이그레이션의 `flowctrl→flow_control` 개명은 **죽은 이름으로의 개명**이었다.

## 확정 결정 (2026-08-22, 상위 — 개정)

`global` 블록(S-027)과 동일하게 **루트 `serial` 블록을 고아로 규정하고 제거**한다.

1. `core/settings_manager.py`: 1.0 체인의 `flowctrl→flow_control` 개명 매핑 제거
   (죽은 이름으로의 개명 — 존치 이유 없음).
2. `CURRENT_VERSION` `"1.2"` → `"1.3"` + 1.2→1.3 마이그레이션: **최상위** `serial` 블록 삭제.
   ⚠ 최상위 키만 — `ports.tabs[*].serial`(탭별 실사용 상태)은 절대 건드리지 않는다.
3. `common/defaults.py`: `create_fallback_settings()`에서 `"serial"` 블록 제거,
   `DEFAULT_SERIAL_SETTINGS` 상수도 다른 참조가 없으면 제거 (참조 있으면 중단·보고).
4. `core/settings_schema.py`: `serial` property 정의가 있으면 제거.
5. **재발 차단 테스트 (핵심 — doc/mistakes.md #2 규칙화)**:
   `create_fallback_settings()`에 `_migrate_settings`를 적용해도 무변경(no-op)임을
   고정하는 테스트 (`_needs_migration(defaults)` False 포함).
6. 테스트: 1.2 파일 이관 시 최상위 serial 소멸 + `ports.tabs[*].serial.flowctrl` 불변 /
   1.3 무변경 통과. 캡처 1회 후 `resources/configs/settings.json` 1.3 이관 결과 커밋
   (checkout 금지).

## Acceptance criteria (DoD)

- [ ] 최상위 serial 블록·죽은 개명 매핑·defaults 항목이 모두 소멸, 탭별 flowctrl 불변.
- [ ] defaults no-op 가드 테스트 존재 (defaults에 옛 키가 생기면 즉시 실패).
- [ ] 전체 pytest 통과 (기준선 115+신규), settings.json version 1.3.
