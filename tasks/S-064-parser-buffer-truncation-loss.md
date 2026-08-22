# S-064 — 파서 버퍼 잘라내기로 완결 패킷 유실

- Status: TODO
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

- [ ] 배치 임계값 이상을 한 번에 받아도 완결 패킷이 유실되지 않는다(수정 전 실패를 확인한 테스트).
- [ ] 미완결 조각을 버릴 때 경고가 남는다.
- [ ] 메모리 보호(무한 증가 방지)가 유지됨을 테스트로 고정한다.
- [ ] 전체 pytest·ruff 통과.
