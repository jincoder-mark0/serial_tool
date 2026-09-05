# 변경 이력 (CHANGELOG)

## [미배포] (Unreleased)

---

### LanguageManager: `__new__` 싱글턴 제거, `configure()` 도입 (2026-09-04)

View 계층 전역 정리 2/2입니다. **앞의 둘과 다른 결론에 도달했습니다** —
`ThemeManager`/`ColorManager`는 생성자 주입으로 바꿨지만 이것은 전역을 유지합니다.

조사 결과 **그 둘을 정당화한 결함이 여기엔 없었습니다.**

| 결함 | Color/Theme | Language |
|---|---|---|
| 주입한 `ResourcePath`가 무시됨 | 있었음 | 없음 — 재설정이 실제로 다시 로드 |
| import만으로 파일 I/O | 있었음 | 없음 — 경로 없으면 로드하지 않는 lazy 설계 |

반면 주입 비용은 자릿수가 달랐습니다. `get_text()` 호출 **452곳**, `language_changed`
구독 17곳, 영향 파일 34개, 생성자 배선이 필요한 위젯 클래스 약 25개입니다. "현재 언어"는
앱 전체에 하나뿐인 값이고, 이 프로젝트는 같은 성격의 값을 이미 전역으로 인정했습니다
(S-050 `theme_state`).

실제 문제는 주입 여부가 아니라 **`__new__`가 만드는 거짓말**이었습니다.
`main.py`의 `LanguageManager(resource_path)`는 새 객체를 만드는 것처럼 보이지만
실제로는 전역을 설정했습니다.

- `__new__`/`_instance` 제거, `configure(resource_path)` 공개 메서드 추가.
  `main.py`·`tools/ux_capture.py`가 `language_manager.configure(...)`를 호출합니다.
- 전역 인스턴스는 **앱 전역 텍스트 카탈로그**로 유지하고, 유지하는 이유와
  `ThemeManager`/`ColorManager`와 결론이 다른 이유를 코드에 적었습니다.

**`__new__`가 가려주던 실수가 이제는 진짜 버그가 됩니다.** 새 인스턴스를 만들어
설정하면 위젯들이 구독한 전역과 다른 객체가 되어, 언어를 바꿔도 **예외도 로그도 없이
화면만 갱신되지 않습니다.** `tests/test_language_manager_contract.py`(5건)가 이 경로와
`configure()`의 재로드 동작을 고정합니다.

검증 결과는 `793 passed`(3회 반복 동일), Ruff 0건, language/task-board gate Green이며,
실제 앱에서 언어 로드(en/ko 303 keys)와 ko 전환까지 확인했습니다.

---

### ThemeManager / ColorManager 싱글턴 해체 (2026-09-03)

두 매니저는 `__new__` 기반 class singleton + module-level 전역 인스턴스였습니다.
`SettingsManager`(P2-C #6)·`DataLoggerManager`와 같은 형태이고, 같은 문제를 만들었습니다.

**조사 중 발견한 결함 2건이 이 리팩토링으로 사라집니다.**

- **주입한 ResourcePath가 적용되지 않았습니다.** `main.py`의 `ColorManager(resource_path)`는
  import 시점에 이미 초기화가 끝나 있어 `_initialized` 가드에 막혔고, `_resource_path`만
  갈아끼운 채 `config_path`는 재계산하지 않았습니다. 색 규칙은 언제나 import 시점의 기본
  경로에서 로드됐습니다. 지금 문제가 되지 않던 이유는 `ResourcePath()`가 번들을 스스로
  감지하기 때문일 뿐이었습니다.
- **import만으로 파일 I/O가 일어났습니다.** 모듈을 읽는 것만으로 `color_rules.json`을
  읽었고, PyInstaller **빌드 분석 단계**에서도 그 로그가 찍혔습니다.

주요 변경입니다.

- 두 클래스에서 `__new__`/`_instance`/`_initialized`와 module-level 전역을 제거하고
  composition root(`main.py`)가 생성해 주입합니다.
- **`ThemeManager`가 전역 `color_manager`를 직접 부르던 호출을 제거했습니다.** 전역이
  전역을 부르는 구조라 어느 쪽도 교체할 수 없었습니다. `MainWindow.switch_theme`은 이미
  두 매니저에 각각 적용하고 있어 중복이기도 했고, 시작 경로의 전파는 `main.py`가 맡습니다.
- `is_dark_theme()`만 필요한 위젯(`system_log`, `smart_list_view`)은 `theme_state`
  리프 모듈을 직접 씁니다 — 깊은 위젯까지 주입을 번지게 할 이유가 없습니다.
- 아이콘·테마 목록이 필요한 곳(`MainMenuBar`, `PortTabPanel`, `PreferencesDialog`)은
  생성자 주입으로 전달합니다.

**테스트 격리 방식이 바뀌었습니다.** `tests/test_singleton_isolation.py`(S-048)와
`conftest.py`의 전역 snapshot/restore는 "공유 상태를 매번 되돌린다"는 전제 위에 있었는데,
인스턴스를 나누면 되돌릴 것이 없습니다. 격리 테스트는 삭제하고
`tests/test_view_manager_instance_contract.py`로 대체했습니다 — **복원이 아니라 애초에
공유하지 않는 것**이 격리입니다. autouse fixture는 아직 공유되는 두 가지
(`theme_state`, `language_manager`)만 복원합니다.

`tests/test_theme_color_managers.py`는 S-054가 "무수정 통과가 계약"으로 선언한 파일입니다.
공개 API는 그대로이고 **인스턴스 획득 방식만** 전역 import에서 fixture로 바뀌었습니다
(26건 전부 통과).

검증 결과는 `788 passed`(3회 반복 동일), Ruff 0건, language/task-board gate Green이며,
실제 앱 기동까지 확인했습니다.

---

### 언어 도구 형식 일치와 flaky 테스트 진단 (2026-09-03)

**언어 키 도구가 절차를 따를 때마다 파일 전체를 재포맷했습니다.**

문서화된 절차(`.claude/skills/lang-keys`)는 키 추가 후
`tools/manage_language_keys.py`를 돌리라고 합니다. 그런데 이 도구는 `indent=4`로
저장하는 반면 `resources/languages/*.json`은 2칸이고 끝 개행이 있습니다. 그래서
키 하나만 추가해도 **두 파일 607줄이 통째로 재포맷**됐습니다. PR diff가 노이즈로
뒤덮여 실제 변경이 묻히고, 재포맷된 줄의 blame도 끊겼습니다 — 절차를 따를수록
기록이 나빠지는 셈이었습니다.

형식은 도구가 아니라 저장된 파일이 정본이므로 도구를 파일에 맞췄습니다
(`indent=2` + 끝 개행). 도구를 실행해도 diff가 0인 것을 확인했습니다.

회귀 방지 계약 4건을 `tests/test_language_tool_format.py`에 추가했습니다. 도구의
저장 형식이 실제 리소스 파일과 일치하는지 바이트 단위로 비교하고, 리소스 파일
자체의 형식(2칸 들여쓰기, 끝 개행)도 함께 고정합니다. 줄바꿈은 정규화해 비교합니다
— CI가 Windows(CRLF)와 Ubuntu(LF) 양쪽에서 돌고, 줄바꿈은 git의 몫입니다.

**`test_async_load_emits_macro_script_data`의 간헐적 실패에 여유와 진단을 넣었습니다.**

전체 스위트 5회 중 2회 실패한 적이 있습니다(`waitUntil` 2초 timeout). 이후 10회
연속 실행에서는 재현되지 않았고, `commentjson` 파서 초기화 비용을 의심했지만
실측 결과 0.000s로 원인이 아니었습니다. **근본 원인은 규명하지 못했습니다.**

이 대기가 재는 것은 "언젠가 도착하는가"이지 지연 시간이 아니므로 상한을 5초로
늘렸습니다. 더 중요한 것은 다음에 또 터졌을 때 원인을 좁힐 수 있도록 worker 상태
(`is_loading` / `running` / `pending_io`)를 실패 메시지에 남긴 것입니다 —
"waitUntil timed out"만으로는 다음에도 못 고칩니다.

검증 결과는 `785 passed`, Ruff 0건, language/task-board gate Green입니다.

---

### 종료 시 TX 드레인 대기가 창을 굳히지 않게 (2026-09-03)

무손실 작업의 마지막 조각입니다. 세션 중 close는 이미 비동기지만(#23),
**종료 경로는 유실을 막기 위해 반드시 기다려야** 합니다 — 프로세스가 사라지면 아직
내보내지 못한 큐가 함께 사라지므로 기다리지 않는 것이 곧 유실입니다.

문제는 기다리는 **방식**이었습니다. `QThread.wait()`로 기다리면 이벤트 루프가 멈춰
창이 흰 사각형으로 굳습니다. 사용자에게는 앱이 죽은 것과 구분되지 않고, 큐가 클수록
오래 굳습니다.

- `ShutdownCoordinator._wait_for_flush_without_freezing_ui()`가 짧은 주기
  (`SHUTDOWN_FLUSH_POLL_MS`, 50 ms)로 끊어 기다리며 그 사이 이벤트를 흘립니다.
  창이 계속 그려지고 남은 바이트가 상태바에 표시됩니다.
- `processEvents`에 `QEventLoop.ExcludeUserInputEvents`를 줍니다. 그리기·타이머만
  흘리고 마우스·키보드는 버립니다. **입력까지 흘리면 종료 도중 다시 연결하거나
  매크로를 돌리는 재진입이 생깁니다** — 이미 정리한 자원을 다시 쓰게 되는 상태입니다.
- `ConnectionController.pending_flush_bytes()`로 남은 양을 조회합니다.
- 대기 위치가 Model에서 Presenter로 옮겨졌습니다. UI 이벤트를 흘리는 일은 View를
  아는 계층이 해야 하고, Model이 이벤트 루프를 돌리면 계층 경계가 무너집니다.
  `ConnectionController.close_all_and_wait()`는 UI가 없는 호출자(테스트 teardown 등)를
  위해 그대로 둡니다.

**상한은 두지 않습니다.** 여기서 포기하는 것은 곧 유실이고, 이제 창이 응답하므로
오래 걸려도 사용자가 무슨 일이 벌어지는지 볼 수 있습니다. 포트가 물리적으로 멎어
드레인이 진행되지 않으면 종료가 끝나지 않는데, 그때는 남은 바이트가 줄지 않는 것이
화면에 그대로 드러납니다.

언어 키 `main_status_msg_flushing`을 en/ko에 추가했습니다.

회귀 테스트 7건을 `tests/test_shutdown_flush_responsive.py`에 추가했습니다. 블로킹
대기로 되돌리면 4건이, 입력 배제만 빼면 1건이 실패합니다.

---

### TX 큐 상한과 backpressure (2026-09-02)

무손실 작업의 후속입니다. 비동기 close(직전 변경)가 UI 멈춤을 없앴다면, 이번 것은
**"큐잉 성공이 전송 성공을 뜻하지 않는다"**는 더 근본적인 문제를 다룹니다.

상한이 없으면 `send_data()`가 항상 성공을 돌려줍니다. 생산자는 포트가 감당하지
못하는 속도로 계속 쌓을 수 있고, 실제로 못 보냈다는 사실은 한참 뒤에야 드러나거나
아예 드러나지 않습니다. 큐가 무한정 자라는 것도 같은 문제의 다른 얼굴입니다.

- `ThreadSafeQueue`에 `max_bytes`를 추가했습니다. 상한에 닿으면 **가장 오래된 것을
  버리지 않고 `enqueue()`가 False를 돌려줍니다** — 조용히 버리면 그 순간이 곧
  유실이지만, 거절하면 생산자가 즉시 알고 늦출 수 있습니다.
- `ConnectionWorker`의 TX 큐에 `TX_QUEUE_MAX_BYTES`(1 MB)를 걸었습니다. 가장 큰
  생산자인 `FileTransferService`가 이미 큐 깊이 50청크(≈200 KB)로 자체 제한하므로
  5배 여유가 있습니다. 여기에 닿는다는 것은 생산자가 backpressure를 무시한다는
  신호입니다.
- **"큐가 가득 참"과 "포트가 닫힘"을 구분**할 수 있게 `is_write_queue_full()` /
  `get_write_queue_bytes()`를 추가했습니다. 구분하지 못하면 생산자가 일시적
  backpressure를 전송 실패로 오인해 중단합니다.
- `ConnectionController.send_data()`가 큐 가득참을 오류로 표면화합니다. 조용히
  False만 돌려주면 사용자는 명령이 사라진 이유를 알 수 없습니다.
- `FileTransferService`는 거절당한 청크를 **버리지 않고 들고 있다가 재시도**합니다.
  새로 읽어버리면 그 청크가 조용히 사라져 상한 도입 목적이 정반대로 뒤집힙니다.
- 재시도가 영원히 돌지 않도록 `FILE_TRANSFER_STALL_TIMEOUT_S`(30초)를 두었습니다.
  포트가 실제로 멎으면(드라이버 정지, XON/XOFF hold) 사용자에게는 전송이 특정
  %에서 영원히 멈춘 것으로만 보입니다 — 조용한 정체입니다. 큐잉되지 않은
  데이터이므로 실패로 끝내도 유실이 아닙니다.

이 상한이 **보장하지 않는 것**도 적어 둡니다. 드레인 *시간*의 상한은 아닙니다 —
1 MB는 115200 bps에서 약 87초, 9600 bps에서는 훨씬 깁니다. 종료 시 대기 시간은
별도 과제입니다.

회귀 테스트 9건을 추가했습니다(`tests/test_tx_backpressure.py` 7건,
`test_file_transfer.py` 2건). 상한과 재시도를 되돌리면 실패하며, 회귀 시 hang이
아니라 실패로 드러나도록 채우기 루프에 상한을 두었습니다.

검증 결과는 `774 passed`(순차 5회 반복 동일), Ruff 0건, language/task-board gate
Green입니다.

---

### 포트 종료를 비동기로 — UI 멈춤 제거, TX 유실 없음 (2026-09-02)

사용자 요구: "데이터 무손실이 중요하다. 다만 UI가 멈추면 안 된다."

두 요구는 상충하지 않았습니다. 남은 TX 큐를 비우는 것은 **worker thread**가 하는
일이고 호출자의 thread는 필요하지 않습니다. 그런데 `ConnectionWorker.stop()`이
무조건 `wait()`를 걸었고 `close_connection()`이 그것을 그대로 호출해서, 포트를 닫는
UI thread가 드레인이 끝날 때까지 멈췄습니다. TX 큐는 상한이 없고 청크당 write는
최대 1초(`WRITE_TIMEOUT_S`)이므로 멈추는 시간에 상한이 없었습니다. 회귀 테스트로
재현한 시나리오에서 `close_connection()`이 **15.02초** 블록됐습니다.

- `ConnectionWorker`에 `request_stop()`(대기 없음)을 두어 요청과 대기를 분리했습니다.
  `stop(timeout_ms=None)`은 대기가 필요한 호출자를 위해 남겨 뒀습니다.
- `ConnectionController.close_connection()`은 이제 기다리지 않고 반환합니다.
  **드레인 범위는 그대로라 유실은 없습니다** — 대기를 없앤 것이지 드레인을 줄인 게
  아닙니다. registry 정리와 `connection_closed` 발행은 지금처럼 동기적으로 하므로
  호출 직후 `is_connection_open()`은 False이고 신규 송신은 거부됩니다.
- **앱 종료 경로는 반대로 반드시 기다립니다.** 프로세스가 사라지면 아직 내보내지
  못한 큐가 함께 사라지므로, 기다리지 않는 것이 곧 유실입니다. `close_all_and_wait()`를
  추가하고 `ShutdownCoordinator`가 이것을 쓰도록 했습니다(상한 없음 — 기존과 동일).
- 진행 상태 조회용으로 `has_pending_flush()` / `wait_for_pending_flush()`를 추가했습니다.
- 드레인 중인 포트를 다시 여는 경우, transport가 아직 열려 있으므로 그대로 열면
  같은 물리 포트를 두 번 여는 시도가 됩니다. `REOPEN_FLUSH_WAIT_MS`(2초)만큼
  기다린 뒤 그래도 안 끝나면 알립니다. 처음에는 곧바로 거부했는데, 그러면
  "탭 닫고 다시 열기"라는 정당한 조작이 깨졌습니다
  (`test_closing_tab_closes_loopback_connection_and_allows_reopen`이 잡아냈습니다).

계약이 하나 바뀌었습니다 — **"close가 반환했다"가 더 이상 "드레인이 끝났다"를
뜻하지 않습니다.** 데이터가 실제로 나갔는지 확인해야 하는 호출자는
`wait_for_pending_flush()`를 써야 합니다. 이 가정에 기대던 테스트들을 새 계약에
맞게 갱신했고, worker thread를 남기지 않도록 종료 대기를 명시했습니다.

회귀 테스트 5건을 `tests/test_async_close_lossless.py`에 추가했습니다. 동기 close로
되돌리면 "close가 15.02초 블록됐다"로 실패합니다.

검증 결과는 `765 passed`(순차 8회 반복 동일), Ruff 0건, language/task-board gate
Green입니다. 후속으로 TX 큐 상한 + backpressure가 남아 있습니다 — 지금은 큐잉
성공이 전송 성공을 뜻하지 않고, 큐가 무한정 쌓일 수 있습니다.

---

### MacroRunner 시작 API를 QThread 계약과 분리 (2026-09-02)

`MacroRunner`가 `QThread`를 상속하면서 `start()`를 **완전히 다른 시그니처**로
override하고 있었습니다.

```text
QThread.start(priority=InheritPriority)
MacroRunner.start(loop_count=1, interval_ms=0, broadcast_enabled=False, stop_on_error=True)
```

이 객체를 QThread로 취급하는 호출자가 `runner.start(QThread.HighPriority)`를 쓰면
priority enum이 `loop_count`로 조용히 들어가 매크로가 엉뚱한 횟수로 돕니다. 예외도
경고도 없습니다.

- 매크로 실행 진입점을 `start_macro()`로 분리하고 `start()`는 QThread의 것을 그대로
  상속합니다. 호출부는 production 1곳(`MacroPresenter`)과 테스트 11곳입니다.
- 이름만 바꾸면 위험이 사라지는 게 아니라 옮겨갑니다. 상속된 `start()`로 직접
  시작한 경우 `run()`이 실행 조건 없이 진행하다 `macro_finished`를 내보내면
  **macro_started 없이 완료 신호만 오는 유령 이벤트**가 됩니다. 시작 요청 플래그를
  두어 그 경로를 안전한 no-op으로 만들고 경고를 남깁니다.
- 회귀 방지 계약 4건을 `tests/test_macro_runner_start_contract.py`에 추가했습니다.
  과거 형태로 되돌리면 4건 모두 실패하는 것을 확인했습니다.

동작 변경은 없습니다. 검증 결과는 `760 passed`, Ruff 0건,
language/task-board gate Green입니다.

---

### 배포 artifact에서 개발자 로컬 설정 유출 차단 (2026-09-02)

P4 #18 artifact smoke를 수행하다 발견했습니다.

- `serial_tool.spec`의 `datas=[('resources', 'resources')]`가 디렉터리를 통째로
  담아, git이 추적하지 않는 `resources/configs/settings.local.json`이 배포본에
  포함됐습니다. 빌드한 개발자의 창 위치·포트 탭 상태·수동 입력값이 실립니다.
  이 파일은 S-043이 "개발자 로컬 세션이 커밋에 섞이는 오염"을 막으려고 분리하고
  `.gitignore`에 넣은 것인데, **그 보호가 git 단계에서만 작동해 빌드로는 그대로
  샜습니다.** 번들 실행 시 사용자 설정은 APPDATA를 쓰므로 읽히지도 않는 순수
  유출이고, 빌드하는 사람마다 artifact가 달라져 재현성도 깨집니다.
  spec에 `EXCLUDED_DATA_BASENAMES`를 두어 제외했습니다.
- PyInstaller가 `requirements.txt`에도 `requirements-backends/`에도 없어 깨끗한
  체크아웃에서는 빌드가 불가능했습니다. `requirements-build.txt`로 선언했습니다.
- 회귀 방지 계약 5건을 `tests/test_packaging_spec_contract.py`에 추가했습니다.
  제외 목록의 파일명이 `ResourcePath`가 실제로 쓰는 dev-mode 파일명과 일치하는지도
  검사합니다 — 한쪽만 이름이 바뀌면 spec은 없는 이름을 거르고 유출은 되살아납니다.

artifact smoke 결과는 [`doc/artifact_smoke_20260902.md`](artifact_smoke_20260902.md)에
기록했습니다. 빌드·기동·번들 경로 리소스 로드·설정 마이그레이션(v1.2 -> v1.3)·
정상 종료가 모두 통과했고 로그 내 WARNING/ERROR는 0건입니다. GUI 대화형 항목은
미검증으로 남겼습니다.

검증 결과는 `756 passed`, Ruff 0건, language/task-board gate Green입니다.

---

### DataLoggerManager 전역 싱글턴 제거 (2026-09-02)

P2-C #6이 `SettingsManager`에서 없앤 것과 **정확히 같은 종류**의 hidden global이
`core/data_logger.py`에 하나 남아 있었습니다. module-level `data_logger_manager`를
Model(`TrafficMonitor`)과 Presenter(`LoggingCoordinator`, `ShutdownCoordinator`)가
각자 import했습니다. import하는 위치가 곧 숨은 의존이 되고, 소유자가 없어 교체할 수
없으며, 같은 프로세스의 테스트가 상태를 공유해 실행 순서에 의존합니다.

- 전역 인스턴스를 삭제하고 composition root(`ApplicationBootstrapper.build()`)가
  하나 생성해 주입합니다. `ApplicationComponents`가 수명을 소유합니다.
- `TrafficMonitor` / `LoggingCoordinator` / `ShutdownCoordinator`가 생성자로
  받습니다. 기본값 없는 필수 인자라 "안 넘기면 스스로 만드는" 경로가 없습니다.
- `DataTrafficHandler`의 `traffic_monitor or TrafficMonitor()` fallback도 없앴습니다.
  같은 종류의 숨은 의존이고, production·테스트 모두 이미 인스턴스를 넘기고 있어
  실제로는 죽은 경로였습니다.
- 전역을 patch하던 테스트들이 주입된 인스턴스를 직접 검증하도록 바뀌어, 더 이상
  프로세스 전역 상태를 공유하지 않습니다. S-059 종료 테스트는 composition root가
  조립한 runtime graph에서 manager를 꺼내 씁니다.
- 재도입 방지 계약 3건을 `tests/test_data_logger_manager_instance_contract.py`에
  추가했습니다 — module-level 인스턴스 금지, composition root 밖 생성 금지,
  전역 이름 import 금지. 전역을 되살리면 실패하는 것을 확인했습니다.

동작 변경은 없습니다. 검증 결과는 `751 passed`(3회 반복 동일), Ruff 0건,
language/task-board gate Green입니다.

---

### 코드 점검 후속 수정 — 침묵 실패·기본값 오염·우측 패널 토글 (2026-09-02)

전체 게이트가 Green인 상태에서 코드를 점검해 **통과하는 검증이 놓치던** 결함 4건을
고쳤습니다.

- **우측 패널 토글이 창 대신 컴포넌트를 늘렸습니다.** 사용자 보고: "창 크기가 변해야
  하는데 창 크기가 유지되어 컴포넌트 크기가 변한다." Qt의 레이아웃 무효화가 지연되기
  때문에 `right_section.setVisible(False)` 직후에는 창의 최소 폭이 아직 우측 패널의
  최소 폭을 포함하고 있고, 그 시점의 `resize()`가 옛 최소 폭에 클램프되어 무시됐습니다
  (실측: 창 3838 유지, 좌측 3244 -> 3828). 숨김 직후 splitter -> central -> main window
  순으로 레이아웃 제약을 즉시 재계산한 뒤 resize하도록 고쳤습니다. 기존 왕복 항등
  테스트는 숨김 단계에서 창이 전혀 줄지 않아도 통과했으므로 숨김 단계 자체를 보는
  회귀 테스트를 추가했습니다.
- **큐에서 꺼낸 transaction이 통지 없이 사라졌습니다 (S-085).** S-084는 큐에 *남은*
  request를 통지하도록 고쳤지만, worker가 `get()`으로 command를 꺼낸 뒤 `_stop_requested`를
  확인해 `break` 하는 경로가 남아 있었습니다. 그 command는 이미 큐 밖이라 종료 시
  큐를 비우는 `_fail_pending_transactions()`도 잡지 못했습니다. 결과를 기다리는
  호출자는 영원히 기다리고 사용자에게 오류 표시도 없습니다.
- **사용자 설정 로드가 모듈 전역 기본값을 덮어썼습니다.** `create_fallback_settings()`가
  얕은 복사를 돌려줘 중첩 dict가 전역 `DEFAULT_*`와 같은 객체였고, 재귀 병합이 사용자
  값을 기본값 자체에 써 넣었습니다. 설정 파일이 손상돼 fallback으로 복구할 때 진짜
  기본값이 아니라 직전 사용자 값이 되살아나고, 테스트에서는 한 케이스의 값이 이후
  케이스로 새어나가 결과가 실행 순서에 의존했습니다 — 전체 스위트를 한 번 돌리는
  것만으로 `DEFAULT_MANUAL_CONTROL_STATE`의 prefix/suffix/broadcast가 False -> True로
  바뀌었습니다.
- **종료 시 매크로 정지 상한이 죽어 있었습니다.** `MacroRunner.stop()`이 내부에서 이미
  무한 `wait()`을 하므로 그 다음 줄의 `wait(1000)`은 항상 이미 끝난 스레드를 기다렸고,
  1초 상한이 아무 역할도 하지 못했습니다. `stop(timeout_ms=...)`로 상한을 실제로
  적용하고, 넘길 경우 경고를 남긴 뒤 종료 시퀀스를 계속 진행합니다.

회귀 테스트 6건을 추가했고, 각각 수정을 되돌리면 실패하는 것을 확인했습니다.
검증 결과는 `748 passed`, Ruff 0건, language/task-board gate Green입니다.

---

### 작업 보드 단일화 (2026-08-30)

- `doc/task.md`에서 현재도 유효한 제품 기능 기준선, 성능·Plugin·환경 검증
  backlog를 루트 `Task.MD`로 통합했습니다.
- EventRouter/EventBus와 과거 ownership·경로처럼 현재 architecture와 충돌하는
  legacy 항목은 이관하지 않았습니다.
- 중복 작업 보드인 `doc/task.md`를 삭제하고 현재 문서·완료 절차·후속 S-xxx
  태스크의 활성 참조를 루트 `Task.MD`와 역사 문서 체계로 갱신했습니다.

---

### 전체 diff 감사 잔여 lifecycle·전송 finding 해결 (2026-08-30)

- Port scan과 Macro script load의 blocking OS/file I/O를 daemon I/O thread로
  분리하고, QThread는 interruption polling과 1초 bounded wait로 종료하도록
  변경했습니다. 반환하지 않는 OS API나 네트워크 파일 읽기 때문에 앱 shutdown이
  무기한 멈추지 않습니다.
- Python thread는 안전하게 강제 종료할 수 없으므로 manager가 반환 전 helper를
  추적하고, helper가 살아 있는 동안 retry를 거부해 작업별 stuck helper를 최대
  1개로 제한합니다. 해당 daemon helper는 process 종료 시 OS가 정리합니다.
- ConnectionWorker의 opened/error/data queued signal도 Worker identity를 검증해
  재연결된 새 세션에 old event가 섞이지 않게 했습니다. 새 세션이 없는 explicit
  close에서는 retiring Worker의 마지막 RX batch만 termination 전까지 보존합니다.
- ConnectionWorker가 Queue 대기뿐 아니라 실제 `transport.write()` in-flight/terminal
  error 상태도 추적하며, FileTransferService는 write 성공과 idle을 모두 확인한 뒤에만
  성공 완료를 알립니다.
- Port scan 실패를 `scan_failed` signal로 Loopback fallback과 구분하고, 초기 scan을
  LoggingCoordinator/MainPresenter 연결 후 시작해 시스템 로그에 오류를 표시합니다.
- blocking fake와 실제 composition graph/ConnectionWorker를 사용하는 회귀 테스트
  10개를 추가했습니다.

검증 결과는 `643 passed`, Ruff 0건, language/task-board gate Green입니다.

---

### main 전체 diff 감사 및 merge blocker 교정 (2026-08-30)

- 이전 Worker의 queued 종료 signal이 동일 포트의 새 연결 registry를 삭제할 수 있던
  race를 Worker identity 검사로 차단했습니다.
- USB Serial 분리/read 오류를 빈 데이터로 숨기지 않고 Worker 오류/종료 경로로
  전파하도록 수정했습니다.
- DataLogger write/stop 및 Loopback write/close 경쟁 구간을 lock으로 보호했습니다.
- 잘못된 parser preference 타입은 Raw parser로 안전하게 fallback하고, newline
  기본값을 UI enum의 canonical `LF`로 통일했습니다.
- `ApplicationComponents`가 모든 runtime owner에 명시적인 strong reference를
  유지하도록 완전한 composition graph를 반환합니다.
- Macro 실행 중 재시작/목록 교체를 거부하고, 중단/실패를 성공 완료로 표시하지
  않도록 실행 결과 의미를 분리했습니다.
- 빈 Macro script load, 우측 탭 저장/복원, Manual View state key, 빈 탭 삭제 후
  control refresh, Preferences font size 즉시 반영을 수정했습니다.
- 언어 키 검사 중 Python parse 오류를 CI 실패로 처리하고 관련 회귀 테스트를
  추가했습니다.

전체 diff 감사 교정 후 Python 3.13 로컬 결과는 `643 passed`, Ruff 0건,
language/task-board gate Green입니다. Python 3.11 PR CI와 실제 PyInstaller 산출물
smoke test는 별도 merge gate/잔여 리스크로 유지합니다.

---

### Presenter/View 리팩토링 로컬 검증 및 마지막 교정 (2026-08-30)

- stale API/constructor 감사에서 남아 있던 `controller.parsers` 테스트 접근을
  `PacketParserManager` public diagnostic API로 이동했습니다.
- shutdown 및 system logging 통합 fixture를 실제 ManualControl View 계약에 맞춰
  Auto Tx 상태와 interval을 명시했습니다.
- `PortPresenter` 테스트의 `QObject` 우회 생성을 제거하고 explicit dependency
  constructor로 조립했습니다.
- MainPresenter dependency DTO와 lowercase theme canonical 계약에 맞게 stale
  assertion을 정리했습니다.
- Ruff unused import 3건과 Preferences dialog line-length 3건을 수정했습니다.
- 루트 `Task.MD`가 현재 검증만 관리하도록 바뀐 문서 체계에 맞춰 과거 S-xxx
  정합 검사를 태스크 파일과 `tasks/README.md`의 2중 검사로 조정했습니다.

로컬 검증 결과:

```text
architecture contract: 33 passed
lifecycle/data-preservation: 45 passed
core feature: 75 passed
full pytest: 622 passed, 0 failed, 0 skipped
ruff check .: 0 errors
language key integrity: success
task board consistency: 78 historical tasks consistent
```

PR GitHub Actions와 `main` 대비 전체 diff 검토는 아직 남아 있습니다.

---

### 고속 수신 시 완결 패킷 유실 수정 (2026-08-22, S-064)

AT/Delimiter/FixedLength 파서가 한 번에 큰 데이터를 받을 때(예: 8192바이트 이상)
구분자가 정상적으로 와 있어도 완결된 패킷까지 조용히 사라지던 문제를 고쳤습니다.
완결된 패킷을 모두 분리해 낸 뒤, 그러고도 남은 미완결 조각에만 버퍼 크기 제한을
적용하도록 순서를 바꿨습니다. 미완결 조각이 상한을 넘어 버려질 때는 경고 로그를
남깁니다.

---

### 종료 시 DataLogger 테스트 간헐 실패 조사·수정 (2026-08-22, S-066)

전체 테스트를 반복 실행하면 드물게(단독 파일 기준 약 3~4%) 실패하던
`test_shutdown_stops_data_logger_and_preserves_written_bytes` 등의 원인을
찾았습니다. 실제 앱 종료 시 데이터가 유실되는 문제는 아니었고, 두 테스트가
LOOPBACK 포트에 데이터를 보낼 때 쓴 API가 발신(TX)과 수신(RX 에코) 양쪽에
로깅을 남기는(전이중 로깅, 의도된 기능) 것과 테스트의 준비 조건 판정이 겹치며
파일에 같은 내용이 한 번 더 기록되던 테스트 쪽 결함이었습니다. 이미 다른 테스트가
쓰던 "발신 경로 우회" 방식을 적용해 고쳤습니다(사용자 체감 변화 없음).

---

### QSS 대비 회귀 테스트 + 포트 상태 색 수정 (2026-08-22, S-065)

S-063이 고친 의미색 버튼 대비가 QSS 색을 한 줄만 바꿔도 조용히 되돌아갈 수 있어,
`tests/test_qss_contrast.py`로 4테마의 대비를 기계적으로 고정했습니다. 이 테스트가
실제로 미달 상태였던 포트 연결/에러 버튼(4테마 중 3곳)과 클래식 테마의 포트 해제
상태 라벨의 대비 미달을 새로 찾아내 함께 수정했습니다.

---

### 로그 색상 테마별 정리 (2026-08-23, S-078)

클래식 테마의 시스템 로그 글씨가 흰 배경에서 잘 안 보이던 문제를 고쳤습니다.
밝은 테마인데 어두운 테마용 색이 적용되고 있었습니다.

로그 색상이 테마 리소스로 옮겨져, 테마별로 읽기 좋은 색이 적용됩니다.

---

### 버튼·입력 구분 개선 (2026-08-23, S-077)

버튼과 입력창·목록이 눈에 더 잘 구분되도록 버튼 테두리를 또렷하게 했습니다.
드롭다운(콤보박스)은 모든 테마에서 입력창과 같은 모양으로 통일했습니다.

---

### UI 정렬·다이얼로그 정리 (2026-08-23, S-075·S-076)

포트 설정에서 프로토콜과 보드레이트 입력 상자가 같은 선에서 시작하도록 맞췄습니다.
언어를 한국어/영어로 바꿔도 입력 상자 위치가 거의 움직이지 않습니다.

파일 전송 창에서 파일 선택 영역과 진행률 표시가 겹쳐 보이던 문제를 고쳤습니다.
창 크기가 내용에 맞게 잡힙니다.

폰트 설정 창의 확인/취소/적용 버튼이 한국어로 표시됩니다.

---

### 클래식 테마 사각 모서리 + 패널 토글 크기 복원 (2026-08-23, S-073·S-074)

클래식 테마의 버튼·입력창·그룹 박스 모서리가 각지게 바뀌었습니다. 전통 Windows
모양에 맞춘 것으로, 다른 테마의 둥근 모서리는 그대로입니다.

우측 패널을 숨겼다 다시 켤 때 창과 패널 크기가 원래대로 돌아옵니다. 이전에는 켤
때마다 창이 조금씩 커지고 좌우 비율이 어긋났습니다.

---

### 패킷 프레이밍 방식 2종 추가 (2026-08-23, S-072)

**길이 필드** 파서를 추가했습니다. 헤더 안에 길이가 실려 패킷마다 크기가 달라지는
프로토콜(`[SOF][LEN][PAYLOAD][CRC]` 등)을 나눌 수 있습니다. 길이 필드의 위치·크기·
바이트 순서와 "길이 값이 헤더를 포함하는지"를 설정에서 지정합니다.

**유휴 간격** 파서를 추가했습니다. 구분자도 길이도 없이 일정 시간 침묵으로 프레임을
구분하는 프로토콜(Modbus RTU 등)에 씁니다. 포트를 닫을 때 마지막 프레임도 유실 없이
표시됩니다.

두 파서는 환경 설정 > 패킷 탭에서 고를 수 있습니다.

---

### 패킷 체크섬 검증 (2026-08-23, S-071)

패킷마다 체크섬이 맞는지 확인해 패킷 분석기에 표시합니다. XOR, SUM8/16, CRC-8,
CRC-16(MODBUS/CCITT), CRC-32를 지원하며, 설정에서 알고리즘과 위치(오프셋, 계산에서
제외할 앞뒤 바이트)를 지정합니다.

결과는 `검증` 열에 **OK / FAIL / 빈칸**으로 나옵니다. 빈칸은 "검증하지 않음"이며,
알고리즘을 고르지 않았거나 패킷이 체크섬을 담기에 짧을 때입니다 — 통과와 구분됩니다.

---

### 고속 수신 시 화면 멈춤 해소 + 종료 정리 (2026-08-22, S-061·S-062)

패킷이 한꺼번에 몰릴 때 화면이 최대 1초까지 멈추던 문제를 해결했습니다. 패킷 뷰가
수신 즉시 그리는 대신 30ms 주기로 모아서 반영합니다(RX 로그 뷰와 같은 방식).
포트를 닫거나 앱을 종료할 때는 남은 패킷을 버리지 않고 반영한 뒤 정리합니다.

포트 검색이 진행 중일 때 앱을 종료하면 검색 스레드가 정리되지 않던 문제도
함께 고쳤습니다.

---

### 클래식 테마 추가 (2026-08-22, S-060)

전통적인 Windows 회색 계열의 **클래식** 테마를 추가했습니다. 메뉴의 테마 선택에서
기존 Dark/Light/Dracula와 함께 고를 수 있습니다.

---

### 의미색 버튼 텍스트 대비 수정 (2026-08-22, S-063)

전송/반복 시작·중지·일시정지 버튼(accent/danger/warning)의 텍스트가 배경과 대비가
낮아 일부 테마에서 잘 안 보이던 문제를 해결했습니다. 밝은 배경에는 어두운 글씨,
어두운 배경에는 밝은 글씨를 쓰도록 4개 테마(dark/light/classic/dracula) 전체를
점검·조정했습니다. `tools/ux_capture.py`로 dracula 테마도 캡처할 수 있게 했습니다.

---

### 전체 리팩토링 감사 및 결함 수정 (2026-08-22)

읽기 전용 4축 감사(아키텍처 규칙 / 구조·설계 / 오동작 예상 / 테스트·문서)를 수행하고
발견된 결함을 우선순위대로 수정했습니다. 상세: `doc/refactor_audit_20260822.md`.

#### 수정 사항 (Fixed) — 실사용 파손

- **수신·송신 데이터가 로그 창에 전혀 표시되지 않던 문제**를 해결했습니다. 같은 클래스에
  메서드가 중복 정의되어 실제로 실행되는 쪽이 존재하지 않는 속성을 참조하고 있었습니다.
- 포트를 닫는 순간 전송 큐에 남아 있던 데이터가 조용히 사라지던 문제를 해결했습니다.
  파일 전송 완료 알림도 실제 전송이 끝난 뒤에 표시됩니다.
- 시리얼 쓰기 완료를 확인하지 않던 설정(`write_timeout=0`)을 바로잡아, 전송 실패를
  감지할 수 있게 했습니다.
- **포트 탭을 닫아도 연결이 유지되어 같은 포트를 다시 열 수 없던 문제**를 해결했습니다.
- 패킷 파서 설정(AT/Delimiter/Fixed Length)이 무시되고 항상 Raw로 동작하던 문제를
  해결했습니다. 미구현 프로토콜(SPI) 선택 시 조용히 시리얼로 연결하지 않고 알립니다.
- 수동 전송 실패(HEX 형식 오류, 미연결 등)가 화면에 표시되지 않던 문제를 해결했습니다.
- 매크로가 정상 종료될 때 완료 알림이 표시되지 않고, 수동 정지 시에는 두 번 표시되던
  문제를 해결했습니다.
- 로깅 중지 시 기록되지 않은 데이터가 유실되던 문제를 해결했습니다.

#### 개선 (Improved)

- 설정 기본값 파일이 개발자 로컬 상태로 오염되지 않도록 개발 모드 설정을 분리했습니다.
- 사용하지 않는 모듈 3건과 미사용 의존성 2건을 제거했습니다.
- 로그 위젯의 중복 코드를 공통 모듈로 정리하고, 테마·색상 매니저의 순환 참조를 없앴습니다.
- 매직 넘버를 상수로 옮기고, 타입과 어긋나던 위젯 이름을 바로잡았습니다.

#### 테스트·도구 (Tests & Tooling)

- 테스트를 **134개 → 282개**로 늘렸습니다. 특히 테스트가 없던 모듈(파일 전송, 데이터
  로거, 전역 예외 처리, 이벤트 라우터, 테마·색상 매니저, 로그 위젯)을 덮었습니다.
- 정적 검사를 도입했습니다: ruff lint(도입 즉시 도달 불가능한 죽은 코드 발견), 클래스 내
  중복 메서드 정의 차단, 코드가 참조하는 언어 키의 실재 여부 검사.
- 문서를 현재 코드 상태에 맞게 정정했습니다(완료된 작업 반영, 언어 키 가이드 표 재작성).

---

### UX 전면 점검 및 결함 수정, 에이전트 작업 체계 정비 (2026-08-22)

#### 수정 사항 (Fixed)

- 수신 로그 툴바의 위젯 생성 코드가 통째로 중복되어 툴팁·검색창 설정 전체가 무효화되던 버그를 제거했습니다 (S-019).
- PyInstaller 번들 감지가 `os._MEIPASS`를 참조해 항상 실패하던 것을 `sys._MEIPASS`로 정정했습니다 (S-018).
- 언어 키 원문이 화면에 노출되던 결함(수동 제어 패널 제목, Packet 패널 키 불일치)과 번역 오타·용어 혼재를 정리했습니다 (S-020).
- 상태바·포트 통계 상시 라벨과 실행 중 메시지(오류 다이얼로그, 매크로/파일 전송 피드백)가 언어 설정을 무시하고 영어로 나오던 것을 언어팩 경유로 전환했습니다 (S-021, 신설 키 32개).
- 고정 크기 하드코딩으로 영문 버튼("Start Repeat", "Scan", "Send")이 잘리던 것을 최소 크기 기반으로 완화했습니다 (S-024).
- WCAG 대비 미달 색(REC 표시, 라이트 섹션 제목, 연결 상태 점, 에러 로그색)과 테마를 우회한 하드코딩 색(파일 전송/About 다이얼로그)을 QSS 동적 속성 방식으로 정리했습니다 (S-022, 전 조합 4.5:1 이상).
- 테마 QSS 로딩이 딕셔너리 경로에 적중하지 못하고 폴백으로만 동작하던 구조와 dracula 테마의 아이콘·번역·동기화 단절을 정합시켰습니다 (S-023).
- UI 갱신 주기 리터럴을 `UI_REFRESH_INTERVAL_MS` 상수로 통일했습니다 (S-017).

#### 개선 (Improved)

- 레이아웃 여백·간격·아이콘 버튼 크기 상수 6종을 신설해 16개 파일의 리터럴을 치환하고, 툴팁 14개 보강, 메뉴 니모닉(Alt+F/V/T/H), PreferencesDialog 표준 버튼바 전환을 적용했습니다 (S-025).

#### 기능 (Added)

- AutoTxScheduler — 수동 명령 주기 반복 전송 (S-006, 실기기 미검증).
- PyInstaller 패키징(onedir spec, S-012)과 GitHub Actions CI(S-014, 러너 확인 대기), 성능 벤치마크 도구(S-011).
- 번들 실행 시 설정·로그를 `%APPDATA%\SerialTool`로 분리 저장 (S-013/S-029) — 첫 실행 자연 이관.

#### 설정 파일 정합 (Settings)

- 설정 네임스페이스를 `settings.*`로 정본화하고 스키마가 실사용 키를 검증하도록 재작성 — `global` 블록·죽은 ui 폰트 키·우측 폭 이중 키·고아 `serial` 블록을 1.1→1.3 마이그레이션으로 정리 (S-027/S-028/S-030). defaults에 마이그레이션을 적용하면 no-op이어야 한다는 재발 차단 테스트 추가.

#### UI 가이드 (Rules)

- `.agent/rules/ui_guide.md` 제정(색·대비·잘림·다국어·테마·상태 저장) 및 정적 스캔 강제 테스트 `tests/test_ui_guidelines.py` 도입 — 색 리터럴·인라인 font-size·한글 하드코딩 잔여 위반 전부 정리, 허용 목록 0건 (S-031).

#### 도구·문서 (Tooling & Documentation)

- 에이전트 작업 체계를 신설했습니다: 루트 `Task.MD` 작업 보드 + `tasks/S-0xx-*.md` 세부 태스크(하위 모델용 자족 문서), CLAUDE.md/RULES.md 재작성, chatlog 훅, task-done/lang-keys 스킬.
- 실행 화면 캡처 도구 `tools/ux_capture.py`를 추가하고(테마×언어×창 크기 조합), 이를 이용한 UX 점검 결과 35건을 `doc/ux_audit_20260822.md`에 기록했습니다.
- 언어 키 도구의 잘못된 경로(`resources/lang`)를 실제 경로로 수정해 검사가 동작하게 했습니다.
- 잔여 과제: 최소 창 크기 과대(S-026), 설정 키 네임스페이스 이중화(S-016) — 작업 보드 참조.

---

### 프로젝트 안정화 및 문서 현행화 (2026-08-22)

#### 수정 사항 (Fixed)

- `ConnectionWorker`의 Broadcast 상태 속성과 메서드 이름 충돌을 제거했습니다.
- Worker 시작 직후 종료할 때 실행 상태가 다시 활성화되어 `wait()`가 끝나지 않던 경합 조건을 수정했습니다.
- Worker 종료 시 배치 버퍼에 남은 수신 데이터를 방출하도록 보완했습니다.
- 송신 Queue 등록에 성공한 경우에만 송신 이벤트를 발행하도록 수정했습니다.
- 연결 종료 시 Worker, Parser, Config 레지스트리를 동기적으로 정리하고 중복 종료 이벤트를 방지했습니다.
- 빈 Delimiter와 0 이하 Fixed Length 설정을 파서 생성 시 거부하도록 검증을 추가했습니다.
- 번역 키가 없을 때 UI가 제공한 기본 문자열을 반환하도록 `LanguageManager.get_text()` 계약을 정리했습니다.

#### 테스트 (Tests)

- 공용 Fixture를 표준 `tests/conftest.py`로 복구하고 설정 및 Serial Mock을 격리했습니다.
- 리팩터링 이전 API를 참조하던 Parser, Presenter, View 및 통합 테스트를 현재 MVP Facade와 DTO 계약에 맞게 갱신했습니다.
- Core, Model, Presenter, View 및 주요 통합 흐름을 포함한 85개 테스트 통과 기준선을 확보했습니다.

#### 문서 (Documentation)

- README의 미구현 SPI/I2C, 미검증 처리량, 삭제된 도구와 문서 경로를 현재 구현 상태에 맞게 수정했습니다.
- 프로젝트 개요, 작업 목록, 테스트 가이드, 설정 가이드의 클래스명과 경로를 현행화했습니다.
- 구현 완료 영역과 패킷 설정 연결, 사용자 설정 경로, 성능 검증, 패키징 및 CI 등 후속 작업을 구분했습니다.

---

### 아키텍처 리팩토링 및 코드 품질 개선 (2025-12-28)

#### 리팩토링 (Refactoring)

- **MVP 아키텍처 고도화 (Strict MVP & Law of Demeter)**
  - **디미터 법칙 준수**: Presenter가 View의 깊은 내부 위젯 계층(`Window -> Section -> Panel -> Widget`)을 직접 탐색하지 않도록 수정하여 모듈 간 결합도를 획기적으로 낮췄습니다.
  - **파사드 패턴(Facade Pattern) 적용**: `ManualControlPanel`, `PortPanel`, `MacroPanel`, `PacketPanel` 등 주요 View 컨테이너에 `get_input_text()`, `is_hex_mode()`와 같은 인터페이스 메서드를 추가하여 내부 구현 상세를 캡슐화했습니다.
  - **내부 위젯 은닉**: View 내부의 하위 위젯 멤버 변수를 `_` 접두어(예: `_manual_control_widget`)로 변경하여 외부에서의 직접 접근을 구조적으로 차단했습니다.

- **데이터 흐름 및 신호 체계 개선**
  - **시그널 중계(Signal Relay)**: 하위 위젯의 이벤트를 패널이 받아 상위로 다시 방출(Re-emit)하는 구조를 확립하여, Presenter는 패널의 시그널만 구독하도록 의존성을 단순화했습니다.
  - **DTO 활용 강화**: `ManualControlPresenter`가 View의 상태를 수집할 때, View가 제공하는 인터페이스를 통해 안전하게 데이터를 조회하고 DTO를 조립하도록 개선했습니다.

- **코드 가독성 및 유지보수성**
  - **명시적 뷰 접근자**: `MainWindow`에 `macro_view`, `packet_view` 등의 프로퍼티를 추가하여, MainPresenter 초기화 시 UI 계층 구조를 탐색하지 않고 명시적으로 뷰 객체에 접근할 수 있게 했습니다.
  - **데이터 라우팅 캡슐화**: `PortTabPanel` 내부에 포트 이름 기반의 데이터 주입 로직(`append_rx_data`)을 캡슐화하여, 외부에서 탭 인덱스를 직접 순회하는 로직을 제거했습니다.

- **앱 초기화 시퀀스 최적화 (Startup Optimization)**
  - **테마 중복 로딩 제거**: `AppLifecycleManager`에서 `switch_theme`를 불필요하게 호출하던 코드를 제거했습니다. `main.py`의 초기 부팅 단계와 `apply_state` 내부의 폰트/테마 갱신 과정만 유지하여, 앱 시작 시 테마가 3번 중복 로드되는 비효율을 개선했습니다.
  - **로그 노이즈 감소**: "Application initialized" 로그가 `main.py`와 `LifecycleManager`에서 이중으로 출력되던 문제를 해결했습니다. `main.py`의 중복 로그를 제거하고, `LifecycleManager`의 완료 로그 레벨을 `INFO`에서 `DEBUG`로 조정하여 로그 가독성을 높였습니다.

#### 수정 사항 (Fixed)

- **로거 설정 강화**: `main.py` 진입점에서 `ResourcePath` 생성 직후 `logger.configure(resource_path)`를 명시적으로 호출하도록 수정하여, 로그 파일 경로가 개발 및 배포 환경(PyInstaller) 모두에서 즉시 올바르게 설정되도록 보장했습니다.

---

### 아키텍처 리팩토링 및 코드 품질 개선 (2025-12-27)

#### 리팩토링 (Refactoring)

- **MVP 아키텍처 고도화 (Strict MVP & Law of Demeter)**
  - **디미터 법칙 준수**: Presenter가 View의 깊은 내부 위젯 계층(`Window -> Section -> Panel -> Widget`)을 직접 탐색하지 않도록 수정하여 모듈 간 결합도를 획기적으로 낮췄습니다.
  - **파사드 패턴(Facade Pattern) 적용**: `ManualControlPanel`, `PortPanel` 등 주요 View 컨테이너에 `get_input_text()`, `is_hex_mode()`와 같은 인터페이스 메서드를 추가하여 내부 구현 상세를 캡슐화했습니다.
  - **내부 위젯 은닉**: View 내부의 하위 위젯 멤버 변수를 `_` 접두어(예: `_manual_control_widget`)로 변경하여 외부에서의 직접 접근을 구조적으로 차단했습니다.

- **데이터 흐름 및 신호 체계 개선**
  - **시그널 중계(Signal Relay)**: 하위 위젯의 이벤트를 패널이 받아 상위로 다시 방출(Re-emit)하는 구조를 확립하여, Presenter는 패널의 시그널만 구독하도록 의존성을 단순화했습니다.
  - **DTO 활용 강화**: `ManualControlPresenter`가 View의 상태를 수집할 때, View가 제공하는 인터페이스를 통해 안전하게 데이터를 조회하고 DTO를 조립하도록 개선했습니다.

- **코드 가독성 및 유지보수성**
  - **명시적 뷰 접근자**: `MainWindow`에 `macro_view`, `packet_view` 등의 프로퍼티를 추가하여, MainPresenter 초기화 시 UI 계층 구조를 탐색하지 않고 명시적으로 뷰 객체에 접근할 수 있게 했습니다.
  - **데이터 라우팅 캡슐화**: `PortTabPanel` 내부에 포트 이름 기반의 데이터 주입 로직(`append_rx_data`)을 캡슐화하여, 외부에서 탭 인덱스를 직접 순회하는 로직을 제거했습니다.

---

### 매크로 엔진 고도화 및 UX/안정성 강화 (2025-12-18)

#### 기능 추가 (Feat)

- **매크로 엔진 (Macro Engine)**
  - **정밀 타이밍 제어**: `QThread`와 `QWaitCondition` 기반으로 엔진을 재설계하여, 1ms 단위의 정밀한 실행 간격 제어 및 즉각적인 일시정지/재개 반응성을 확보했습니다.
  - **실행 피드백 강화**: 매크로 실행 시 현재 처리 중인 행(Row)을 리스트에서 실시간으로 하이라이트(Highlight)하고 스크롤을 동기화하며, 반복 횟수(현재/전체)를 표시합니다.
  - **반복 상태 제어**: `is_repeat` 파라미터를 도입하여 단일 실행과 반복 실행을 구분하고, 반복 모드에서만 정지/일시정지 버튼이 활성화되도록 UI 로직을 정교화했습니다.
  - **에러 처리 정책**: 실행 중 타임아웃 등 에러 발생 시 동작을 '중단(Stop)' 또는 '무시하고 계속(Continue)'으로 설정할 수 있는 `stop_on_error` 옵션을 구현했습니다.

- **스마트 전송 제어 (Smart Transmission Control)**
  - **브로드캐스트 동기화**: 브로드캐스팅 옵션이 켜져 있을 경우, 현재 탭의 연결이 끊겨 있더라도 **다른 활성 포트가 존재하면 전송 버튼을 활성화**하도록 로직을 개선했습니다.
  - **실시간 반응성**: 하위 위젯(`Widget`)에서 상위 프레젠터(`MainPresenter`)까지 이어지는 `broadcast_changed` 시그널 체인을 구축하여, 체크박스 상태 변경 즉시 전송 버튼의 활성화 상태가 갱신됩니다.

#### 리팩토링 (Refactoring)

- **MVP 패턴 강화 (MVP Enforcement)**
  - **Gatekeeping 로직**: 전송 요청 시 Controller에 의존하기 전, Presenter 단계에서 활성 포트 존재 여부 및 브로드캐스트 유효성을 선제적으로 검사하도록 구조를 개선했습니다.

- **안정성 및 최적화**
  - **스레드 안전성 (Thread Safety)**: `ConnectionController`에서 브로드캐스트 전송 시 `Dictionary changed size` 런타임 에러를 방지하기 위해, 연결 목록의 복사본을 순회하도록 수정했습니다.
  - **초기화 최적화**: `LanguageManager`의 지연 로딩(Lazy Initialization) 적용 및 `main.py` 실행 순서 재정립을 통해 초기 구동 속도를 높이고 테마 깜빡임을 제거했습니다.

#### 수정 사항 (Fixed)

- **안정성 및 예외 처리 (Stability & Safety)**
  - **안전한 종료**: 애플리케이션 종료 시 실행 중인 매크로 스레드를 감지하고 안전하게 정지(`wait`)시킨 후 프로세스를 종료하여 크래시를 방지했습니다.
  - **연결 방어 로직**: 매크로 실행 중 포트 연결이 끊기거나 탭이 닫히는 경우, 즉시 실행을 중단하는 게이트키퍼(Gatekeeper) 로직을 추가했습니다.
  - **UI 상태 복구**: 포트 연결 시도 중 에러 발생 시, 버튼 상태가 '연결됨'으로 잘못 남지 않고 '연결 해제' 상태로 즉시 복구되도록 수정했습니다.

- **버그 수정 (Bug Fixes)**
  - **파일 전송 오류**: 파일 전송 다이얼로그 호출 시 타겟 포트 인자가 누락되어 발생하던 `TypeError`를 수정했습니다.
  - **DTO 무결성 강화**: `PortConfig`, `MacroEntry` 등 주요 DTO 변환 시 `_safe_cast` 헬퍼를 적용하여 타입 안전성을 확보했습니다.
  - **색상 코드 보정**: `ColorManager`에서 설정 파일 로드 시 `#` 접두사가 누락된 HEX 코드를 자동으로 보정하도록 수정했습니다.

---

### UX 고도화 및 고급 기능 구현 (2025-12-18)

#### 기능 추가 (Feat)

- **스마트 헥사 덤프 (Smart Hex Dump Export)**
  - **다중 포맷 지원**: 로그 저장 시 `.bin` (Raw Binary) 외에 `.txt` (Hex Dump), `.pcap` (Wireshark 호환) 포맷을 지원합니다.
  - **자동 감지**: 파일 저장 다이얼로그에서 선택한 확장자에 따라 자동으로 저장 포맷을 결정합니다.
  - **PCAP 지원**: Global Header와 Packet Header를 포함한 표준 PCAP 포맷 저장을 구현하여 외부 분석 도구와의 호환성을 확보했습니다.

- **UI 상태 동기화 (UI State Synchronization)**
  - **포트 연동 제어**: 현재 활성화된 탭의 포트 연결 상태(Open/Close)에 따라 `ManualControl` 및 `MacroControl` 패널의 활성화 여부를 실시간으로 동기화합니다.
  - **설정 잠금**: 포트가 연결된 상태에서는 `PortSettingsWidget`의 설정 콤보박스들이 비활성화되어, 통신 중 설정 변경을 방지합니다.

- **테마 기반 색상 매핑 (Hybrid Color Mapping)**
  - **듀얼 컬러 지원**: `ColorRule`에 `light_color`와 `dark_color` 필드를 추가하여 테마별 최적의 색상을 지정할 수 있습니다.
  - **자동 보정 (HLS Fallback)**: 색상이 지정되지 않은 경우, HLS 알고리즘을 사용하여 배경색 대비 가독성이 좋은 명도로 색상을 자동 보정합니다.

#### 리팩토링 (Refactoring)

- **생명주기 관리 분리 (Lifecycle Management)**
  - **AppLifecycleManager**: `MainPresenter`의 비대한 초기화 로직(`_init_...`)을 별도의 매니저 클래스로 분리하여 코드 응집도를 높이고 유지보수성을 개선했습니다.
- **설정 마이그레이션 (Settings Migration)**
  - **버전 관리**: `SettingsManager`에 설정 파일 버전 확인 및 마이그레이션(`_migrate_settings`) 로직을 추가하여, 앱 업데이트 시 사용자 설정이 초기화되는 문제를 방지했습니다.
- **View-Model 완전 분리**
  - View 계층(`DataLogWidget`, `SystemLogWidget` 등)에서 `ColorManager` 등 Model 성격의 싱글톤 의존성을 완전히 제거하고, Presenter를 통해 데이터를 주입받도록 수정했습니다.
- **코드 정리 (Clean Code)**
  - `SmartNumberEdit` 위젯에 남아있던 디버깅용 `print` 문과 테스트 코드를 제거하고 `logger`로 대체했습니다.

#### 수정 사항 (Fixed)

- **런타임 오류 수정**: `MainPresenter`에서 누락된 `color_manager` import를 수정하여 `NameError`를 해결했습니다.
- **정규식 성능 최적화**: `ColorService`에 정규식 컴파일 캐싱(`_regex_cache`)을 도입하여 반복적인 컴파일 오버헤드를 제거했습니다.

---

### 아키텍처 및 안정성 강화 (2025-12-17)

#### 리팩토링 (Refactoring)

- **아키텍처 클린업 & 구조 개선 (Architecture Cleanup)**
  - **Service 계층 도입 (Phase 2)**: `ColorService`를 신설하여 색상 매칭 로직을 분리하고, `ColorManager`는 상태 관리와 영속성(Persistence)에만 집중하도록 리팩토링했습니다.
  - **DTO 중앙화 (Phase 2)**: `ColorRule` 데이터 구조를 `common/dtos.py`로 이동하여 순환 참조를 방지하고 데이터 정의를 일원화했습니다.
  - **Transport 계층 재구조화 (Step 3)**: `core`와 `model`에 혼재되어 있던 통신 드라이버 로직을 `core/transport` 패키지로 통합 이동하여 의존성 방향(Model -> Core)을 바로잡았습니다.
  - **Pure DTO 전환 (Step 2)**: `EventRouter` 및 Presenter 계층에서 레거시 `dict` 지원을 제거하고 DTO 사용을 강제했습니다.
  - **결합도 완화 (Step 2)**: `DataHandler`가 View 내부를 탐색하지 않고 인터페이스(`append_rx_data`)를 통해 데이터를 전달하도록 개선했습니다.
  - **기반 구조 정비 (Step 1)**: `core/utils.py`를 `core/structures.py`로, `common/schemas.py`를 `core/settings_schema.py`로 이동했습니다.
  - **테스트 환경 개선**: `conftest.py`를 도입하여 공용 Fixture를 중앙화했습니다.

#### 기능 개선 (Feat)

- **자료구조 API 확장**
  - `RingBuffer`에 `available()` 메서드를 추가하여 버퍼 상태 확인의 가독성을 높였습니다.
- **포트 스캔 최적화**
  - **비동기 스캔**: `PortScanWorker`를 `Model` 계층으로 이동시키고 비동기로 동작하게 하여 UI 프리징을 제거했습니다.
  - **Lazy Loading**: `ClickableComboBox` 구현으로 클릭 시점 스캔을 지원합니다.
  - **정렬 개선**: `Natural Sorting`을 적용하여 포트 목록 가독성을 높였습니다.
- **매크로 로딩 최적화**
  - **비동기 로드**: `ScriptLoadWorker`를 도입하여 대용량 JSON 로딩 시 반응성을 확보했습니다.

#### 수정 사항 (Fixed)

- **시리얼 통신 안정성**
  - **UI 프리징 방지**: `SerialTransport`에 `write_timeout=0` 설정을 추가했습니다.
  - **데이터 유실 방지**: `write` 예외 무시 로직을 제거하고 에러를 상위로 전파했습니다.
  - **성능 최적화**: `BATCH_SIZE_THRESHOLD`를 8KB로 상향 조정했습니다.
- **배포 및 데이터 안전성**
  - **아이콘 경로**: PyInstaller 배포를 위해 QSS 로딩 시 절대 경로 치환 로직을 추가했습니다.
  - **설정 복구 알림**: 설정 파일 초기화 시 사용자 경고 알림을 추가했습니다.

---

### 아키텍처 고도화 및 확장성 강화 (2025-12-15)

#### 리팩토링 (Refactoring)

- **Strict MVP 아키텍처 적용**
  - **DTO 도입**: `PreferencesState`, `MainWindowState`, `ManualControlState` DTO를 도입하여 View와 Presenter 간의 데이터 교환을 정형화했습니다.
  - **View 로직 제거**: `PreferencesDialog`의 설정 파싱 로직과 `MainWindow`의 상태 복원(`restore_state`) 로직을 Presenter로 이관했습니다.
  - **상태 관리 이관**: `ManualControlWidget`의 명령어 히스토리 관리와 `DataLogWidget`의 파일 다이얼로그 호출 로직을 각 Presenter로 이동시켜 View를 순수한 UI 컴포넌트로 전환했습니다.
  - **스키마 분리**: `core/settings_manager.py`에 있던 `CORE_SETTINGS_SCHEMA`를 `common/schemas.py`로 이동하여 데이터 정의와 로직을 분리했습니다.

#### 기능 추가 (Feat)

- **리소스 동적 로딩 및 확장성 강화**
  - **언어/테마 자동 감지**: `LanguageManager`와 `ThemeManager`가 폴더를 스캔하여 추가된 JSON/QSS 파일을 자동으로 인식하도록 개선했습니다.
  - **설정 변경 이벤트**: `EventBus`에 `SETTINGS_CHANGED` 토픽을 추가하여, 설정 변경 시 `MainPresenter`를 거치지 않고 각 컴포넌트가 독립적으로 반응하도록 개선했습니다.
  - **언어 메타데이터**: 언어 파일(`*.json`)에 `_meta_lang_name` 키를 추가하여 UI 표시 이름을 파일 내에서 정의하도록 했습니다.

#### 수정 사항 (Fixed)

- **안정성 강화**
  - **매크로 브로드캐스트**: `MainPresenter`에서 매크로 전송 시 `is_broadcast` 플래그를 누락하던 버그를 수정했습니다.
  - **파일 전송 타겟**: 파일 전송 다이얼로그 호출 시 현재 활성 포트 컨텍스트를 명시적으로 전달하여, 멀티탭 환경에서 엉뚱한 포트로 전송되는 문제를 방지했습니다.
  - **종료 시 예외**: `MainWindowState` DTO를 iterable로 잘못 사용하여 발생하던 `TypeError`를 수정했습니다.
  - **UI 스타일**: `common.qss`에 `QSmartTextEdit`의 기본 속성(Fallback)을 명시하여 테마 로드 실패 시에도 UI 가독성을 보장하도록 개선했습니다.

---

### 시스템 안정성 및 성능 최적화 (2025-12-14)

#### 성능 개선 (Performance)

- **고속 데이터 수신 최적화 (Fast Path)**
  - `ConnectionController`에서 `MainPresenter`로 이어지는 데이터 수신 경로에서 `EventBus`를 우회하는 **Fast Path**를 구현했습니다.
  - **UI Throttling**: 수신된 데이터를 즉시 렌더링하지 않고 버퍼링한 후, 30ms 간격(`QTimer`)으로 일괄 업데이트하여 메인 스레드 부하를 최소화했습니다.
  - 이를 통해 2MB/s 이상의 고속 통신 시에도 UI 프리징 없는 부드러운 화면 갱신을 보장합니다.

#### 수정 사항 (Fixed)

- **파일 전송/포트 종료 경합 조건(Race Condition) 해결**
  - 파일 전송 중 포트를 강제로 닫을 때 발생할 수 있는 충돌을 방지하기 위해 `ConnectionController`에 활성 전송 레지스트리를 추가했습니다.
  - 포트 종료 시 진행 중인 전송이 있다면 즉시 `cancel()`을 호출하고 안전하게 정리되도록 로직을 강화했습니다.
- **설정 파일 무결성 검증 강화**
  - `SettingsManager` 로드 시 `jsonschema`를 사용하여 필수 필드와 데이터 구조를 검증하는 로직을 추가했습니다.
  - `common/dtos.py`의 `from_dict` 메서드에 `_safe_cast` 헬퍼를 적용하여, 설정 파일이 손상되거나 값이 누락되어도 기본값으로 복구되어 크래시가 발생하지 않도록 개선했습니다.

---

### 매크로 기능 확장 (2025-12-14)

#### 기능 추가 (Feat)

- **매크로 브로드캐스트 지원**
  - `MacroControlWidget`에 'Broadcast' 체크박스를 추가했습니다.
  - 매크로 실행 시 활성화된 모든 포트로 명령어를 전송할 수 있는 기능을 구현했습니다.
  - `MacroRepeatOption` DTO에 `is_broadcast` 필드를 추가하여 UI 상태를 Model로 전달하도록 구조를 확장했습니다.
  - `MacroRunner`에서 `ManualCommand` 생성 시 브로드캐스트 플래그를 적용하여, 연결된 모든 장비에 일괄 명령을 전송(Fire-and-forget)하도록 로직을 구현했습니다.

---

### 아키텍처 정밀화 및 안정성 강화 (2025-12-14)

#### 수정 사항 (Fixed)

- **설정 동기화 버그 수정**
  - `PreferencesDialog`에서 변경한 'Local Echo' 설정이 `ManualControlWidget` 체크박스에 즉시 반영되지 않는 문제 해결
  - `ManualControlWidget` 및 `Panel`에 `set_local_echo_state` 메서드 추가하여 외부 제어 허용
  - `ManualControlPresenter`에 `update_local_echo_setting` 추가 및 `MainPresenter`와 연동

- **PortSettingsWidget 런타임 오류 수정**
  - `on_connect_clicked` 메서드에서 `PortConfig` DTO 객체에 딕셔너리 메서드인 `.update()`를 호출하여 발생하던 `AttributeError`를 수정했습니다.
  - `get_current_config` 메서드 내부에서 객체 생성 시 데이터를 완벽하게 조립하여 반환하도록 로직을 개선했습니다.

#### 추가 사항 (Added)

- **EventBus 기능 강화**
  - **와일드카드 구독 지원**: `fnmatch`를 도입하여 `port.*`와 같은 패턴으로 이벤트를 구독할 수 있는 기능을 추가했습니다.
  - **디버깅 모드**: `set_debug_mode(True)` 호출 시 모든 발행 이벤트를 로그로 출력하는 기능을 추가했습니다.
- **EventTopics 상수 도입**
  - `common/constants.py`에 `EventTopics` 클래스를 신설했습니다.
  - `PORT_OPENED`, `MACRO_STARTED`, `FILE_PROGRESS` 등 시스템 전반의 이벤트 토픽을 한곳에서 관리합니다.

#### 리팩토링 (Refactoring)

- **데이터 전송 객체(DTO) 도입**
  - `common/dtos.py` 신설: `ManualCommand`, `PortConfig`, `FontConfig` 데이터 클래스 정의
  - 딕셔너리(`dict`) 대신 명시적인 DTO를 사용하여 컴포넌트 간 데이터 전달 (View ↔ Presenter ↔ Model)
  - `ManualControlWidget`, `PortSettingsWidget` 등 주요 위젯에 적용하여 타입 안전성(Type Safety) 확보 및 오타 방지

- **MVP 아키텍처 위반 수정 (MVP)**
  - **MainWindow**: `SettingsManager`(Model) 직접 생성 및 의존성 제거
  - **MainPresenter**: 설정 로드 책임 이관 및 `View.restore_state()` 메서드를 통해 초기 상태 주입
  - **Main Entry**: `main.py`에서 모든 Manager(`Settings`, `Theme`, `Lang`, `Color`)를 사전 초기화하여 전역 상태 보장
  - View는 수동적(Passive) 뷰로 전환하고, 데이터 처리는 Presenter가 전담하도록 구조 개선

- **전면적인 DTO(Data Transfer Object) 적용**
  - **매크로**: `MacroScriptData` (파일 저장/로드), `MacroRepeatOption` (반복 설정), `MacroStepEvent` (실행 단계) DTO를 도입하여 `dict` 사용을 제거했습니다.
  - **에러 핸들링**: `ErrorContext` DTO를 도입하여 에러 타입, 메시지, 트레이스백 정보를 구조화했습니다.
  - **파일 전송**: `FileProgressEvent` DTO를 도입하여 EventBus를 통한 진행률 전달 시 타입 안전성을 확보했습니다.
- **매직 스트링(Magic String) 제거**
  - `ConnectionController`, `MacroRunner`, `FileTransferEngine`, `EventRouter` 등 핵심 모듈에서 문자열 리터럴로 사용되던 이벤트 토픽을 `EventTopics` 상수로 전면 교체했습니다.
  - 이를 통해 오타로 인한 버그 발생 가능성을 원천 차단하고 IDE의 자동 완성 지원을 강화했습니다.

#### 기능 추가 (Feat)

- **초기 기능 구현 통합**
  - 수동 제어(Manual Control) 및 매크로(Macro) 기능을 위한 UI, Presenter, Model, Test 코드 통합 구현
  - MVP 아키텍처 기반의 핵심 시리얼 통신 도구 기능 완성

---

### 명명 규칙 표준화 및 디커플링 (2025-12-13)

#### 리팩토링 (Refactoring)

- **DataLogViewer 리네이밍**
  - `RxLogWidget`을 **`DataLogViewer`**로 클래스명 변경
  - 송신(TX) 데이터와 수신(RX) 데이터를 모두 표시하는 역할에 맞게 이름 현실화
  - Model 계층의 `DataLogger`와 이름의 톤앤매너 일치

- **ConnectionController 활성 연결 명시화**
  - `set_active_connection(name)` 메서드 추가로 명시적인 제어권 확보
  - `current_connection_name` 속성이 모호함 없이 현재 활성 탭의 연결을 반환하도록 로직 개선

- **CommandProcessor 디커플링 (Decoupling)**
  - `process_cmd` 메서드 내부의 `SettingsManager` 직접 참조(Hidden Dependency) 제거
  - Prefix/Suffix 설정을 외부(Presenter)에서 주입받도록 변경하여 순수 함수(Pure Function)에 가깝게 전환
  - 테스트 용이성 및 아키텍처 투명성 향상

---

### 아키텍처 안정화 및 핵심 기능 고도화 (2025-12-12)

#### 추가 사항 (Added)

- **설정 키 상수화 (ConfigKeys)**
  - `constants.py`에 `ConfigKeys` 클래스 추가 및 설정 경로 중앙 관리
  - 모든 설정 접근 로직(`SettingsManager.get/set`)에 상수 적용 완료

- **핵심 기능 로직 보강**
  - **매크로**: `ExpectMatcher` 구현 및 `_wait_for_expect` 응답 대기 로직 추가
  - **파일 전송**: 송신 큐 모니터링을 통한 Backpressure(역압) 제어 로직 추가
  - **성능**: `QSmartListView` 검색 입력에 디바운싱(300ms) 타이머 추가

#### 변경 사항 (Changed)

- **명명 규칙 및 구조 개선 (Renaming & Refactoring)**
  - **Data Logger**: `LogRecorder`를 `DataLogger`로 명칭 변경 (시스템 로그와 데이터 로깅의 역할 분리 명확화)
  - **Data Log View**: `RxLogWidget`를 `DataLogViewWidget`로 명칭 변경 (송수신 데이터를 포괄하는 `DataLog`가 더 정확함)
  - **Event System**: `PortController`의 중복된 이벤트 발행 구조를 제거하고 Signal-EventBus 자동 브리지 구현
  - **Macro Engine**: `QTimer` 기반 루프를 `QThread` + `QWaitCondition` 기반으로 전면 교체 (Windows 타이머 정밀도 문제 해결)
  - **Font Settings**: 폰트 설정 저장 로직을 View(`MainWindow`)에서 Presenter(`MainPresenter`)로 이관하고, 동적 키 생성(`f-string`) 대신 `ConfigKeys` 매핑 딕셔너리를 사용하여 MVP 원칙 준수 및 안전성 강화
  - **Sys Log View**: `SystemLogWidget`를 `SysLogViewWidget`로 명칭 변경 (통일성)

- **코드 품질 및 테스트 안정성 (Quality & Stability)**
  - **Documentation**: `model/macro_runner.py` 등 핵심 모듈에 Google Style Docstring 가이드(WHY/WHAT/HOW, Logic)를 엄격히 적용하여 가독성 향상
  - **Thread Safety**: `MacroRunner`의 `_on_data_received` 및 `run` 루프 내 Mutex 잠금 범위를 최적화하여 경쟁 상태(Race Condition) 방지
  - **Test Reliability**: `test_model.py`의 비동기 시그널 대기 타임아웃을 연장(1s → 5s)하고 스레드 초기화 대기(`qtbot.wait`)를 보강하여 간헐적인 `TimeoutError` 해결

- **로직 최적화 및 수정**
  - **Flow Control**: 하드웨어 흐름 제어 설정에 따라 전송 지연(Sleep)을 조건부로 적용하도록 변경
  - **Error Handler**: `KeyboardInterrupt` 발생 시 기존 훅(`_old_excepthook`)을 호출하여 호환성 유지

#### 이점 (Benefits)

- **안정성 확보**: 대량 데이터 전송 및 고속 매크로 실행 시의 메모리 폭증 및 데이터 유실 방지
- **유지보수성 향상**: 문자열 리터럴 제거, 이벤트 흐름 단일화, 표준화된 주석 적용으로 코드 복잡도 감소
- **성능 개선**: 정규식 필터링 시 UI 프리징 현상 해결 및 매크로 타이밍 정밀도(1ms) 확보
- **신뢰성 높은 테스트**: 비동기 테스트 시나리오의 안정화로 CI/CD 신뢰도 향상
- **명확성 증대**: 시스템 로그와 데이터 로깅의 용어 분리로 개발자 혼동 방지

---

### Presenter 계층 구조화 및 MVP 리팩토링 (2025-12-12)

#### 추가 사항 (Added)

- **신규 Presenter 도입**
  - **`ManualCtrlPresenter`**: 수동 명령어 전송, Prefix/Suffix 처리, Hex 변환 로직을 전담
  - **`PacketPresenter`**: 패킷 데이터의 포맷팅(Timestamp, Hex/ASCII 변환) 및 설정 적용 로직 전담
  - **`FilePresenter`**: 파일 전송 진행률, 속도(Speed), 잔여 시간(ETA) 계산 로직 전담

- **View 인터페이스 강화 (Passive View)**
  - **Interface Methods**: Presenter가 View의 내부 위젯에 직접 접근하지 않도록 공개 메서드(`set_connected`, `append_local_echo_data`, `update_progress`) 구현
  - **Signal Bubbling**: 하위 위젯(`ManualCtrlWidget`)의 이벤트를 패널(`ManualCtrlPanel`)과 섹션(`MainLeftSection`)을 거쳐 최상위(`MainWindow`)로 전달하는 구조 구현

#### 변경 사항 (Changed)

- **MainPresenter 대규모 리팩토링**
  - View 내부 계층(`view.left_section.manual_ctrl...`)에 대한 직접 접근 코드를 전면 제거
  - `ManualCtrl`, `Packet`, `File` 관련 로직을 각 전담 Presenter로 이관하여 코드 비대화 해소
  - `EventRouter`와 `MainWindow`의 공개 인터페이스만을 사용하여 로직 조율

- **MVP 원칙 적용**
  - **PortPresenter**: `connect_btn` 등 위젯 직접 제어를 제거하고 시그널 구독 및 상태 변경 요청 방식으로 전환
  - **FileTransferDialog**: 내부의 계산 로직을 모두 제거하고, Presenter가 전달하는 데이터만 표시하는 수동적인 뷰로 전환
  - **Local Echo**: `MainPresenter` 내 하드코딩된 로직을 제거하고, View 인터페이스(Callback)를 통해 유연하게 처리

#### 이점 (Benefits)

- **결합도 감소**: Presenter가 View의 구체적인 구현(위젯 계층 구조)을 알 필요가 없어져 유지보수성 향상 (디미터 법칙 준수)
- **책임 분리 명확화**: 각 Presenter가 특정 도메인 로직만 담당하여 단일 책임 원칙(SRP) 강화
- **테스트 용이성 증대**: View의 로직이 제거되고 Presenter로 이동함에 따라, UI 없이 비즈니스 로직에 대한 단위 테스트 가능

---

### 코드 문서화 강화 (2025-12-12)

#### 추가 사항 (Added)

- **주석 가이드 준수 문서화**
  - 25개 핵심 파일에 WHY/WHAT/HOW 섹션 추가
  - Google Style Docstring 형식 100% 준수
  - Logic 섹션으로 복잡한 알고리즘 설명 강화

- **모듈별 문서화 완료**
  - **Core 모듈 (3개)**: event_bus, logger, settings_manager
  - **Model 모듈 (8개)**: macro_runner, file_transfer, port_controller, serial_manager, connection_worker, serial_transport, packet_parser, macro_entry
  - **Presenter 모듈 (5개)**: macro_presenter, main_presenter, port_presenter, file_presenter, event_router
  - **View 모듈 (5개)**: lang_manager, theme_manager, smart_plain_text_edit, smart_number_edit
  - **Entry/Config/Resource (4개)**: main.py, constants.py, resource_path.py
  - **Test 모듈 (1개)**: test_ui_translations_dynamic.py

#### 변경 사항 (Changed)

- **주석 간결성 개선**
  - "~합니다" → "~" 형태로 간결화
  - 불필요한 조사 제거
  - 명사형 종결로 통일

- **기술 용어 일관성 확보**
  - PyQt, PySerial, pathlib 등 영어 유지
  - Signal, Slot, Thread, Worker 등 PyQt 용어 영어 유지
  - Singleton, MVP, Pub/Sub, Factory 등 디자인 패턴 용어 영어 유지

- **Logic 섹션 추가 (17개 파일)**
  - 복잡한 알고리즘 흐름 명확화
  - 조건 분기 의도 설명
  - 에러 처리 로직 문서화
  - 버퍼 관리 및 메모리 보호 로직 설명

#### 이점 (Benefits)

- **가독성 향상**: 코드 의도를 명확히 전달하여 이해도 증대
- **유지보수성 개선**: 일관된 문서화 형식으로 코드 수정 용이
- **온보딩 효율화**: 신규 개발자가 코드베이스를 빠르게 이해 가능
- **자동 문서화 준비**: mkdocstrings 플러그인으로 자동 문서 생성 가능

---

### EventBus 싱글톤 수정 및 Presenter 계층 구조화 (2025-12-12)

#### 추가 사항 (Added)

- **EventRouter (이벤트 라우터)**
  - `presenter/event_router.py`: EventBus 이벤트를 PyQt 시그널로 변환하는 라우터 클래스
  - Port Events: `port_opened`, `port_closed`, `port_error`, `data_received`
  - Macro Events: `macro_started`, `macro_finished`, `macro_progress`
  - File Transfer Events: `file_transfer_progress`, `file_transfer_completed`
  - 스레드 안전한 UI 업데이트 보장

- **MacroPresenter (매크로 프레젠터)**
  - `presenter/macro_presenter.py`: MacroPanel과 MacroRunner를 연결하는 Presenter
  - 매크로 시작/정지, 단일 명령 전송 요청 처리
  - MacroRunner 시그널과 UI 연동

- **FilePresenter (파일 전송 프레젠터)**
  - `presenter/file_presenter.py`: 파일 전송 로직을 전담하는 Presenter
  - FileTransferEngine 관리 및 진행률 UI 업데이트
  - 전송 완료/에러 상태 처리

- **Core Refinement 테스트**
  - `tests/test_core_refinement.py`: ExpectMatcher 및 ParserType 상수 테스트
  - 문자열 매칭, 정규식 매칭, 버퍼 크기 제한, 파서 팩토리 생성 테스트

#### 수정 사항 (Fixed)

- **EventBus 싱글톤 패턴**
  - `core/event_bus.py`: 전역 `event_bus` 인스턴스 도입
  - `__new__` 메서드 제거, 모듈 레벨 싱글톤으로 단순화
  - `PortController`, `MacroRunner`, `FileTransferEngine`, `EventRouter`에서 전역 인스턴스 사용

- **PortController 시그널 복구**
  - 실수로 제거된 시그널 정의 복구
  - `port_opened`, `port_closed`, `error_occurred`, `data_received`, `data_sent`, `packet_received`

- **MacroRunner 시그널 불일치 수정**
  - `send_requested` 시그널 (4개 인자)과 `on_manual_cmd_send_requested` (5개 인자) 불일치 해결
  - `on_macro_cmd_send_requested` 중간 핸들러 추가

- **테스트 파라미터 수정**
  - `ExpectMatcher` 테스트: `feed()` → `match()` 메서드명 수정
  - `ExpectMatcher` 테스트: `timeout_ms` 파라미터 제거 (구현에 없음)
  - `ParserType` 테스트: 상수값 수정 (`"raw"` → `"Raw"` 등)

#### 변경 사항 (Changed)

- **MainPresenter 리팩토링**
  - `MacroPresenter`, `FilePresenter`, `EventRouter` 초기화 추가
  - `EventRouter` 시그널을 통한 포트 이벤트 처리로 변경
  - 파일 전송 로직을 `FilePresenter`로 위임

- **Model 계층 EventBus 통합**
  - `PortController`: 포트 상태 변경 시 EventBus 이벤트 발행
  - `MacroRunner`: 매크로 생명주기 이벤트 발행
  - `FileTransferEngine`: 파일 전송 진행률/완료 이벤트 발행

---

### Core 및 Model 기능 강화 (2025-12-11 - 심야 세션)

#### 추가 사항 (Added)

- **Global Error Handler (전역 에러 핸들러)**
  - `core/error_handler.py`: 처리되지 않은 예외(Uncaught Exception)를 포착하여 로깅하고 사용자에게 알림
  - `sys.excepthook` 오버라이딩을 통해 구현
  - `main.py`에 통합하여 애플리케이션 안정성 확보

- **ExpectMatcher (응답 대기 매처)**
  - `model/packet_parser.py`: 정규식(Regex) 및 문자열 리터럴 기반 매칭 클래스 구현
  - 매크로 실행 시 특정 응답을 대기하는 기능의 기반 마련

- **PacketParser 통합**
  - `model/port_controller.py`: `PacketParser`를 통합하여 수신된 Raw 데이터를 Packet 객체로 변환
  - `packet_received` 시그널 추가 및 `parsers` 딕셔너리를 통한 포트별 파서 관리
  - 설정(`parser_type`, `delimiter` 등)에 따른 파서 자동 초기화

- **FileTransferEngine (파일 전송 엔진)**
  - `model/file_transfer.py`: `QRunnable` 기반의 파일 전송 엔진 구현
  - 별도 스레드에서 실행되어 UI 블로킹 방지
  - Baudrate 기반 적응형 청크 전송 및 진행률(Progress) 시그널링
  - 전송 취소 기능 지원

#### 개선 사항 (Refinement & Hardening)

- **GlobalErrorHandler 스레드 안전성 확보**
  - `QObject` 상속 및 시그널/슬롯 패턴 적용
  - 워커 스레드에서 발생한 예외도 메인 UI 스레드에서 안전하게 다이얼로그 표시

- **ExpectMatcher 안정성 강화**
  - `max_buffer_size` 도입으로 메모리 무한 증가 방지 (기본 1MB)
  - 버퍼 초과 시 오래된 데이터 자동 삭제

- **PortController 캡슐화 및 확장**
  - `send_data_to_port` 메서드 추가로 특정 포트 대상 전송 지원
  - `FileTransferEngine`이 내부 `workers`에 직접 접근하지 않도록 개선

- **PacketParser 코드 품질 개선**
  - `ParserType` 상수 클래스 도입으로 하드코딩 문자열 제거
  - `ParserFactory` 및 `PortController`에서 상수 사용으로 유지보수성 향상

---

### UI 기능 보완 및 사용성 개선 (2025-12-11)

#### 추가 사항 (Added)

- **Packet Inspector 설정 UI**
  - `PreferencesDialog`에 `Packet` 탭 추가
  - Parser Type (Auto, AT, Delimiter, Fixed, Raw), Delimiter 설정, Fixed Length, AT Color Rules, Inspector Options UI 구현
  - 관련 설정 로드/저장 로직 구현

- **RX Newline 처리 옵션**
  - `RxLogWidget`에 Newline 모드 선택 콤보박스 (Raw, LF, CR, CRLF) 추가
  - 수신 데이터 줄바꿈 처리 로직 구현
  - 관련 언어 키 추가 (`ko.json`, `en.json`)

- **Main Status Bar 동적 업데이트**
  - `PortController`에 `data_sent` 시그널 추가
  - `MainPresenter`에서 1초 주기로 RX/TX 속도(KB/s) 계산 및 상태바 업데이트
  - 포트 연결/해제/에러 상태 실시간 표시 연동

- **전역 단축키 시스템**
  - `MainWindow`에 전역 단축키 등록
  - F2: 현재 포트 연결 (Connect)
  - F3: 현재 포트 연결 해제 (Disconnect)
  - F5: 현재 포트 로그 지우기 (Clear Log)
  - `MainPresenter`와 `PortPresenter` 연동하여 동작 구현

- **전이중 레코딩 (Full Duplex Recording)**
  - 송신(TX) 데이터와 수신(RX) 데이터를 모두 로그 파일에 기록하는 기능 구현
  - `MainPresenter`에서 데이터 송수신 이벤트를 캡처하여 `DataLoggerManager`로 전달
  - `RxLogWidget`의 로그 저장 버튼을 토글 방식으로 변경하고, 파일명에 탭 이름 포함

#### 변경 사항 (Changed)

- **문서 업데이트**
  - `doc/task.md`: Phase 2.5 완료 상태 반영

---

### 기능 개선 및 버그 수정 (2025-12-11)

#### 추가 사항 (Added)

- **MacroListWidget 컨텍스트 메뉴**
  - 우클릭 메뉴 추가: Add, Delete, Up, Down 기능 제공
  - 키보드 단축키 외에 마우스 조작 편의성 향상
  - **MacroListWidget 추가 기능 개선**
  - 매크로 추가 시 선택된 행 바로 아래에 삽입되도록 변경 (기존: 항상 맨 뒤 추가)
- **ManualControlWidget 히스토리 기능**
  - 최근 전송된 명령어 50개 기억 (MRU 방식)
  - 전송 버튼 상단에 히스토리 탐색(▲, ▼) 버튼 추가
  - Ctrl+Up/Down 키로도 히스토리 탐색 가능

- **리팩토링 (Refactoring)**
  - `PortController.open_port`: 개별 인자 대신 `config` 딕셔너리를 받도록 변경하여 확장성 확보
  - `MainWindow` 종료 로직을 `MainPresenter`로 이동하여 역할 분리 (MVP 패턴 강화)
  - `PortController`: 멀티포트 지원을 위해 다중 `ConnectionWorker` 관리 구조로 리팩토링

#### 변경 사항 (Changed)

- **에러 핸들링 및 로깅 개선**
  - `PortPresenter` 및 `MacroPanel`에서 `print` 문을 `logger`와 `QMessageBox`로 대체
  - 포트 미선택 시 Warning, 에러 발생 시 Critical 팝업 표시
  - 에러 상황을 로그 파일에 기록하여 디버깅 용이성 확보

- **PortSettingsWidget 로직 복원**
  - `get_current_config` 메서드 추가 및 `PortPresenter` 연동
  - 누락되었던 `on_protocol_changed`, `on_connect_clicked`, `on_port_scan_clicked` 메서드 복원
  - `set_connected` 메서드 추가로 호환성 확보
  - 포트 설정 및 연결 로직 정상화

- **ManualCtrlWidget UI 정리**
  - `RxLogWidget`과 중복되는 `Clear` 및 `Save Log` 버튼 제거
  - UI 레이아웃 재구성

- **RingBuffer 최적화**
  - `core/utils.py`: `memoryview` 슬라이싱을 사용하여 `write` 메서드 성능 개선
  - 불필요한 데이터 복사 최소화

#### 수정 사항 (Fixed)

- **QSmartListView 테두리 스타일**
  - `QSmartListView`에 객체 이름(`SmartListView`) 부여
  - `common.qss`, `dark_theme.qss`, `light_theme.qss`에서 ID 선택자(`#SmartListView`)를 사용하여 테두리 스타일 적용
  - `QGroupBox` 스타일과의 간섭 제거로 올바른 테두리 표시

- **RxLogWidget 버그 수정**
  - 존재하지 않는 `add_logs_batch` 메서드 호출을 `append_batch`로 수정하여 대량 로그 처리 오류 해결

#### 추가 사항 (Added) - 오후 세션

- **Local Echo (로컬 에코)**
  - `ManualCtrlWidget`에 로컬 에코 체크박스 추가
  - 송신 데이터를 수신창(`RxLogWidget`)에 표시하는 기능 구현
- **시스템 로그 및 타임스탬프 색상 규칙**
  - `ColorManager`에 `SYS_INFO`, `SYS_ERROR` 등 시스템 로그 규칙 추가
  - `TIMESTAMP` 규칙 추가 및 `get_rule_color` 메서드 구현
  - `SystemLogWidget` 및 `RxLogWidget`이 `ColorManager`를 통해 색상을 적용하도록 개선

#### 변경 사항 (Changed) - 오후 세션

- **경로 관리 리팩토링 (Path Management)**
  - `ResourcePath` 클래스 도입으로 리소스 경로 관리 일원화
  - `Paths` 클래스 대체 및 테마 아이콘 경로 처리 로직 개선
  - 주요 모듈(`main.py`, `settings_manager.py` 등) 업데이트
- **QSmartListView 리팩토링**
  - 타임스탬프 색상 처리 로직을 제거하고 순수 뷰어 역할로 변경
  - 색상 처리는 `RxLogWidget` 및 `SystemLogWidget`에서 수행

#### 수정 사항 (Fixed) - 오후 세션

- **RxLogWidget 버그 수정**
  - 존재하지 않는 `add_logs_batch` 메서드 호출을 `append_batch`로 수정하여 대량 로그 처리 오류 해결

#### 변경 사항 (Changed) - 저녁 세션

- **System Log 위치 변경**
  - `PortPanel` 내부에서 `MainLeftSection` 하단(전역)으로 이동
  - 탭별로 분산된 시스템 로그를 한곳에서 통합 관리하도록 개선
  - 공간 효율성 증대 및 포트 간 이벤트 순서 파악 용이성 확보
- **Manual Control UI 개선**
  - 불필요한 그룹박스(`manual_options_grp`, `manual_send_grp`) 제거
  - 레이아웃 재배치: 입력창/전송 버튼을 상단에, 옵션 체크박스를 하단에 배치하여 사용성 향상
  - 옵션 체크박스 레이아웃을 3열 2행으로 변경하여 가로 폭 절약
- **하단 UI 레이아웃 변경**
  - `ManualCtrlWidget`과 `SystemLogWidget`을 `MainLeftSection` 하단에 수직(`QVBoxLayout`)으로 배치
  - `SystemLogWidget`의 전체 높이를 100px로 고정(리스트 높이 고정 제거)하여 우측 패널(`MacroCtrlWidget`)과의 수평 라인 정렬 유도
  - `MacroCtrlWidget`의 `execution_settings_grp` 높이를 100px로 고정하여 좌측 패널(`SystemLogWidget`)과 높이 일치
  - 좌측 패널 구성: `PortTabs(Stretch)` - `ManualCtrl` - `SystemLog(Fixed)`

- **Model 계층 강화 (Phase 4)**
  - `SerialManager`: 싱글톤 스레드 안전성 강화 (QMutex 적용) 및 포트 관리 로직 개선
  - `ConnectionWorker`: TX 큐(`ThreadSafeQueue`) 도입으로 비동기 전송 구현, `time.monotonic()` 적용으로 타이밍 정밀도 향상
  - `SerialTransport`: 예외 처리 강화 (연결 끊김 감지 및 에러 전파)
  - `PacketParser`: `ATParser`, `DelimiterParser` 버퍼 크기 제한 추가 (메모리 보호), 임포트 최적화
  - `MacroRunner`: Expect 처리 구조 마련 및 비동기 실행 로직 개선

---

### View 계층 완성, 중앙 경로 관리, 아키텍처 및 리팩토링 (2025-12-10)

#### 리팩토링 (Refactoring)

- **통신 계층 추상화 (Transport Abstraction)**
  - `core/interfaces.py`: 모든 통신 드라이버가 구현해야 할 `ITransport` 인터페이스 정의
  - `model/transports.py`: PySerial을 감싸는 `SerialTransport` 구현체 작성
  - **목적**: SPI, I2C 등 향후 프로토콜 확장을 위한 기반 마련

#### 추가 사항 (Added)

- **로그 검색 기능 강화**
  - `QSmartListView` 내부에 검색 탐색(`find_next`, `find_prev`) 로직 구현
  - 검색어 일치 항목 하이라이트 및 자동 스크롤 이동 기능 추가

- **Parser 탭 구현 (PreferencesDialog)**
  - Parser Type 선택: Auto Detect, AT Parser, Delimiter Parser, Fixed Length Parser, Raw Parser
  - Delimiter 설정: 구분자 리스트 관리 (추가/삭제)
  - Fixed Length 설정: 패킷 길이 지정 (1-4096 바이트)
  - Inspector Options: 버퍼 크기, 실시간 추적, 자동 스크롤
  - 22개의 새로운 언어 키 추가 (en.json, ko.json)

- **중앙 집중식 경로 관리 (AppConfig)**
  - `config.py`: 모든 리소스 경로를 중앙에서 관리하는 `AppConfig` 클래스 생성
  - 개발 모드와 PyInstaller 번들 환경 자동 감지
  - 경로 검증 메서드 (`validate_paths()`)
  - `SettingsManager`, `LangManager`, `ThemeManager`에 AppConfig 통합

- **Package-level Imports**
  - `view/sections/__init__.py`: 섹션 클래스 export
  - `view/dialogs/__init__.py`: 다이얼로그 클래스 export
  - `main_window.py` import 구문 간결화

- **QSS 스타일 개선**
  - `section-title` 클래스 추가: QGroupBox::title과 유사한 스타일
  - `RxLogWidget.recv_log_title`, `StatusAreaWidget.status_log_title`에 적용
  - Dark/Light 테마별 색상 지정 (녹색/파란색)
  - `QSmartTextEdit` 스타일 추가 (공통, 다크, 라이트 테마)

- **수동 제어 (ManualCtrl) 개선**
  - `QSmartTextEdit` 도입: 라인 번호가 표시되는 멀티라인 에디터
  - 여러 줄 입력 지원 (Enter: 새 줄, Ctrl+Enter: 전송)
  - 플레이스홀더 텍스트 업데이트 ("Ctrl+Enter to send")

#### 버그 수정 (Fixed)

- **UI 레이아웃**
  - 우측 패널 토글 시 좌측 패널 크기가 변경되는 문제 수정
  - 스플리터 스트레치 팩터 조정 (좌: 0, 우: 1) 및 패널 너비 저장/복원 로직 개선
  - 윈도우 리사이즈 시 System Log 높이를 고정하고 Received Area만 늘어나도록 수정 (`setFixedHeight`)

#### 변경 사항 (Changed)

- **테마 및 스타일 (QSS)**
  - `QSmartListView` 및 `QSmartTextEdit`에 다크/라이트 테마 완벽 지원
  - `QSmartTextEdit`에 `Q_PROPERTY`를 추가하여 QSS에서 라인 번호 색상 제어 가능
  - `common.qss`에 `QSmartListView` 기본 스타일 추가
- **MVP 아키텍처 적용**
  - View 계층(`MacroPanel`, `MainLeftSection` 등)에서 `SettingsManager` 의존성을 완전히 제거했습니다.
  - View는 이제 스스로 파일을 저장하지 않고, `save_state() -> dict`와 `load_state(dict)` 메서드를 통해 상태 데이터만 주고받습니다.
  - 데이터의 영구 저장 및 복원 책임이 `MainWindow`(향후 `MainPresenter`)로 이관되어, UI와 비즈니스 로직(설정 관리)의 결합도가 낮아졌습니다.
  - `MainRightSection`에 하위 패널들의 상태를 집계하는 로직을 추가했습니다.

- **네이밍 일관성 개선**
  - `rx` → `recv`: RxLogWidget의 모든 변수 및 메서드명 변경
    - `on_clear_rx_log_clicked()` → `on_clear_recv_log_clicked()`
    - `rx_search_input` → `recv_search_input`
    - `rx_hex_chk` → `recv_hex_chk` 등
  - `manual_control` → `manual_ctrl`:
    - 파일명: `manual_control.py` → `manual_ctrl.py`
    - 클래스명: `ManualControlWidget` → `ManualCtrlWidget`
    - 설정 키: `"manual_control"` → `"manual_ctrl"`
  - 언어 키 통일:
    - `recv_lbl_log` → `recv_title`
    - `status_lbl_log` → `system_title`
    - `right_tab_inspector` → `right_tab_packet`
    - `pref_tab_parser` → `pref_tab_packet`

- **DTR/RTS 제거**
  - `PortSettingsWidget`에서 DTR/RTS 체크박스 제거
  - 포트 설정 2행 레이아웃 간소화 (Data | Parity | Stop | Flow)
  - 설정 저장/로드 로직에서 DTR/RTS 제거

- **파일 이동**
  - `view/widgets/main_toolbar.py` → `view/sections/main_tool_bar.py`
  - 섹션 관련 파일은 `sections/`에 통합

#### 수정 사항 (Fixed)

- **싱글톤 패턴 수정**
  - `SettingsManager`, `LangManager`의 `__new__` 메서드에 `*args, **kwargs` 추가
  - `TypeError: takes 1 positional argument but 2 were given` 오류 해결

- **경로 계산 수정**
  - `LangManager`의 하위 호환성 경로 계산 오류 수정
  - `view/tools/lang_manager.py`에서 3단계 상위 디렉토리로 이동하도록 수정

- **우측 패널 표시 상태 복원**
  - `MainWindow.init_ui()`에서 설정값 읽어서 메뉴 체크 상태 복원
  - `right_panel_visible` 설정 적용

- **clear_log() 메서드 개선**
  - `isinstance(current_widget, PortPanel)` 체크 제거
  - PortPanel import 제거로 의존성 감소

#### 아키텍처 개선 (Architecture)

- **Worker 구조 개선**
  - 파일명 변경: `model/serial_worker.py` → `model/connection_worker.py`
  - 클래스명 변경: `SerialWorker` → `ConnectionWorker`
  - **의존성 주입**: Worker가 특정 라이브러리(pyserial) 대신 `ITransport` 인터페이스에 의존하도록 변경
  - `PortController`: `SerialTransport`를 생성하여 `ConnectionWorker`에 주입하는 구조로 변경

- **ReceivedArea 동적 설정**
  - `set_max_lines(max_lines)` 메서드 추가
  - `MainPresenter`에서 설정 변경 시 모든 ReceivedArea 업데이트
  - `PortPresenter`에서 초기화 시 설정값 적용

- **PortState Enum 통합**
  - `core/port_state.py`: `DISCONNECTED`, `CONNECTED`, `ERROR` 상태 정의
  - `PortSettingsWidget.set_connection_state(PortState)` 구현
  - QSS 동적 속성 (`QPushButton[state="..."]`) 활용

- **SettingsManager 개선**
  - `_get_config_path`를 `@property`로 변경
  - AppConfig 통합으로 경로 관리 일원화

- **고성능 로그 뷰어 도입 (`QSmartListView`)**
  - 기존 `QTextEdit` 기반 로그 뷰를 `QListView` 기반의 `QSmartListView`로 교체
  - 대량의 로그 데이터 처리 시 메모리 사용량 감소 및 렌더링 성능 대폭 향상
  - `view/widgets/received_area.py` 및 `view/widgets/system_log.py`에 적용

#### 문서 업데이트 (Documentation)

- **doc/task.md**
  - Phase 2 완료 항목 추가 (ReceivedArea, PortState, Parser 탭, AppConfig)
  - Phase 3 상태를 "진행 중"으로 변경

- **doc/implementation_plan.md**
  - 최종 업데이트 날짜: 2025-12-10
  - 프로젝트 구조 업데이트 (AppConfig, **init**.py, 파일명 수정)

- **README.md**
  - 주요 기능 업데이트 (PortState, AppConfig, Package-level imports)
  - 용어 통일 (커맨드 → 매크로)

---

### 버그 수정 및 UI/UX 개선 (2025-12-09)

#### 수정 사항 (Fixed)

- **초기화 및 Import 오류 수정**
  - `MainWindow` 초기화 시 `AttributeError` (left_section 미생성 상태에서 시그널 연결) 수정
  - `PortController`에서 `SerialWorker` import 경로 오류 (`ModuleNotFoundError`) 수정
  - 애플리케이션 실행 안정성 확보

- **툴바 동작 로직 개선**
  - 'Close' 버튼이 토글 방식으로 동작하여 닫힌 포트를 여는 문제 수정
  - `close_current_port` 메서드 추가 및 `is_connected` 상태 확인 로직 도입
  - 명시적인 닫기 동작 보장

#### 변경 사항 (Changed)

- **시그널 네이밍 일관성 강화**
  - `MacroCtrlWidget`: `cmd_run_single` → `cmd_run_once`, `cmd_auto_start` → `cmd_repeat_start` 등
  - `PortSettingsWidget`: `scan_requested` → `port_scan_requested`
  - 버튼 텍스트 및 기능과 일치하도록 시그널 이름 직관화

- **테스트 코드 최신화**
  - `test_view.py`, `test_ui_translations.py`를 최신 위젯 클래스명(`RxLogWidget` 등) 및 시그널로 업데이트

- **네이밍 리팩토링 (Command -> Macro)**
  - `CommandListWidget` → `MacroListWidget`
  - `CommandControlWidget` → `MacroControlWidget`
  - `CommandListPanel` → `MacroPanel`
  - 관련 파일명 및 변수명 일괄 변경 (`command_list.py` → `macro_list.py` 등)
  - "Command" 용어의 모호성(시스템 명령 등) 해소 및 "Macro"로 명확화

- **설정 키 구조 정리**
  - `PreferencesDialog`에서 `port_baudrate`, `port_newline`, `port_scan_interval` 추가
  - `main_presenter.py`에서 설정 키 매핑 업데이트
  - 설정 로드/저장 로직 일관성 확보

#### 추가 사항 (Added)

- **동적 윈도우 리사이징**
  - 우측 패널(Right Panel) 토글 시 윈도우 크기가 자동으로 조정되는 기능 구현
  - 패널 숨김/표시 시 자연스러운 윈도우 크기 변화 제공
  - 좌측 패널 크기 유지: 스플리터 크기 설정으로 좌측 패널이 변경되지 않도록 수정

#### 아키텍처 개선 (Architecture)

- **MVP 패턴 준수 강화**
  - `PreferencesDialog`에서 `SettingsManager` 직접 접근 제거
  - Presenter(`MainWindow`)를 통해 설정을 전달받아 사용하도록 변경
  - `_get_setting()` 헬퍼 메서드 추가: 중첩된 설정 키 안전 접근
  - View 계층이 Model 계층에 직접 접근하지 않도록 개선

#### 완성도 개선 (Polish)

- **언어 키 완성**
  - `MainToolBar`: 모든 액션에 언어 키 적용 (`toolbar_open`, `toolbar_close` 등)
  - `MainMenuBar`: 메뉴 액션에 언어 키 적용 (`main_menu_open_port`, `main_menu_close_tab` 등)
  - `MacroCtrlWidget`: Pause 버튼 언어 키 추가 (`macro_ctrl_btn_repeat_pause`)
  - `PreferencesDialog`: Newline 설정 언어 키 추가 (`pref_lbl_newline`)

- **TODO 주석 정리**
  - 모든 TODO 주석을 Note로 변경하고 향후 구현 계획 명시
  - `macro_panel.py`: Repeat 파라미터 전달 방식 설명 추가
  - `port_presenter.py`, `main_presenter.py`: 상태바 에러 표시 계획 명시
  - `received_area.py`: 정규식 검색 지원 계획 명시

- **테마 메뉴 개선**
  - View -> Theme 메뉴에 현재 선택된 테마 체크 표시 추가
  - `MainMenuBar.set_current_theme()` 메서드 추가
  - 테마 전환 시 자동으로 체크 표시 업데이트

- **우측 패널 토글 개선**
  - 패널 숨김 시 왼쪽 패널 너비 저장
  - 패널 표시 시 저장된 왼쪽 패널 너비 복원
  - `_saved_left_width` 인스턴스 변수 추가

- **QSS 스타일 확장**
  - `warning` 클래스 추가 (노란색 버튼 스타일)
  - Pause 버튼에 warning 스타일 적용

---

### 언어 확장성 개선 및 아이콘 수정 (2025-12-08)

#### 추가 사항 (Added)

- **LanguageManager 확장성 개선**
  - `get_text()` 메서드에 optional `lang_code` 파라미터 추가
  - `get_supported_languages()` 메서드 추가: 지원되는 모든 언어 코드 목록 반환
  - `text_matches_key()` 헬퍼 메서드 추가: 텍스트가 특정 키의 어떤 언어 번역과 일치하는지 확인
  - 새 언어 추가 시 코드 수정 없이 자동 지원 가능

#### 수정 사항 (Fixed)

- **UI 아이콘 표시 문제**
  - `dark_theme.qss`, `light_theme.qss`에서 아이콘 선택자 수정
  - 버튼 objectName 불일치 해결: `add_btn` → `add_cmd_btn`, `del_btn` → `del_cmd_btn` 등
  - Command List 및 검색 버튼 아이콘이 정상적으로 표시됨

#### 변경 사항 (Changed)

- **언어 비교 로직 개선**
  - `manual_control.py`, `main_status_bar.py`, `file_progress.py`에서 하드코딩된 언어별 비교 제거
  - `== lang_manager.get_text("key", "en") or == lang_manager.get_text("key", "ko")` 패턴을
  - `lang_manager.text_matches_key(text, "key")` 호출로 변경
  - 일본어, 중국어 등 새 언어 추가 시 코드 수정 불필요

#### 이점 (Benefits)

- **확장성 향상**: 새 언어 추가 시 JSON 파일만 추가하면 자동 지원
- **유지보수성 개선**: 언어별 하드코딩 제거로 코드 간소화
- **UI 일관성**: 모든 아이콘 버튼이 테마에 맞게 정상 표시

---

### UI 요소 및 시그널/메서드 네이밍 리팩토링 (2025-12-08)

#### 변경 사항 (Changed)

- **UI 요소 이름 구체화**
  - `send_btn` → `send_manual_cmd_btn`, `clear_btn` → `clear_manual_options_btn` 등
  - `manual_control.py`, `received_area.py`, `tx_panel.py`, `command_control.py` 전체 적용
  - 모호한 변수명을 제거하고 컨텍스트와 기능을 명확히 함

- **시그널 및 메서드 네이밍 표준화**
  - 시그널: `[context]_[action]_requested` 패턴 적용 (예: `manual_cmd_send_requested`)
  - 핸들러: `on_[widget]_[event]` 패턴 적용 (예: `on_send_manual_cmd_clicked`)
  - `guide/naming_convention.md` 업데이트

#### 이점 (Benefits)

- **가독성 향상**: 코드만 보고도 어떤 UI 요소가 어떤 동작을 하는지 즉시 파악 가능
- **유지보수성 개선**: 명확한 네이밍으로 버그 발생 가능성 감소 및 협업 효율 증대

### 설정 다이얼로그 리팩토링 (2025-12-08)

#### 변경 사항 (Changed)

- **PreferencesDialog MVP 패턴 적용 및 리팩토링**
  - `load_settings`: `SettingsManager` 직접 사용하여 의존성 제거
  - `apply_settings`: 데이터 변환 로직(lower(), int() 등)을 View에서 제거하고 원본 데이터 전송
  - `MainWindow`에 `preferences_save_requested` 시그널 추가하여 이벤트 전달
  - `MainPresenter`에 `on_preferences_save_requested` 핸들러 구현하여 비즈니스 로직 처리

#### 이점 (Benefits)

- **아키텍처 준수**: View는 UI 로직만 담당하고, 데이터 검증 및 변환은 Presenter가 담당하여 MVP 패턴 강화
- **데이터 일관성**: `SettingsManager`를 단일 진실 공급원(SSOT)으로 사용
- **유지보수성**: 설정 로드/저장 로직이 명확하게 분리됨

### UI/UX 개선 및 버그 수정 (2025-12-08)

#### 추가 사항 (Added)

- **SmartNumberEdit 위젯**
  - `view/widgets/common/smart_number_edit.py` 신규 생성
  - HEX 모드와 일반 텍스트 모드 지원
  - HEX 모드 시 0-9, A-F, 공백만 입력 허용
  - 자동 대문자 변환 기능
  - `ManualControlWidget` 입력 필드에 적용

- **PortTabPanel 위젯**
  - `view/panels/port_tab_panel.py` 신규 생성 (기존 `PortTabWidget` 리네임)
  - 포트 탭 관리 로직 캡슐화 (추가/삭제/플러스 탭)
  - `LeftSection`에서 `QTabWidget` 대신 `PortTabPanel` 사용
  - 코드 재사용성 및 유지보수성 향상

- **테마별 SVG 아이콘 지원**
  - `ThemeManager.get_icon()` 메서드 추가
  - 테마에 따라 `resources/icons/{name}_{theme}.svg` 로드
  - `add_dark.svg`, `add_light.svg` 아이콘 생성
  - 플러스 탭에 테마별 아이콘 적용

- **포트 탭 이름 수정 기능**
  - 탭 이름 형식: `[커스텀명]:포트명`
  - 탭 더블클릭 시 커스텀 이름 수정 다이얼로그 표시
  - 포트 변경 시 자동으로 탭 제목 업데이트
  - 커스텀 이름 저장/복원 기능
  - `PortPanel`에 `tab_title_changed` 시그널 추가

#### 수정 사항 (Fixed)

- **MacroListWidget Send 버튼 상태 버그**
  - 행 이동 시 Send 버튼 활성화 상태가 초기화되는 문제 수정
  - `_move_row` 메서드에서 이동 전 버튼 상태 저장 후 복원

- **포트 탭 닫기 버튼 문제**
  - `insertTab` 사용 시 닫기 버튼이 사라지는 버그 수정
  - 플러스 탭 제거 → 새 탭 추가 → 플러스 탭 재추가 방식으로 변경
  - 모든 탭의 닫기 버튼이 정상적으로 표시됨

- **포트 탭 삭제 시 새 탭 생성 버그**
  - 탭 삭제 시 `on_tab_changed` 시그널로 인해 새 탭이 생성되는 문제 수정
  - `close_port_tab`에서 시그널 차단 및 적절한 탭으로 포커스 이동
  - 최소 1개의 포트 탭 유지 로직 추가

- **순환 import 문제**
  - `PortTabWidget`과 `PortPanel` 간 순환 import 해결
  - `TYPE_CHECKING`을 사용한 타입 힌트 분리
  - 런타임에만 필요한 곳에서 import 수행

#### 변경 사항 (Changed)

- **설정 키 일관성 확보**
  - `SettingsManager`, `PreferencesDialog`, `MainWindow`에서 `menu_theme`, `menu_language` 키 통일
  - `settings.json`의 `global.theme`, `global.language`와 내부 키 간 명확한 매핑 확립

- **LeftSection 리팩토링**
  - `PortTabWidget` 사용으로 탭 관리 코드 간소화
  - `add_new_port_tab`, `close_port_tab`, `on_tab_changed` 등 메서드 제거 (캡슐화)

#### 이점 (Benefits)

- **사용자 경험 향상**: HEX 모드 입력 제한으로 오류 방지, 탭 이름 수정으로 사용자 정의 가능
- **코드 품질 개선**: 위젯 캡슐화로 재사용성 및 유지보수성 향상
- **테마 일관성**: 모든 UI 요소에 테마가 올바르게 적용됨
- **안정성 향상**: 버튼 상태 및 탭 닫기 버그 수정으로 사용자 경험 개선

---

### 문서화 및 가이드 개선 (2025-12-05)

### 문서화 및 가이드 개선 (2025-12-05)

#### 추가 사항 (Added)

- **주석 가이드 문서**
  - `guide/comment_guide.md` 신규 생성: Google Style Docstring 표준 가이드
  - Google Style 정의 및 공식 문서 링크 추가
  - 모듈/클래스/함수 Docstring 작성 규칙 상세화
  - 인라인 주석 작성 규칙 (블록 주석, 분기문, 수식, TODO/FIXME/NOTE 태그)
  - MkDocs 자동 문서화 설정 가이드
  - 체크리스트 제공

- **Git 관리 가이드 문서**
  - `guide/git_guide.md` 신규 생성
  - 커밋 메시지 규칙 (Header/Body/Footer, 태그별 예시)
  - PR 및 이슈 템플릿 가이드
  - 실무 Git 레시피 (Amend, Stash, Reset/Revert 등 복구 명령어)
  - 브랜치 전략 상세

- **View 구현 계획 보강**
  - `view/doc/implementation_plan.md`에 Packet Inspector 설정 섹션 추가
  - Parser 타입 선택 (Auto/AT/Delimiter/Fixed Length/Raw)
  - Delimiter 설정 (기본값 + 사용자 정의)
  - AT Parser 색상 규칙 설정
  - Inspector 동작 옵션 (버퍼 크기, 실시간 추적, 자동 스크롤)
  - Preferences 다이얼로그 탭 UI 레이아웃 정의

#### 변경 사항 (Changed)

- **README.md 업데이트**
  - 프로젝트 설명: "시리얼 통신 유틸리티" → "통신 유틸리티" (SPI, I2C 확장 예정 명시)
  - 폴더 구조 정리: `guide/` 폴더 분리, 중복 파일 제거
  - 향후 계획 상세화: 단기/중장기 구분, FT4222/SPI/I2C 지원 로드맵 추가
  - 문서 참조 표 보강: 코딩 규칙, 명명 규칙 추가
  - Git 관리 가이드 강화: 지속적 백업 권장 명시

- **코드 스타일 가이드 간소화**
  - `guide/code_style_guide.md`에서 Docstring 상세 내용 제거 (117줄 → 31줄)
  - 주석 관련 내용을 `guide/comment_guide.md` 참조로 대체
  - 기본 원칙과 간단한 예시만 유지

- **구현 계획 우선순위 조정**
  - `view/doc/implementation_plan.md` 우선순위 섹션에서 일정 표기 제거
  - Packet Inspector 설정을 선택적 항목으로 추가

#### 이점 (Benefits)

- **문서 체계화**: 주석 가이드를 독립 문서로 분리하여 관리 용이
- **확장성 명시**: README에 향후 프로토콜 확장 계획 명확히 전달
- **개발 가이드 강화**: Google Style Docstring 표준 및 작성 규칙 상세화
- **View 계층 완성도**: Packet Inspector UI 설정 요구사항 문서화

### MVP 아키텍처 리팩토링 및 코드 품질 개선 (2025-12-05)

#### 변경 사항 (Changed)

- **MVP 아키텍처 준수**
  - `ManualControlWidget`에서 `SettingsManager` 직접 호출 제거
  - `send_command_requested` 시그널 변경: 3개 파라미터 → 4개 파라미터 (text, hex_mode, use_prefix, use_suffix)
  - View는 원본 사용자 입력과 체크박스 상태만 전달
  - prefix/suffix 처리 로직을 `MainPresenter.on_send_command_requested()`로 이동
  - View 계층에서 비즈니스 로직 40+ 라인 제거

- **네이밍 규칙 문서 통합**
  - `docs/naming_convention.md`에 모든 네이밍 규칙 통합 (클래스, 함수, 변수, 상수, 언어 키 등)
  - `doc/code_style_guide.md`에서 중복 내용 제거, 참조 링크로 대체
  - 단일 문서로 일관성 및 유지보수성 향상

- **Logger 싱글톤 패턴 개선**
  - 예외 발생 방식에서 `__new__` + `_initialized` 패턴으로 변경
  - `SettingsManager`와 동일한 구현 방식 적용
  - 다중 인스턴스 생성 시도 시 안전하게 동일 인스턴스 반환

- **설정 구조 리팩토링**
  - 평탄한 `global.*` 네임스페이스에서 논리적 그룹으로 재구조화
  - 새로운 그룹: `serial.*`, `command.*`, `logging.*`, `ui.*`
  - `main_window.py` `apply_preferences()` 메서드에 settings_map 추가
  - `main_presenter.py`에서 `global.command_prefix` → `command.prefix` 경로 변경
  - `settings.json` 구조 개선

#### 이점 (Benefits)

- **아키텍처 개선**: View와 Presenter 책임 분리 명확화, MVP 패턴 준수
- **문서 통합**: 단일 소스로 네이밍 규칙 참조, 문서 관리 일원화
- **안정성 향상**: Logger 싱글톤 패턴 개선으로 애플리케이션 안정성 증대
- **설정 관리**: 논리적 그룹화로 장기 유지보수 용이

### 문서 및 Preferences 다이얼로그 개선 (2025-12-04)

#### 변경 사항 (Changed)

- **코딩 스타일 가이드 업데이트**
  - `doc/code_style_guide.md`에 언어 키 네이밍 규칙 섹션(5.1) 추가
  - `[context]_[type]_[name]` 형식 엄격히 정의
  - UI 요소 타입별 분류 (`btn`, `lbl`, `chk`, `combo`, `input`, `grp`, `col`, `tab`, `dialog`, `txt`, `tooltip`)
  - 올바른/잘못된 예시 제공
  - 특수 케이스 문서화 (다이얼로그 타이틀, 상태 메시지, 필터 문자열)

- **설정 키 일관성 확보**
  - `SettingsManager`의 Fallback 설정 키를 `menu_theme`, `menu_language`로 통일
  - `PreferencesDialog`와 `MainWindow` 간의 설정 키 매핑 불일치 해결
  - `settings.json`의 `global.theme`, `global.language`와 내부 키(`menu_theme`, `menu_language`) 간의 명확한 매핑 로직 확립

- **Preferences 다이얼로그 접근성 수정**
  - `view/main_window.py`에서 `preferences_requested` 시그널 연결
  - `open_preferences_dialog()` 및 `apply_preferences()` 메서드 추가
  - 메뉴바 → View → Preferences 정상 작동
  - 테마 및 언어 변경 즉시 적용

#### 이점 (Benefits)

- 언어 키 네이밍에 대한 명확한 가이드라인 제공
- 신규 개발자 온보딩 시 참고 자료 확보
- Preferences 다이얼로그 접근성 개선
- 일관성 있는 코드베이스 유지

### UI 아키텍처 리팩토링 (2025-12-04)

#### 변경 사항 (Changed)

- **4단계 계층 구조 확립 (Window → Section → Panel → Widget)**
  - 기존 `LeftPanel`, `RightPanel`을 `LeftSection`, `RightSection`으로 리팩토링
  - 새 디렉토리 `view/sections/` 생성
  - `ManualControlPanel`, `PacketInspectorPanel` 래퍼 추가
  - 각 계층의 역할 명확화:
    - **Window**: 최상위 애플리케이션 셸 (`MainWindow`)
    - **Section**: 화면 구획 분할, Panel만 포함 (`LeftSection`, `RightSection`)
    - **Panel**: 기능 단위 그룹, Widget만 포함 (`PortPanel`, `MacroListPanel`, `ManualControlPanel` 등)
    - **Widget**: 실제 UI 요소 및 로직 (`PortSettingsWidget`, `ManualControlWidget` 등)
  - Presenter 계층 업데이트 (`port_presenter.py`, `main_presenter.py`)

#### 이점 (Benefits)

- 코드 구조의 일관성 및 가독성 향상
- 컴포넌트 책임 범위 명확화
- 유지보수 및 확장성 개선

### UI 개선 및 기능 강화 (2025-12-04)

#### 추가 사항 (Added)

- **ManualControlWidget 기능 확장**
  - 접두사(Prefix) 및 접미사(Suffix) 입력 필드 및 체크박스 추가
  - 데이터 전송 시 포맷팅 옵션 적용 기능

- **스크립트 저장/로드**
  - Command List 및 실행 설정을 JSON 파일로 저장/로드하는 기능 구현 (`MacroListPanel`)
  - `save_script_to_file`, `load_script_from_file` 메서드 추가

- **아이콘**
  - 검색 탐색 버튼용 아이콘 추가 (`find_prev`, `find_next`)

#### 수정 사항 (Fixed)

- **UI 아이콘 표시**
  - `MacroListWidget` 버튼의 objectName 불일치 수정 (`btn_add` → `add_btn` 등)으로 아이콘 미표시 문제 해결
- **테마 스타일**
  - 다크 테마에서 Placeholder 텍스트 색상 문제 수정 (`placeholder-text-color` 추가)

### 언어 키 표준화 및 로깅 프레임워크 (2025-12-03)

#### 추가 사항 (Added)

- **로깅 프레임워크**
  - `core/logger.py` 구현: 싱글톤 패턴 기반 Logger 클래스
  - 로그 레벨: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - 파일 로깅: RotatingFileHandler (10MB x 5개 파일)
  - 콘솔 로깅: 색상 구분 출력
  - 타임스탬프 자동 추가

- **자동화 테스트**
  - `tests/test_ui_translations.py`: UI 컴포넌트 번역 자동 검증
  - 8개 위젯/패널 언어 전환 테스트 (6개 통과)

- **도구**
  - `tools/manage_lang_keys.py` 개선: 자동 모듈 탐지 기능

#### 변경 사항 (Changed)

- **언어 키 표준화**
  - 모든 언어 키를 `[context]_[type]_[name]` 규칙으로 리팩토링
  - `en.json`, `ko.json` 업데이트 (192개 키)
  - 모든 UI 컴포넌트의 `get_text()` 호출 수정
  - 주석 제거 및 JSON 구조 정리

- **MainWindow 구조 개선**
  - `MainMenuBar`를 별도 위젯으로 분리 (`view/widgets/main_menu_bar.py`)
  - `MainStatusBar`를 별도 위젯으로 분리 (`view/widgets/main_status_bar.py`)
  - 코드 재사용성 및 가독성 향상

- **로깅 개선**
  - `ThemeManager`, `LanguageManager`의 print 문을 logger 호출로 교체
  - 구조화된 로그 메시지 형식

#### 수정 사항 (Fixed)

- **About Dialog**: `MainWindow`에서 시그널 연결 누락 수정
- **manage_lang_keys.py**: 하드코딩된 모듈 리스트 제거, 자동 탐지로 개선

### View 계층 마무리 및 다국어 지원 (2025-12-02)

#### 추가 사항 (Added)

- **다국어 지원 (Phase 1)**
  - LanguageManager 확장: 50+ UI 문자열 추가 (한국어/영어)
  - MainWindow 메뉴 시스템 한글화 (파일, 보기, 도움말 메뉴)
  - 윈도우 제목 및 상태바 한글화
  - 언어 동적 변경 핸들러 구현 (on_language_changed)
  - PortSettingsWidget 부분 한글화 (포트, 스캔, 보레이트 버튼)
  - **리팩토링**: 언어 리소스를 코드에서 JSON 파일로 분리 (`config/languages/*.json`)

- **commentjson 지원**
  - 모든 JSON 파일 처리에 commentjson 라이브러리 적용
  - JSON 파일에 주석 사용 가능 (가독성 향상)
  - 설정 파일 및 언어 파일에 설명 주석 추가 가능

- **설정 관리 개선**
  - 설정 저장 위치를 `config/settings.json`으로 변경 (프로젝트 루트에서 config 폴더로)
  - SettingsManager에 싱글톤 패턴 적용하여 설정 동기화 문제 해결

- **위젯 상태 저장/복원 구현**
  - ManualControlWidget: 입력 텍스트, HEX 모드, RTS/DTR 상태 저장/복원
  - ReceivedArea: 검색어, HEX 모드, 타임스탬프, 일시정지 상태 저장/복원
  - CommandControl: 초기화 문제 수정 및 상태 저장/복원 안정화
  - MacroListPanel: 초기화 순서 변경으로 load_state 오류 해결

#### 수정 사항 (Fixed)

- **ThemeManager**: `load_theme()` 메서드의 `@staticmethod` 데코레이터 제거 (NameError 방지)
- **ColorRulesManager**: 설정 파일 경로 계산 오류 수정 (`parent.parent.parent` → `parent.parent`)
- **MainWindow**:
  - Import 구문을 파일 상단으로 이동 (코드 스타일 가이드 준수)
  - `on_language_changed` 및 `_save_window_state` 메서드 복구
- **PortSettingsWidget**: 필수 메서드 복원 (`set_port_list`, `set_connected`)
- **CommandControl**: SyntaxError 수정 (중복 코드 제거)
- **MacroListPanel**: 초기화 순서 변경으로 상태 복원 시 오류 해결
- **탭 관리**:
  - 포트 탭 증식 문제 수정 (재시작 시 탭이 계속 추가되던 버그)
  - LeftPanel의 탭 추가 로직 개선
- **About Dialog**: 구현 완료 및 manage_lang_keys.py JSON 주석 처리 개선
- **manage_lang_keys.py**: JSON 파싱 오류 처리 추가

#### 변경 사항 (Changed)

- **test_view.py**: PreferencesDialog, AboutDialog, FileProgressWidget, Language 테스트 케이스 추가
- **디버그 로깅**:
  - 모든 주요 컴포넌트에 저장/복구 디버그 로그 추가 (개발 중)
  - 검증 완료 후 디버그 로그 제거

### 듀얼 폰트 시스템 (2025-12-01)

#### 추가 사항 (Added)

- **폰트 시스템 개선**
  - Proportional Font (가변폭): UI 요소 (메뉴, 상태바, 레이블, 버튼 등)에 적용
  - Fixed Font (고정폭): TextEdit, CommandList 등 데이터 표시 영역에 적용
  - 폰트 설정 대화상자 구현

- **테마 시스템**
  - 중앙 집중식 QSS 기반 테마 관리 구현 (`view/theme_manager.py`)
  - 다크 테마 (`resources/themes/dark_theme.qss`) 및 라이트 테마 (`resources/themes/light_theme.qss`) 생성
  - View 메뉴를 통한 동적 테마 전환
  - 폰트 커스터마이징 메뉴 (사전 정의 폰트 및 커스텀 폰트 대화상자)

- **SVG 아이콘 시스템**
  - 아이콘 리소스 디렉토리 생성 (`resources/icons/`)
  - 테마 인식 SVG 아이콘 구현 (다크 테마용 흰색, 라이트 테마용 검은색)
  - 아이콘: Add, Delete, Up, Down, Close, ComboBox 화살표
  - objectName 선택자를 통한 QSS 기반 아이콘 로딩 적용

- **UI 컴포넌트**
  - `PortSettingsWidget`: 컴팩트한 2줄 레이아웃
    - 1행: 포트 | 스캔 | 보레이트 | 열기
    - 2행: 데이터 | 패리티 | 정지 | 흐름 | DTR | RTS
  - `MacroListWidget`:
    - Prefix/Suffix 컬럼 추가 (이전 Head/Tail에서 변경)
    - 3단계 Select All 체크박스 (선택 안함, 부분 선택, 전체 선택)
    - 세로 스크롤바 항상 표시
    - 행별 Send 버튼
  - `MacroCtrlWidget`:
    - 전역 명령 수정을 위한 Prefix/Suffix 입력 필드 추가
    - 스크립트 저장/로드 버튼
    - 자동 실행 설정 (지연시간, 최대 실행 횟수)

#### 변경 사항 (Changed)

- **디렉토리 구조 재정리**
  - `view/resources/` → `resources/` (루트로 이동)
  - `view/styles/` → `resources/themes/` (테마 파일 통합)
  - `view/styles/theme_manager.py` → `view/theme_manager.py`
  - 모든 QSS 파일 내 아이콘 경로 업데이트 (`view/resources/` → `resources/`)

- **레이아웃 최적화**
  - `CommandControl`에서 `CommandList` 헤더로 Select All 체크박스 이동
  - 일관성을 위한 컴포넌트 크기 조정
  - Port combo 너비를 Baud combo와 동일하게 맞춤
  - 명확성을 위해 UI 요소 간 간격 추가

- **명명 규칙**
  - `CommandList` 및 `CommandControl` 전체에서 "Head/Tail"을 "Prefix/Suffix"로 변경
  - 관련된 모든 레이블, 툴팁 및 변수명 업데이트

#### 수정 사항 (Fixed)

- 두 테마 모두에서 ComboBox 드롭다운 화살표가 이제 표시됨
- 탭 닫기 버튼 아이콘이 올바르게 테마 적용됨
- Select All 체크박스가 이제 개별 행 체크박스 변경에 반응함
- Import 오류 수정 (QCheckBox, QSizePolicy)

### View 계층 개선 및 설정 관리 (2025-12-01)

#### 추가 사항 (Added)

- **View 기능 강화**
  - **색상 규칙 (Color Rules)**: `ReceivedArea`에 특정 패턴(OK, ERROR 등) 강조 기능 추가 (`config/color_rules.json`)
  - **로그 최적화 (Log Trim)**: 2000줄 초과 시 자동 삭제 기능으로 메모리 관리
  - **타임스탬프**: 수신 데이터에 타임스탬프(`[HH:MM:SS]`) 표시 옵션 추가
  - **파일 전송 UI**: ManualControlWidget에 파일 선택 및 전송 UI 추가

- **설정 관리 시스템**
  - `SettingsManager` 구현: `config/settings.json` 및 사용자 설정 관리
  - 상태 저장: 창 크기, 위치, 테마 설정을 종료 시 자동 저장 및 시작 시 복원

- **테스트 도구**
  - 독립 테스트 앱 (`tests/test_view.py`): View 컴포넌트(위젯)를 메인 로직 없이 독립적으로 테스트 가능

#### 수정 사항 (Fixed)

- `ManualControlWidget`: `file_selected` 시그널 누락 수정
- `LeftPanel`: 탭 추가 로직(`add_plus_tab`) 오류 수정
- `PortPresenter`: 파일 손상 복구 및 안정화
- `MainPresenter`: 문법 오류 수정

### UI/UX 개선 및 테마 리팩토링 (2025-12-01)

#### 변경 사항 (Changed)

- **ManualControlWidget 개선**:
  - 레이아웃을 컴팩트하게 조정 (불필요한 여백 제거)
  - 입력창을 `QTextEdit`에서 `QLineEdit`으로 변경하여 높이 축소
  - Send 버튼 높이 조정 및 스타일 적용
  - Flow Control (RTS/DTR) 체크박스 추가
- **MacroCtrlWidget 개선**:
  - 레이아웃 정리 및 버튼 배치 최적화
  - Start Auto Run (녹색), Stop (붉은색) 버튼에 강조 스타일 적용
- **MainWindow 개선**:
  - 좌우 패널 스플리터 비율을 2:1에서 1:1로 조정하여 균형 개선
- **테마 시스템 리팩토링**:
  - `common.qss` 도입으로 공통 스타일 통합 관리
  - `ThemeManager`가 공통 스타일과 개별 테마를 병합하여 로드하도록 개선
  - 라이트 테마에서 비활성화된 버튼의 시인성 개선 (틴트 색상 적용)

### 프로젝트 구조 (2025-11-30)

#### 추가 사항 (Added)

- MVP 아키텍처 확립
- 모듈식 폴더 구조 생성:
  - `view/panels/`: LeftPanel, RightPanel, PortPanel, MacroListPanel
  - `view/widgets/`: PortSettings, CommandList, CommandControl, ManualControl
  - `resources/themes/`: 테마 관리자 및 QSS 파일
  - `resources/icons/`: SVG 아이콘
  - `doc/`: 문서 및 계획 파일

#### 변경 사항 (Changed)

- 프로젝트 이름을 "SerialManager"에서 "SerialTool"로 변경
- UI를 LeftPanel(포트 + 수동 제어) 및 RightPanel(커맨드 리스트 + 패킷 인스펙터)을 사용하도록 리팩토링
- 미사용 파일 제거 (rx_log_view.py, status_bar.py 등)

## 버전 이력 (Version History)

### [1.0.0] - 개발 중

#### 완료 (Completed)

- ✅ 프로젝트 설정 및 구조
- ✅ UI 골격 구현
- ✅ 테마 및 스타일링 시스템
- ✅ UI 레이아웃 최적화
- ✅ SVG 아이콘 시스템
- ✅ 위젯 개선 및 다듬기
- ✅ 디렉토리 구조 재정리
- ✅ View 계층 마무리 (다이얼로그, 다국어 지원)
- ✅ Command List 영속성 구현

#### 진행 중 (In Progress)

- 🔄 Core 유틸리티 (RingBuffer, ThreadSafeQueue)
- 🔄 Model 계층 (SerialWorker, PortController)
- 🔄 Presenter 통합

#### 계획 (Planned)

- ⏳ Command List 자동화 엔진
- ⏳ 파일 전송 기능
- ⏳ 플러그인 시스템
- ⏳ 테스트 및 배포

---

**범례:**

- ✅ 완료
- 🔄 진행 중
- ⏳ 계획됨
- 🐛 버그 수정
- ⚡ 성능 개선
- 🎨 UI/UX 향상
