# S-044 — [P2] Dead code 제거 + DTO/enum 우회 정리

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done
- 근거: `doc/refactor_audit_20260822.md` C-3, C-4

## 목적 (Why)

**Dead code 3건** (감사에서 전수 grep으로 무참조 확인):
- `model/connection_manager.py`(119줄) — 어디서도 import되지 않는다. 그런데 **README 구조도는
  "연결 인스턴스 관리" 활성 기능으로 나열**해, S-015(SPI/I2C) 작업자가 "이미 있는 확장점"으로
  오인할 함정이다. 실제로는 `MainPresenter`가 `ConnectionController`를 직접 생성한다.
- `view/widgets/packet.py`(131줄) — `view/widgets/__init__.py`에서 재수출만 되고 인스턴스화 0건.
  실제 패킷 뷰는 `view/panels/packet_panel.py`의 별개 구현.
- `common/enums.py` `MacroStepType` — 참조 0건.

**DTO/enum 우회 2건**:
- 매크로 스크립트 로드가 `MacroScriptData` DTO를 두고도 raw `dict`로 Worker→Presenter→View를
  통과한다(`presenter/macro_presenter.py`의 `load_finished = pyqtSignal(dict)`, `_on_load_success`,
  `panel.apply_state(data)`). CLAUDE.md: "계층 간 데이터 전달은 dict 금지, DTO만 사용".
- `model/file_transfer_service.py`가 `SerialFlowControl` enum 대신 `["RTS/CTS","XON/XOFF"]`
  문자열 리터럴로 비교한다(오타 시 조용히 실패). `status="Sending"` 리터럴도 `FileStatus` 우회.

## Steps

1. **삭제 전 재확인**: 세 dead code 각각을 Grep으로 전수 재확인한다(테스트·문서 포함).
   참조가 하나라도 있으면 **삭제하지 말고 보고**. `view/widgets/__init__.py`의 재수출도 함께 제거.
2. 삭제 수행. `README.md` 구조도에서 `connection_manager.py` 항목 제거(또는 실제 상태로 정정).
3. **매크로 로드 DTO화**: `MacroScriptData`(`common/dtos.py`)를 실제로 사용하도록
   Worker→Presenter→View 경로를 정리한다. 시그널 시그니처는 `pyqtSignal(object)`로,
   View의 `apply_state`가 받는 타입도 함께 정리. **기존 저장/불러오기 동작(JSON 파일 형식)은
   바뀌면 안 된다** — 파일 포맷 호환성 유지가 조건이다.
4. **enum 우회 정리**: `file_transfer_service.py`의 문자열 리터럴을 `SerialFlowControl`/
   `FileStatus` enum 값 참조로 교체. 값이 동일해야 기존 동작이 유지된다(확인 후 교체).

## 검증 방법

- 삭제 후 전체 pytest(offscreen, 기준선 168) + 앱 import 스모크
  (`.venv\Scripts\python -c "import main"`) — 삭제된 모듈을 참조하는 곳이 없는지.
- 매크로 저장→불러오기 왕복 테스트(기존 테스트가 있으면 통과, 없으면 1건 추가).
- 캡처 1회(dark/ko)로 UI 회귀 없음 확인 후 `git checkout -- resources/configs/settings.json`
  (S-043 이후로는 settings.local.json에 쓰이므로 settings.json이 변경되지 않아야 정상 —
  변경됐다면 보고).

## Acceptance criteria (DoD)

- [ ] dead code 3건 제거, 잔존 참조 0건, README 정합.
- [ ] 매크로 로드가 DTO 경유이고 파일 포맷 호환이 유지된다(왕복 테스트).
- [ ] file_transfer_service의 문자열 리터럴이 enum 경유로 교체됨.
- [ ] 전체 pytest 통과.
