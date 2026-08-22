# 전체 리팩토링 감사 보고서 (2026-08-22)

사용자 지시로 수행한 전면 진단. **읽기 전용 감사 4축**(아키텍처 규칙 / 구조·설계 /
오동작 예상 / 테스트·문서)을 병렬로 돌리고, 상위 모델이 각 지적을 코드·실행으로
재확인해 판정했다. 실행 검증한 항목은 명령과 출력을 함께 남긴다.

기준 시점: 커밋 `16f3cf1`(S-035) 직후. 테스트 기준선 134 → 감사 중 P0 수정으로 139.

## 요약

| 심각도 | 건수 | 대표 |
|---|---|---|
| **P0 (실사용 파손)** | 4 | 로그 뷰 표시 불가(**수정 완료**), TX 큐 유실, write_timeout 무효, 포트 탭 좀비 연결 |
| 높음 | 7 | 파서 설정 무효, SPI 선택 기만, 연결 실패 워커 잔존, 전송 실패 무통보, 커버리지 공백 5모듈 |
| 중간 | 12 | 매크로 종료 알림 비대칭, DataLogger 종료 유실, dead code 3건, DTO 우회, 문서 불일치 다수 |
| 낮음 | 9 | 매직 넘버, 명명 규칙, 중복 코드, 미사용 의존성 |

**깨끗하게 지켜지고 있는 것** (감사에서 위반 0건 확인): 계층 의존 방향 4방향 전부,
워커 스레드의 위젯 직접 접근, SettingsManager 우회 파일 I/O, View↔Model 직결,
Presenter의 위젯 내부 구조 접근(LoD). 구조적 불변식은 견고하다.

---

## A. P0 — 실사용 파손 (즉시 조치)

### A-1. 로그 뷰가 데이터를 전혀 표시하지 못함 ✅ 수정 완료 (S-038, 커밋 0336dcd)

`QSmartListView`에 `append_bytes` 등 4개 메서드가 **두 번 정의**돼 있었고, Python이 나중
정의로 덮으므로 실행되는 쪽은 존재하지 않는 `self._color_manager`를 참조하는 구버전이었다.

```
QSmartListView().append_bytes(b'hello world\n')
→ AttributeError: 'QSmartListView' object has no attribute '_color_manager'
```

`append_bytes`는 `DataLogWidget.flush_buffer`(30ms 타이머)가 수신·송신 바이트마다 호출하는
**유일한 표시 경로**다. 테스트 134개가 전부 통과한 이유는 이 클래스의 테스트가 0건이었고,
캡처 검증은 포트 미연결이라 호출 자체가 없었기 때문.

조치: 중복 블록 삭제 + `tests/test_log_view.py` 신설(표시 경로 4건 + **AST 기반 중복 메서드
정의 차단** — 전 계층 스캔). 스캔 결과 프로젝트에 다른 중복 정의는 없다.

### A-2. close 시 TX 큐 flush 부재 → "전송 성공" 후 데이터 유실

`model/connection_worker.py`의 `run()` 루프는 `while self.is_running():` 조건을 **루프 맨
위에서만** 확인한다. `msleep(1)` 중 `stop()`이 플래그를 내리면 TX 큐를 비우는 블록을 한 번도
통과하지 못하고 `finally`로 빠지며, `finally`는 RX 버퍼만 flush하고 TX 큐는 버린다.
`send_data()`는 큐잉 성공 시점에 이미 `True`를 반환했으므로 호출자는 전송됐다고 믿는다.

**결합 위험**: `model/file_transfer_service.py`는 마지막 청크가 **큐에 들어간 시점**에
`FileCompletionEvent(success=True)`를 발행한다(전선에 나갔는지 확인하지 않음). 전송 완료
직후 포트를 닫는 흔한 운용에서 파일 끝부분이 조용히 유실되고도 "Transfer successful"이 뜬다.

### A-3. `write_timeout=0` — 주석과 실제 동작이 정반대 (실행 검증됨)

`core/transport/serial_transport.py:72`는 `write_timeout=0`으로 열면서 주석에
"전송 실패 시 예외를 전파하여 데이터 유실을 방지"라고 적었다. 그러나 설치된 pyserial 3.5의
Windows 구현은 정반대다:

```
serialwin32.py:315  if self._write_timeout != 0:   # 이때만 GetOverlappedResult로 완료 확인
serialwin32.py:332-334  elif errorcode in (ERROR_SUCCESS, ERROR_IO_PENDING): return len(data)
```

즉 `write_timeout=0`이면 **완료 미확인(IO_PENDING) 상태에서도 성공으로 보고**한다.
RTS/CTS 흐름제어가 켜진 상태에서 상대가 CTS를 내려도 앱은 backpressure를 감지하지 못하고,
`FileTransferService`는 하필 그 설정에서 소프트웨어 스로틀을 꺼버려(`flowctrl in [...]` →
`pass`) 유실 감지가 가장 약해진다.

### A-4. 포트 탭을 닫아도 연결이 끊기지 않음 (좀비 연결)

`view/panels/port_tab_panel.py`의 `close_port_tab()`은 `removeTab()`만 호출하고,
`PortPresenter`는 탭 제거를 구독하지 않는다(`close_connection()` 호출 경로 없음).

재현: COM3 연결 → 탭 추가 → COM3 탭 닫기 → 워커 스레드는 계속 실행, 위젯은 람다가 참조를
붙잡아 잔존 → 새 탭에서 COM3 재연결 시 `is_connection_open()`이 True라 **"Connection is
already open."** 에러. UI에 그 탭이 없으므로 사용자는 재시작 전까지 포트를 되찾을 수 없다.

---

## B. 높음 — 기능이 조용히 거짓말하는 지점

### B-1. 패킷 파서 설정이 통째로 무효 (실행 경로 확인됨)

`model/connection_controller.py:250`이 설정을 무시하고 **항상** `ParserType.RAW`로 파서를
생성한다. Preferences의 Packet 탭(Parser Type/Delimiter/Fixed Length), `packet.parser_type`
설정 키, README의 기능 서술이 모두 존재하지만 **사용자가 무엇을 골라도 반영되지 않고**
AT/Delimiter/FixedLength 파서는 도달 불가 코드다.

### B-2. SPI 선택이 조용히 시리얼로 연결됨

`PortConfig.protocol`과 SPI 전용 필드(`speed`/`mode`), 프로토콜 콤보와 `QStackedWidget`
분기가 갖춰져 "SPI 지원"처럼 보이지만, `open_connection()`은 LOOPBACK 여부만 보고 그 외에는
무조건 `SerialTransport`를 만든다. `config.protocol`을 **읽는 코드가 저장소에 한 곳도 없다**.
SPI를 골라도 경고 없이 시리얼로 연결을 시도한다 — S-015 착수 전에 최소한 명시적 거부가 필요.

### B-3. 연결 실패 워커가 레지스트리에 영구 잔존

`ConnectionWorker.close_connection()`은 `transport.is_open()`일 때만 `connection_closed`를
emit한다. 포트 열기 자체가 실패하면 아무 시그널도 안 나가므로 `controller.workers[name]`에
죽은 워커가 남는다 → `has_active_connection`이 거짓 True, 종료 시 "[COMx] Port closed"라는
오도하는 로그(한 번도 연결된 적 없음).

### B-4. 수동 전송 실패가 사용자에게 전혀 안 알려짐

`_process_and_send()`의 세 실패 경로(HEX 파싱 오류 / 브로드캐스트 대상 없음 / 미연결)가 전부
로그만 남기고 `False`를 반환하는데, 호출부는 반환값을 쓰지 않는다("View에 에러 알림 필요 시
추가 구현" 주석이 미구현 상태). 매크로 경로는 QMessageBox로 알리므로 **비대칭**이다.

### B-5. 커버리지 공백 5모듈 (테스트 0건)

`file_transfer_service`(백프레셔·취소·완료 이벤트), `data_logger`(PCAP `struct.pack` —
틀리면 저장 로그 전체가 조용히 깨짐), `error_handler`(전역 예외 후크 = 마지막 안전망 자체가
무검증), `event_router`(EventBus 구독 로직이 한 번도 실행되지 않아 **토픽 오타를 아무 테스트도
못 잡음**), `theme_manager`+`color_manager`(1300줄).

또한 `tests/test_core_structures.py`는 이름과 달리 `core/structures.py`를 import하지 않아
RingBuffer/ThreadSafeQueue가 완전 무검증이면서 "커버됐다"고 오인시킨다.

---

## C. 중간 — 구조·정합

### C-1. 매크로 종료 알림이 뒤바뀜

`stop()`과 `run()`이 각각 `macro_finished`를 emit해 **수동 정지 시 2회 발생**(UI 이중 리셋).
반대로 **정상 종료 시에는 `MACRO_FINISHED` 이벤트가 한 번도 발행되지 않아** 상태바에
"매크로 종료"가 뜨지 않는다 — 끝까지 실행하면 알림이 없고, 중간에 멈추면 알림이 있다.

### C-2. DataLogger 종료 시 잔여 큐 유실

`stop_logging()`이 `join(timeout=1.0)` 후 타임아웃 여부와 무관하게 파일을 닫는다. 고속 로깅
중지 시 백그라운드 스레드가 쓰는 중인 파일을 메인이 닫아 `ValueError: I/O operation on
closed file` + 잔여 데이터 유실.

### C-3. Dead code 3건 (전수 grep으로 무참조 확인)

- `model/connection_manager.py`(119줄) — 어디서도 import 안 됨. **README는 "연결 인스턴스
  관리" 활성 기능으로 나열**. S-015 작업자가 "이미 있는 확장점"으로 오인할 함정.
- `view/widgets/packet.py`(131줄) — `__init__`에서 재수출만 되고 인스턴스화 0건.
  실제 패킷 뷰는 `view/panels/packet_panel.py`의 별개 구현.
- `common/enums.py` `MacroStepType` — 참조 0건.

### C-4. DTO/enum 우회

- 매크로 스크립트 로드가 `MacroScriptData` DTO를 두고도 raw `dict`로 Worker→Presenter→View
  통과 (`presenter/macro_presenter.py:55,215,224`).
- `model/file_transfer_service.py:161`이 `SerialFlowControl` enum 대신 `["RTS/CTS","XON/XOFF"]`
  문자열 리터럴 비교 — 오타 시 조용히 실패.

### C-5. 설정 기본값 파일이 개발자 세션으로 오염

`resources/configs/settings.json`은 "배포 기본값 원본"인데 커밋된 내용에 개발자 개인 경로
(`C:\Users\lkj01\Desktop\Serial_Tool` — **사용자명 노출**), 창 위치·splitter 블롭, 매크로 테스트
입력(`"zx\nzc\nz\nzc\n"`)이 들어 있다. 근본 원인은 **개발 모드가 이 파일에 직접 쓰기** 때문
(S-013은 번들 모드만 분리) — 커밋할 때마다 반복 오염된다.

### C-6. 이벤트 채널 이중화 (상위 판정: 문서 정밀화)

`connection_closed` 하나가 EventBus(→EventRouter→MainPresenter) + 직접 시그널 2곳
(`port_presenter`, `manual_control_presenter`)으로 소비된다. 추적한 결과 **중복 처리가 아니라
서로 다른 관심사의 팬아웃**이라 오동작은 아니다.

→ **판정**: 실제 설계("소유 관계가 명확한 1:1/1:N은 Qt 직접 시그널, 계층을 건너뛰는 팬아웃은
EventBus")가 합리적이다. Qt 시그널을 버스로 강제 우회시키면 타입 안정성과 수명 관리 이점을
잃는다. **코드가 아니라 CLAUDE.md 문언("예외는 단 하나")을 실제 설계에 맞게 정밀화**한다.

### C-7. God object / 중복 코드

- `ThemeManager`(833줄): 팔레트·아이콘 탐색·테마 파일 스캔·폰트·QSS 로드·216줄 폴백 QSS 생성.
  `color_manager`와 **함수-지역 import로 순환 참조**를 우회 중(주석이 스스로 인정).
- `MainPresenter`(632줄): 설정 DTO 조립/해체, 종료 상태 수집, 이벤트 브로드캐스트, 매크로
  라우팅, 로깅 포맷 결정 등 5~6개 관심사.
- `DataLogWidget` ↔ `SystemLogWidget`: 검색바·필터·REC 버튼이 150~200줄 중복이면서 제어
  흐름은 반대(전자는 Presenter 권위, 후자는 위젯 자기 권위).
- 싱글톤 4종 중 `SettingsManager`/`EventBus`만 테스트 리셋 장치가 있고
  `ThemeManager`/`ColorManager`/`LanguageManager`는 없다 → 순서 의존 오염 잠재.

---

## D. 낮음 — 정리 대상

- **매직 넘버**: 필터 디바운스 300ms(`smart_list_view`), 상태바 갱신 1000ms(`lifecycle_manager`),
  backpressure 10ms(`file_transfer_service`), 다이얼로그 크기·버튼 폭 다수.
- **명명 규칙**: `_edit` 접미사 6곳(가이드에 없는 형태). 특히
  `view/dialogs/preferences_dialog.py:218`은 **QLabel을 `log_path_edit`로 명명**해 타입을 오도.
  언어 키에도 규격 외 `edit` 토큰 6개.
- **`.agent/rules/naming_convention_guide.md`의 언어 키 Context 표가 실제와 완전 불일치** —
  표의 `rx`/`manual_ctrl`/`file_prog`/`inspector`/`system`/`toolbar`/`status` 중 실제 코드에
  존재하는 것이 **하나도 없다**. 도구 경로도 오기(`manage_lang_keys.py` → `manage_language_keys.py`).
- **미사용 의존성**: `requirements.txt`의 `requests`, `qdarkstyle` 사용처 0건(README 요구사항
  목록에는 아예 없어 두 문서가 서로 다름).
- **lint 부재**: ruff/mypy 설정이 프로젝트에 아예 없다. C-3의 dead code나 미사용 의존성은
  lint가 있었으면 잡혔을 유형.
- **문서-코드 불일치**: `doc/task.md`가 이미 완료된 AutoTx·벤치마크·패키징·CI를 미완료로 표기
  (Task.MD가 스스로 정한 "완료 시 doc/task.md 반영" 절차 미이행), `doc/00_overview.md`가
  완료된 설정 분리를 "필요합니다"로 서술, README 구조도에 `loopback_transport.py` 누락 및
  기능 목록에 LOOPBACK 미기재, README 설정 예시에 `version` 키 누락(실제 스키마는 1.3 필수).
- **검증 도구 사각지대**: `check_language_keys`는 en/ko 대칭과 `[TODO]`만 본다 — **코드가
  참조하는 키가 JSON에 실재하는지 검증하지 않아** 오타 키가 런타임에 조용히 폴백된다.
  플레이스홀더 개수 불일치(`.format` IndexError)도 미검출. `test_ui_guidelines`의 한글 스캔은
  `view/`·`presenter/`만 대상이라 `model/`·`core/`는 사각지대.
- **패킷 뷰 무스로틀**: `packet_presenter.py:134`가 패킷 1건마다 즉시 UI 반영(30ms 버퍼 미적용).
  RX raw와 성격이 달라 즉시 결함은 아니나 고속 환경 미검증.

---

## 조치 계획

| 태스크 | 대상 | 우선 |
|---|---|---|
| [S-038](../tasks/S-038-log-view-duplicate-methods.md) ✅ | 로그 뷰 파손 (A-1) | P0 완료 |
| [S-039](../tasks/S-039-tx-data-loss.md) | TX 큐 flush + write_timeout (A-2, A-3) | P0 |
| [S-040](../tasks/S-040-port-tab-close-cleanup.md) | 포트 탭 좀비 연결 (A-4) | P0 |
| [S-041](../tasks/S-041-parser-and-protocol-wiring.md) | 파서 설정 무효 + SPI 기만 (B-1, B-2) | P1 |
| [S-042](../tasks/S-042-silent-failures.md) | 워커 잔존·전송 실패 무통보·매크로 알림 (B-3, B-4, C-1) | P1 |
| [S-043](../tasks/S-043-settings-pollution.md) | 설정 기본값 오염 차단 (C-5) | P1 |
| [S-044](../tasks/S-044-dead-code-and-dto.md) | dead code 3건 + DTO/enum 우회 (C-3, C-4) | P2 |
| [S-045](../tasks/S-045-test-coverage-gaps.md) | 커버리지 공백 5모듈 + DataLogger 종료 (B-5, C-2) | P2 |
| [S-046](../tasks/S-046-docs-and-rules-sync.md) | 문서·규칙 정합 일괄 (C-6 판정 반영, D 문서군) | P2 |
| S-047 (미작성) | 매직 넘버·명명 규칙·lint 도입 (D) | P3 |
| S-048 (미작성) | 싱글톤 테스트 격리, 언어 키 사용처 검증 도구 (C-7, D) | P3 |
| S-049 (미작성) | God object 분해·로그 위젯 공통화 (C-7) | P3 |

**원칙**: P0/P1은 "조용히 틀린 결과를 내는" 것들이라 먼저 없앤다. 구조 개선(God object 분해,
중복 공통화)은 회귀 위험이 크므로 **커버리지 공백(S-045)을 메운 뒤** 착수한다 — 지금 상태에서
`ThemeManager`를 쪼개면 그 변경을 검증할 테스트가 없다.
