# S-064 — 파서 버퍼 잘라내기로 완결 패킷 유실

- Status: DONE (2026-08-22 — 하위 Sonnet, 회귀 테스트로 수정 전 실패 확인 후 3파서 순서 교정, pytest 393 passed·ruff 0건)
- Recommended model: **하위(Sonnet) 가능**
- 선행: 없음 (S-061 측정 중 발견)
- Skills to load: task-done
- 근거: S-061 범위 밖 발견 + 상위 코드 확인 (2026-08-22)

## 목적 (Why) — 고속 수신에서 조용히 데이터가 사라진다

`model/packet_parser.py`의 `DelimiterParser.parse()`가 **구분자로 패킷을 분리하기
전에** 버퍼를 잘라낸다:

```python
def parse(self, buffer: bytes) -> List[Packet]:
    self._buffer += buffer
    if len(self._buffer) > self._max_buffer_size:      # ← 먼저 자르고
        self._buffer = self._buffer[-self._max_buffer_size:]
    packets = []
    while self._delimiter in self._buffer:              # ← 그 다음 분리
        chunk, self._buffer = self._buffer.split(self._delimiter, 1)
        packets.append(...)
```

이 보호 로직의 의도는 "구분자가 전혀 오지 않는 폭주 스트림이 메모리를 먹는 것"을
막는 것이다. 그런데 순서 때문에 **이미 완결된(구분자까지 갖춘) 패킷들도 함께
잘려나간다.**

### 상위 확인 결과 (전제는 코드로 검증됨)

- `DelimiterParser`/`ATParser`/`FixedLengthParser` 모두 `max_buffer_size` 기본값 **4096**
  (`model/packet_parser.py:87, 129, 168`).
- `ConnectionWorker`의 배치 임계값 `BATCH_SIZE_THRESHOLD`는 **8192**
  (`common/constants.py:168`, 사용처 `model/connection_worker.py:107`).
- 즉 워커가 한 번에 8192바이트를 넘겨주면 파서는 **받자마자 앞의 4096바이트를 버린다.**
  구분자가 정상적으로 오고 있어도 유실된다. S-061 수행자가 고속 재현으로 확인했다.

## 확정 설계

**자르기와 분리의 순서를 뒤집는다.** 완결된 패킷을 먼저 전부 분리해 내보내고,
**그러고도 남은 미완결 조각에만** 상한을 적용한다. 그러면 상한이 버리는 것은
"구분자가 없어 영영 패킷이 될 수 없는 부분"뿐이라 원래 의도와 정확히 일치한다.

1. `DelimiterParser`, `ATParser`, `FixedLengthParser` **세 파서 모두** 같은 순서 문제를
   갖는지 확인하고, 갖는 것만 고친다(`FixedLengthParser`는 성격이 다를 수 있으니
   **코드를 보고 판단**하라 — 다르면 그 근거를 보고).
2. 미완결 조각이 상한을 넘어 실제로 버려질 때는 **조용히 버리지 마라.** 기존 로깅
   관례(`core/logger.py`)에 맞춰 경고를 남긴다 — S-039/S-045/S-059가 세운 "유실은
   보고한다" 원칙과 같은 계열이다.
3. `max_buffer_size` 기본값 자체도 검토하라. 배치 임계값(8192)보다 작으면 한 번의
   정상 emit이 곧바로 상한에 걸린다. 상수를 `common/constants.py`로 옮겨 관계를
   명시할지(예: 배치 임계값의 배수) **판단하고 근거를 보고**하라 — 매직 넘버 단일
   관리 규칙(CLAUDE.md)에 해당한다.

## 검증 방법

- **회귀 테스트가 이 태스크의 핵심이다**: 8192바이트(배치 임계값) 이상을 한 번에
  넘겼을 때 **완결 패킷이 하나도 유실되지 않음**을 고정하라. 고치기 전 코드에서
  그 테스트가 **실제로 실패하는 것을 먼저 확인**하고 보고에 적어라 — S-036에서
  "통과하는 무의미한 테스트"를 만든 전례가 있다.
- 구분자 없는 폭주 스트림에서 메모리가 무한히 늘지 않는다는 기존 보호도 함께 고정한다.
- 전체 pytest(offscreen, 기준선은 직전 커밋 값) + **ruff 0건**.

## Acceptance criteria (DoD)

- [x] 배치 임계값 이상을 한 번에 받아도 완결 패킷이 유실되지 않는다(수정 전 실패를 확인한 테스트).
- [x] 미완결 조각을 버릴 때 경고가 남는다.
- [x] 메모리 보호(무한 증가 방지)가 유지됨을 테스트로 고정한다.
- [x] 전체 pytest·ruff 통과.

## 수행 결과 (2026-08-22, 하위 Sonnet)

- **전제 재확인**: `model/packet_parser.py`의 세 생성자 라인(87/129/168)·
  `common/constants.py:168`의 `BATCH_SIZE_THRESHOLD=8192`·
  `model/connection_worker.py:107` 사용처 모두 태스크 기술과 일치함을 코드로 확인.
- **수정 전 실패 확인**: `tests/test_model_packet_parsers.py`에 회귀 테스트를 먼저 작성한 뒤,
  `model/packet_parser.py`만 수정 전(git HEAD) 버전으로 되돌려 실행 →
  `DelimiterParser`: `assert 8 == 2000`(1992개 유실), `ATParser`: `assert 6 == 1500`
  (1494개 유실), `FixedLengthParser`: `assert 8 == 1200`(1192개 유실) — 세 파서 모두
  실패를 직접 확인한 뒤 수정 파일을 복원했다.
- **세 파서 모두 수정**: `ATParser`/`DelimiterParser`/`FixedLengthParser` 전부 "완결 패킷
  분리 → 남은 미완결 조각에만 상한 적용" 순서로 교정. `FixedLengthParser`도 "길이 도달"이
  DelimiterParser의 구분자와 동일한 역할(완결 기준)을 하므로 같은 순서 버그를 갖고 있어
  동일하게 고쳤다(별도 처리 불필요 — 코드로 확인, 성격이 다르지 않았음).
- **미완결 조각 폐기 시 경고**: 세 파서 모두 `core.logger.logger.warning(...)`으로
  버려지는 바이트 수를 로그에 남김 (`core/data_logger.py`의 기존 관례와 동일 계열).
- **`max_buffer_size` 기본값 판단**: `common/constants.py`에 `PARSER_MAX_BUFFER_SIZE =
  BATCH_SIZE_THRESHOLD * 2`(16384) 신설, 세 파서 기본값을 매직 넘버 4096 대신 이 상수로
  교체. 순서 수정 자체로 "정상 배치가 즉시 상한에 걸리는" 원래 문제는 해소되지만,
  구분자가 오지 않는 미완결 조각이 한 배치 분량만큼 더 누적돼도 곧바로 잘리지 않도록
  여유를 둔 것 — `BATCH_SIZE_THRESHOLD`와의 관계를 배수로 명시해 매직 넘버 단일 관리
  원칙을 충족.
- **검증**: `pytest tests/test_model_packet_parsers.py -q` 23 passed →
  전체 `pytest -q` 393 passed → `ruff check .` All checks passed. Mock 기반(실기기 미검증
  항목 없음 — 순수 파서 단위 로직).
