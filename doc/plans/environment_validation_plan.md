# Environment / Deployment Validation Plan

> 우선순위: P4
> 기준 브랜치: `main`
> 목표: P2/P3 완료 후 최종 packaged artifact와 virtual/physical Serial 환경을 제품 관점에서 종합 검증

---

## 1. 역할

이 문서는 개발 선행 baseline이 아니라 **최종 환경/배포 검증 gate**다.

개별 작업 중 실기기 확인이 필요한 경우 해당 작업 acceptance에서 최소 smoke를 수행한다.
예:

- Serial I/O 최적화 → 실제 USB Serial 최소 smoke
- SPI/I2C Transport → 실제 지원 adapter/backend 검증

P4는 이들을 대체하지 않고, 모든 변경이 합쳐진 최신 `main`을 제품 관점에서 다시 검증한다.

---

## 2. 실행 순서

### 2.1 PyInstaller artifact smoke

최신 `main`으로 새 artifact를 생성한다.

```powershell
pyinstaller serial_tool.spec --noconfirm
```

확인:

- startup / shutdown
- resource / icon / language / theme load
- settings read/write
- LOOPBACK
- Manual TX/RX
- Macro 기본 실행
- Packet Inspector
- File Transfer 기본 경로
- logging / file dialog path

목적은 packaging/runtime dependency 누락과 bundled-path 문제 검출이다.

### 2.2 Windows com0com E2E

Windows serial stack을 통과하는 가상 포트 pair로 반복 가능한 E2E를 수행한다.

확인:

- connect / reconnect
- sustained RX/TX
- close 중 RX
- queued TX flush
- file transfer
- macro Expect
- packet parsing/filter/annotation 관련 적용 기능
- trigger 기능이 구현된 경우 loop safety
- shutdown

### 2.3 실제 USB Serial 종합 검증

지원 대상 hardware를 최소 1종 선정한다.

확인:

- cable/device disconnect
- reconnect
- baudrate 변경
- RTS/DTR
- 장시간 RX/TX
- Macro / File Transfer
- logging
- application shutdown

기록:

- adapter/device
- driver/version
- baudrate
- duration / data volume
- observed limitation

### 2.4 Linux socat

Linux가 실제 지원/배포 대상인 경우 수행한다.
그렇지 않으면 compatibility task로 유지하고 release blocker로 사용하지 않는다.

---

## 3. 기록 형식

```text
OS / version
artifact or Python environment
Serial backend / driver
port pair or physical device
scenario
Duration / data volume
Result
Known limitation
```

성능 수치는 benchmark 문서가 정본이며, 이 문서에서는 정상 동작/회귀 여부를 우선한다.

---

## 4. Acceptance Criteria

P4 완료 조건:

- 최신 main PyInstaller artifact smoke 성공
- Windows com0com E2E 성공
- 실제 USB Serial 최소 1종 종합 검증 성공
- blocker 수준 data loss / crash / shutdown hang 없음
- 발견 문제를 code defect / environment limitation으로 분류
- 실행 환경과 결과 문서화

Linux socat는 Linux 지원 여부에 따라 별도 판정한다.

---

## 5. 실패 시 처리

P4에서 defect가 발견되면 해당 기능 owner로 되돌아가 수정하고 다시 관련 targeted test → full CI → P4 영향 범위를 재검증한다.

P4 자체에서 architecture를 즉흥적으로 수정하지 않는다.
