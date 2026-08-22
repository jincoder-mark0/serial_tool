# S-017 — UI 갱신 주기 리터럴 30 상수화

- Status: TODO
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

UI 갱신 주기(30ms Throttling)가 상수 `UI_REFRESH_INTERVAL_MS`로 정의되어 있는데
실제 사용처 한 곳이 리터럴 `30`을 하드코딩하고 있다. 값을 바꿀 때 두 곳이 어긋나면
문서(README §1.1 "30ms 주기")·위젯 타이머·프레젠터 타이머가 서로 다른 주기로 돈다.

## 배경 (자족적 설명)

- 수신 데이터는 EventBus를 우회하는 Fast Path로 `DataTrafficHandler`에 도착하고,
  내부 버퍼에 쌓였다가 QTimer가 30ms마다 UI로 일괄 전달된다 (UI Throttling).
- 상수 정의: `common/constants.py:152` — `UI_REFRESH_INTERVAL_MS: int = 30`
- 올바른 사용 예: `view/widgets/data_log.py:36`(import), `:109` `setInterval(UI_REFRESH_INTERVAL_MS)`
- **문제 지점**: `presenter/data_handler.py:56` — `self._ui_refresh_timer.setInterval(30)` (리터럴)

## Steps

1. `presenter/data_handler.py`를 열어 상단 import에 `common.constants`에서
   `UI_REFRESH_INTERVAL_MS`를 추가한다 (기존 import 블록 스타일에 맞출 것 —
   이 파일이 이미 `common.constants`에서 다른 이름을 import하고 있으면 그 줄에 추가).
2. `data_handler.py:56` 부근 `setInterval(30)` → `setInterval(UI_REFRESH_INTERVAL_MS)`로 교체.
   주변 주석("30ms (약 33 FPS)")이 리터럴을 언급하면 상수명 기준으로 자연스럽게 손본다.
3. 다른 곳에 같은 리터럴 하드코딩이 없는지 확인:
   `Grep`으로 `presenter/`·`view/`에서 `setInterval(30)` 검색 — 나오면 같은 방식으로 교체
   (단, 30이 UI 갱신 주기가 아닌 다른 의미면 건드리지 말고 보고만).

## Acceptance criteria (DoD)

- [ ] `presenter/data_handler.py`에 리터럴 `30` 주기 설정이 없다 (상수 사용).
- [ ] `setInterval(30)` 하드코딩이 프로젝트에 남아 있지 않다 (또는 남은 곳의 사유 보고).
- [ ] 전체 pytest 85개 통과.

## 검증 방법

```powershell
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest -q
```
