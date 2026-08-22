# S-051 — DataLogWidget 브로드캐스트 초기값 불일치

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: S-049 (발견 경위)
- Skills to load: task-done

## 목적 (Why) — S-049 특성화 테스트 작성 중 발견 (2026-08-22)

`DataLogWidget` 생성 직후 내부 변수 `tx_broadcast_allowed_enabled`는 `True`인데,
체크박스 위젯은 **unchecked(False)** 로 시작해 둘이 어긋나 있다.

**결과**: 생성 직후 `apply_state({"tx_broadcast_allowed_enabled": False, ...})`를 호출하면
체크박스가 이미 False라 `stateChanged` 신호가 발생하지 않고, 따라서 내부 변수가 갱신되지
않는다 → **상태 저장/복원 왕복이 실패**한다(저장된 False가 True로 되살아난다).

실사용 경로: 앱 시작 시 `lifecycle_manager`가 저장된 설정을 `apply_state`로 복원하므로,
사용자가 TX 브로드캐스트를 끈 채 종료했다면 다음 실행에서 내부적으로는 켜진 상태로
복원될 수 있다(UI 표시와 실제 동작이 어긋난다).

## Steps

1. **현상 재확인**: `view/widgets/data_log.py`에서 `tx_broadcast_allowed_enabled` 초기값과
   체크박스 초기 상태를 확인하고, 위 왕복 실패를 재현하는 테스트를 먼저 작성한다
   (실패하는 것을 확인한 뒤 고친다).
2. **수정 방향 판단**: 둘 중 무엇이 옳은 기본값인지 코드·설정 기본값(`common/defaults.py`,
   `resources/configs/settings.json`의 해당 키)을 확인해 결정하라.
   - 체크박스와 내부 변수의 초기값을 일치시키는 것이 최소 수정이다.
   - 추가로, `apply_state`가 **신호에 의존하지 않고** 내부 변수를 직접 반영하도록 하면
     같은 유형(신호 미발생으로 인한 복원 실패)이 근본적으로 막힌다 — 이 위젯의 다른 필드도
     같은 패턴인지 확인하고 함께 처리할지 판단해 보고하라.
3. 같은 유형의 초기값 불일치가 다른 위젯에도 있는지 확인한다(값-위젯 쌍이 있는 곳).
   범위가 커지면 발견만 보고하고 이 태스크에서는 DataLog만 고친다.

## 검증 방법

- 재현 테스트가 수정 전 실패 → 수정 후 통과.
- 전체 pytest(offscreen, 기준선은 S-049/S-050 커밋 후 값) + 캡처 1회 육안.
- 실제 왕복: `get_state` → 값 반전 → `apply_state` → `get_state`가 반전된 값을 유지하는지.

## Acceptance criteria (DoD)

- [ ] 생성 직후 내부 변수와 체크박스 상태가 일치한다.
- [ ] 저장/복원 왕복이 성공한다(테스트로 고정).
- [ ] 같은 유형의 다른 사례 조사 결과 보고.
