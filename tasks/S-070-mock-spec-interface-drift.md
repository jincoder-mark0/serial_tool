# S-070 — Presenter->View 인터페이스 드리프트를 Mock이 삼킨다

- Status: DONE (2026-08-23 — 상위 직접 수행. View Mock 전수에 spec 적용 + 정적 계약 검사 신설(147건 확인). 새 결함 0건 — S-067이 이 부류의 유일한 사례였다. pytest 459 passed, ruff 0건)
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-067 (이 구멍으로 실제 결함이 새어 나간 사례)
- Skills to load: task-done
- 근거: S-067 조사 중 발견 + 상위 전수 확인 (2026-08-22)

## 목적 (Why) — 393개가 초록인데 앱은 매번 죽었다

S-067에서 `ManualControlPresenter.set_enabled()`가 패널에 **없는 메서드**
(`panel.set_enabled()`, 실제 이름은 `set_controls_enabled()`)를 부르고 있었다.
사용자가 포트 탭을 바꿀 때마다 앱이 AttributeError로 죽었는데, 전체 테스트는
393개 전부 통과였다.

이유는 단순하다. Presenter 테스트가 View를 `MagicMock()`으로 만드는데 **`spec`이 없어
어떤 이름이든 받아준다.** 존재하지 않는 메서드를 불러도 Mock이 조용히 삼킨다.

`grep -rn "spec=\|autospec" tests/` 결과 프로젝트 전체에서 **0건**이다. 즉 이 구멍은
`manual_control` 하나가 아니라 **모든 Presenter 테스트에 열려 있다.**

## Steps

1. **먼저 실태를 조사하라.** Presenter 테스트에서 View/Panel을 Mock으로 만드는 지점을
   전수 파악한다. 어떤 Presenter가 어떤 View 클래스를 상대하는지 표로 보고하라.
2. **각 Mock에 `spec=<실제 View 클래스>`를 지정한다.** 한 번에 다 바꾸지 말고
   파일 단위로 진행하며, 바꿀 때마다 테스트를 돌려라.
3. **여기서 새 결함이 나올 가능성이 높다** — spec을 붙이는 순간 "지금까지 조용히
   통과하던 잘못된 호출"이 드러난다. 그런 것이 나오면:
   - **프로덕션 코드의 오타/개명 누락이면 고친다** (S-067과 같은 부류).
   - 판단이 필요한 설계 문제로 보이면 **중단하고 보고**하라.
   - 발견한 것은 개수와 내용을 반드시 보고에 남긴다 — 이 태스크의 성과가 그것이다.
4. **`spec`을 붙일 수 없는 경우**(예: 테스트가 View에 없는 헬퍼를 일부러 붙여 씀)가
   있으면 억지로 맞추지 말고, 그 사유를 주석으로 남기고 보고하라.
5. 마지막으로 `.agent/rules/`나 `tests/README.md` 중 적절한 곳에 한 줄 규칙을 남긴다:
   **"View/Panel Mock에는 `spec=`을 지정한다 — 없으면 존재하지 않는 메서드 호출이
   테스트를 통과한다."** 어디에 쓸지는 기존 문서 구성을 보고 판단하라.

## 검증 방법

- 전체 pytest(offscreen, 기준선은 직전 커밋 값) + **ruff 0건**.
- **spec을 붙였다고 끝이 아니다**: 최소 한 곳에서 일부러 없는 메서드를 부르도록 고쳐
  테스트가 실패하는 것을 확인하고, 그 출력을 보고에 인용하라(S-067에서 이 확인으로
  실효성을 증명했다).
- 새로 드러난 결함이 있으면 각각 수정 전 실패를 확인한 뒤 고쳤음을 보고하라.

## Acceptance criteria (DoD)

- [x] Presenter 테스트의 View Mock 전수에 `spec=`이 지정된다.
- [x] spec 적용으로 드러난 결함: **0건**. 정적 검사로 147건을 전수 확인한 결과도 0건 — S-067이 이 부류의 유일한 사례였다.
- [x] S-067 결함(`panel.set_enabled`)을 되살려 정적 검사가 파일:라인·체인·클래스를 짚어 실패하는 것을 확인했다.
- [x] `tests/README.md`에 "View Mock 규율" 절 추가.
- [x] 전체 pytest·ruff 통과.


## 수행 결과 (2026-08-23, 상위 직접)

### 1. spec 적용 (테스트가 지나가는 경로)

| 테스트 | Mock | spec |
|---|---|---|
| `test_presenter_manual_control.py` | `mock_panel` | `ManualControlPanel` (S-067에서 선적용) |
| `test_presenter_packet.py` | `mock_panel` | `PacketPanel` |
| `test_auto_tx.py` (2곳) | `panel` | `ManualControlPanel` |
| `test_presenter_init.py` | 하위 패널 3종 | `ManualControlPanel`/`SystemLogWidget`/`PacketPanel` |
| `test_port_scan_shutdown.py` | 하위 패널 3종 | 동일 |

`MainWindow` 자체에는 spec을 걸지 않았다. `spec=MainWindow`는 **클래스 속성만**
노출하는데 `left_section` 등은 `__init__`에서 만들어지는 인스턴스 속성이라, 픽스처의
`view.left_section = MagicMock()` 대입이 막힌다. Presenter 호출이 실제로 닿는 곳은
하위 패널이므로 거기에 거는 편이 값어치가 크다.

### 2. 정적 계약 검사 — 여기서 진짜 값이 나온다

spec은 **테스트가 실제로 지나가는 호출만** 막는다. Presenter의 View 호출은 대부분
테스트가 닿지 않으므로, 그것만으로는 이 구멍을 닫았다고 할 수 없다.

`tests/test_presenter_view_contract.py`를 만들어 소스를 AST로 훑는다. `__init__`
파라미터 중 View 타입으로 주석된 것을 찾고, `self.X = param` 대입을 추적한 뒤,
`self.X.a.b` 형태의 접근을 **실제 View 인스턴스에서 `getattr`로 따라간다.**

클래스만 봐서는 부족했다 — `left_section` 같은 속성은 `__init__`에서 생겨 클래스에
없다. 그래서 실제 인스턴스를 하나 만들어 체인을 걷는다.

검사 규모:

| Presenter | 확인한 접근 |
|---|---|
| `main_presenter.py` | 57 |
| `manual_control_presenter.py` | 30 |
| `macro_presenter.py` | 28 |
| `port_presenter.py` | 19 |
| `packet_presenter.py` | 12 |
| `data_handler.py` | 1 |
| **합계** | **147** |

`checked >= 100` 하한을 걸어 두었다. 추적 로직(타입 주석 → 대입 형태)이 깨지면
검사가 조용히 0건이 되어 통과해 버리기 때문이다. 메서드 호출 결과에 이어지는
접근(`self.view.get_panel_at(0).foo`)은 반환 타입을 알 수 없어 검사하지 못하며,
그 개수를 실패 메시지에 함께 보고한다 — 검사하지 못한 것을 통과로 위장하지 않는다.

### 3. 결과: 새 결함 0건

147건 전부 존재를 확인했다. spec 적용으로도 새로 깨진 테스트가 없었다.
**S-067의 `set_enabled`가 이 부류의 유일한 사례였다.**

태스크를 쓸 때는 "spec을 붙이면 조용히 통과하던 잘못된 호출이 더 드러날 가능성이
높다"고 적었는데, 실제로는 없었다. 추정이 빗나간 것이므로 그대로 기록한다 —
값어치는 "찾아낸 결함 수"가 아니라 **앞으로 같은 결함이 들어올 수 없게 된 것**에 있다.

### 4. 검사의 실효성 확인

`manual_control_presenter.py`의 호출을 `set_controls_enabled` → `set_enabled`로
되돌리자 정적 검사가 다음과 같이 실패했다.

```
manual_control_presenter.py:125: self.panel.set_enabled — ManualControlPanel에 'set_enabled'이(가) 없다
```

파일·라인·체인·클래스를 모두 짚어 준다. 복원 후 통과를 확인했다.
