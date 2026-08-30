# Environment / Deployment Validation Plan

> 우선순위: P1
> 기준 브랜치: `main`
> 목표: 구조/성능 변경 전에 실제 배포·통신 환경의 baseline 확보

---

## 1. WHY

현재 자동 검증은 Mock Serial, LoopbackTransport, offscreen Qt와 GitHub-hosted runner를 중심으로 한다.
성능 최적화나 추가 구조 변경 전에 실제 실행 환경에서 기준선을 확보하지 않으면 이후 회귀가 코드 변경 때문인지 환경 차이 때문인지 구분하기 어렵다.

따라서 post-merge 첫 단계는 **현재 main을 그대로 검증하는 것**이다.

---

## 2. 실행 순서

### 2.1 PyInstaller artifact smoke

현재 `main`으로 새 artifact를 생성한다.

```powershell
pyinstaller serial_tool.spec --noconfirm
```

확인:

- application startup / shutdown
- resource / icon / language / theme load
- settings read/write
- LOOPBACK 연결
- Manual TX/RX
- Macro 기본 실행
- Packet Inspector 표시
- File dialog / logging path

목적은 기능 전체 E2E가 아니라 packaging/runtime dependency 누락 검출이다.

### 2.2 Windows com0com

실제 Windows serial stack을 통과하는 가상 포트 pair로 검증한다.

확인:

- connect / reconnect
- sustained RX/TX
- close 중 RX
- queued TX flush
- file transfer
- macro Expect
- shutdown

### 2.3 실제 USB Serial 장치

지원 대상 hardware를 최소 1종 선정한다.

확인:

- cable/device disconnect
- reconnect
- baudrate 변경
- RTS/DTR
- 장시간 RX/TX
- file transfer
- application shutdown

실기기 결과는 사용한 adapter/device/driver를 기록한다.

### 2.4 Linux socat

Linux가 실제 지원/배포 대상인 경우 수행한다.
그렇지 않으면 필수 blocker가 아니라 별도 compatibility task로 유지한다.

---

## 3. 기록할 Baseline

각 환경에서 다음을 기록한다.

```text
OS / version
Python 또는 packaged artifact
Serial backend / driver
Port pair 또는 device
Scenario
Duration / data volume
Result
Known limitation
```

성능 수치는 P2 benchmark 문서로 넘기고, 이 문서에서는 정상 동작/회귀 여부를 우선한다.

---

## 4. Acceptance Criteria

P1 완료 조건:

- 현재 main PyInstaller artifact smoke 성공
- Windows serial stack 기반 가상 포트 E2E 성공
- 실제 USB Serial 최소 1종 smoke 성공
- 발견된 문제를 코드 defect / environment limitation으로 분류
- 실행 환경과 결과 문서화

Linux socat는 Linux 지원 필요성에 따라 별도 판정한다.

---

## 5. 다음 단계 연결

P1 결과가 Green이면 작은 구조 cleanup과 성능 benchmark로 이동한다.

```text
Environment baseline
    -> low-risk architecture cleanup
    -> performance baseline / optimization
```

실환경에서 blocking/crash/data-loss 문제가 발견되면 P2 최적화보다 해당 defect 수정이 우선이다.