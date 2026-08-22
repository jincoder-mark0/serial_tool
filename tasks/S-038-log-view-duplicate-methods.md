# S-038 — [P0] 로그 뷰 데이터 표시 파손 (중복 메서드 정의)

- Status: DONE (2026-08-22 — 상위 모델이 발견 즉시 직접 수정. 리팩토링 감사② 산출)
- Recommended model: 상위 (P0 — 즉시 수정)
- 선행: 없음

## 목적 (Why) — 실사용 핵심 기능 파손

`view/custom_qt/smart_list_view.py`의 `QSmartListView`에 **동일 메서드 4개가 두 번 정의**돼
있었다: `append_bytes` / `_should_add_timestamp` / `_create_line_formatter` / `_refresh_all_data`.

- 1차 정의(210~351행): `self._color_rules` + `ColorService.apply_rules(...)`를 쓰는 **정상** 구현.
  `set_color_rules()`가 실제로 채우는 속성과 일치한다.
- 2차 정의(612~750행): `self._color_manager.apply_rules(...)`를 참조하는 **구버전** 구현.
  그런데 `_color_manager`는 `__init__` 어디에도 없다(전 저장소에 대입 코드 0건).

Python은 나중 정의가 앞 정의를 덮으므로, **실제로 실행되는 것은 깨진 2차 정의**였다.

### 실행 검증 (수정 전, 2026-08-22)

```
QSmartListView().append_bytes(b'hello world\n')
→ AttributeError: 'QSmartListView' object has no attribute '_color_manager'
```

기본/타임스탬프/색규칙 주입 세 경로 모두 예외. `append_bytes`는
`view/widgets/data_log.py`의 `flush_buffer`(30ms 타이머)가 수신·송신 바이트마다 호출하는
**유일한 표시 경로**이므로, 실기기·LOOPBACK 어느 쪽이든 **데이터가 화면에 전혀 표시되지
않고**, 전역 excepthook(`core/error_handler.py`)이 데이터가 올 때마다 "Critical Error"
다이얼로그를 띄우는 형태로 나타났을 것이다.

### 왜 테스트 134개가 전부 통과했는가

`QSmartListView`를 다루는 테스트가 **0건**이었다. 캡처 검증도 포트 미연결 상태라
`append_bytes`가 호출되지 않아 드러나지 않았다.

## 조치 (완료)

1. 2차 중복 블록(612~751행) 삭제 — 정답 구현이 이미 같은 파일에 있으므로 위험 없는 수정.
   삭제 후 실행 검증: 세 경로 모두 정상 표시.
2. **회귀 테스트 신설** `tests/test_log_view.py` (5건):
   - 표시 경로 4건(기본/색 규칙/HEX/타임스탬프) — `model().rowCount() > 0` 확인.
   - **`test_no_duplicate_method_definitions`** — AST로 `common/core/model/presenter/view/tools`
     전체를 스캔해 "같은 클래스에 같은 이름 메서드 2회 정의"를 기계적으로 차단
     (property setter/deleter/overload는 정상이므로 제외). 이 유형은 눈 리뷰로 못 잡는다.

## 결과

- 전체 pytest **139 passed** (기준선 134 + 5).
- 중복 정의 스캔 결과 프로젝트 전체에서 이 1건 외 추가 위반 없음.

## 남은 확인 (사용자/실기기)

- 실제 앱에서 LOOPBACK 포트로 데이터 왕복 시 로그 표시 육안 확인 — 자동 검증은 위젯
  단위까지이며, `DataLogWidget.flush_buffer`→`append_bytes` 배선의 실사용 확인은 미실시.
