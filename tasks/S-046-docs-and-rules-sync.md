# S-046 — [P2] 문서·규칙 정합 일괄 + EventBus 규칙 정밀화

- Status: TODO
- Recommended model: **하위(Sonnet) 가능** (판정은 이미 확정 — 문서 반영만)
- 선행: 없음 (문서만 수정 — 다른 태스크와 병렬 안전)
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-6 판정, D 문서군

## 목적 (Why)

문서가 코드보다 뒤처져 잘못된 정보를 준다. 특히 **완료된 작업이 미완료로 표기**되어 있고,
**규칙 문서가 실제 설계와 어긋나** 있어 다음 작업자를 오도한다.

## Steps

### 1. EventBus 규칙 정밀화 (상위 판정 반영 — CLAUDE.md)

현재 CLAUDE.md는 "상태·이벤트는 EventBus 경유. 예외는 단 하나 — Fast Path"라고 적었지만,
실제 코드는 `connection_closed` 등을 **Qt 직접 시그널(소유 Presenter) + EventBus(팬아웃)**
두 채널로 쓴다. 감사 결과 이는 중복 처리가 아니라 **관심사별 팬아웃**이며 설계로서 합리적이다
(Qt 시그널의 타입 안정성·수명 관리 이점).

→ 문언을 실제 설계에 맞게 고친다. 취지:
- **Qt 직접 시그널**: 소유 관계가 명확한 인접 계층 1:1/1:N (Model ↔ 그것을 소유한 Presenter).
- **EventBus**: 계층을 건너뛰거나 소유 관계가 없는 다자 팬아웃, 그리고 대량 RX의 Fast Path 예외.
- "예외는 단 하나"라는 문장을 위 기준으로 대체하되, **새 Fast Path를 임의로 늘리지 않는다**는
  기존 제약은 유지.

### 2. 완료 작업 반영 (`doc/task.md`)

Phase 6·8의 미체크 항목 중 **실제로 완료된 것**을 체크한다: AutoTxScheduler(S-006),
성능 벤치마크(S-011), pyinstaller.spec·EXE 빌드(S-012), GitHub Actions CI(S-014),
RingBuffer bytearray(이미 구현돼 있었음). **이력 문서이므로 체크만 추가하고 과거 항목을
재구성하지 말 것**(CLAUDE.md 규칙).

### 3. `doc/00_overview.md`

- "성능 벤치마크, 가상 시리얼 포트 검증, 패키징·CI는 후속 작업" → 실제 상태로
  (가상 포트(S-010)만 미완).
- "설정은 resources/configs/settings.json에 저장되므로 배포 전 사용자 데이터 경로 분리가
  필요" → S-013/S-043으로 완료된 상태로 갱신(번들=APPDATA, 개발=settings.local.json).

### 4. `README.md`

- 프로젝트 구조 트리에 `core/transport/loopback_transport.py` 추가.
- 기능 목록(§1)에 LOOPBACK 디버그 포트 한 줄 추가.
- 설정 구조 예시(§6.5 부근)에 `version` 필드 추가(실제 스키마는 1.3이 필수).
- `model/connection_manager.py` 항목은 **S-044가 삭제 중**이므로 건드리지 말 것(충돌 회피).

### 5. `.agent/rules/naming_convention_guide.md`

- 언어 키 Context 표가 실제와 완전히 불일치한다. 표의 `rx`/`manual_ctrl`/`file_prog`/
  `inspector`/`system`/`toolbar`/`status` 중 **실제 코드에 존재하는 것이 하나도 없다**.
  `resources/languages/en.json`의 실제 prefix를 조사해 표를 재작성하라
  (`pref/main/macro/port/manual/data/sys/font/packet/file/about/right/lifecycle/left` 등).
- 도구 경로 오기 수정: `tools/manage_lang_keys.py` → `tools/manage_language_keys.py`.
- Type 토큰 표에 실제 사용 중인 `edit`가 없다 — 표에 추가하거나 "코드 정리 대상"으로 명시
  (실제 코드 개명은 이 태스크 범위 밖 — 판단해서 보고).

### 6. `requirements.txt`

`requests`, `qdarkstyle`이 소스 전체에서 사용처 0건이다. **삭제 전 재확인**(Grep으로
import·문자열 참조 전수) 후 제거하고, README §2.1 요구사항 목록과 일치시킨다.
하나라도 참조가 있으면 삭제하지 말고 보고.

## 검증 방법

- 전체 pytest(offscreen, 기준선 168) — 문서 변경이므로 회귀가 없어야 정상.
- `requirements.txt` 변경 후 `.venv\Scripts\python -c "import main"` 스모크.
- 수정한 문서의 주장이 실제 코드와 맞는지 각 항목마다 한 번씩 확인(추측으로 쓰지 말 것).

## Acceptance criteria (DoD)

- [ ] CLAUDE.md의 EventBus 문언이 실제 설계와 일치한다.
- [ ] doc/task.md·00_overview.md·README가 현재 상태를 반영한다.
- [ ] naming guide의 언어 키 표가 실제 prefix와 일치한다.
- [ ] 미사용 의존성 제거(또는 보류 사유 보고), import 스모크 통과.
