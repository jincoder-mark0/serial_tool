# S-009 — 플러그인 인프라

- Status: TODO
- Recommended model: **상위 전용** (인터페이스 설계가 본체) — 하위 모델 시작 금지
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

`doc/task.md` Phase 7 계획: `core/plugin_base.py`(인터페이스) + `core/plugin_loader.py`
(동적 임포트) + ExamplePlugin. 현재 **코드에 플러그인 관련 구현은 전혀 없다**
(core/에 두 파일 모두 부재, EventTopics에 플러그인 토픽 없음 — 2026-08-22 조사).

## 설계 재료

- 초안: `doc/implementation_plan.md:552-584` — `PluginBase(ABC)`, `importlib` 기반
  `plugins/` 디렉터리 스캔, `plugins/example_plugin/`.
- 결정 필요: 플러그인이 접근 가능한 표면(EventBus 구독만? 송신 API도?), 로드 실패 격리,
  샌드박스/신뢰 모델, 활성화 UI(Preferences 탭?), 배포 형태(단일 .py vs 패키지).
- 아키텍처 제약: 플러그인이 View를 직접 만지게 하지 않는다 (MVP 유지). EventBus
  와일드카드 구독(`core/event_bus.py:130-133`, fnmatch)이 자연스러운 진입점.

## Acceptance criteria (설계 후 상세화)

- [ ] 인터페이스·신뢰 모델 결정 기록 (이 파일 또는 doc/ ADR).
- [ ] 하위 모델용 구현 태스크 분할.
