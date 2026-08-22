# S-010 — 가상 시리얼 포트 실환경 검증

- Status: TODO
- Recommended model: 상위 + **사용자 개입 필요** (com0com 설치는 관리자 권한 수동 작업)
- 선행: 없음
- Skills to load: task-done

## 목적 (Why)

현재 테스트는 pyserial 클래스를 patch한 Mock(`tests/conftest.py:71 mock_serial_port`)뿐이라
실제 OS 시리얼 스택(타이밍·버퍼·flow control·에러 경로)을 통과하지 않는다.
"실기기 미검증" 항목을 장비 없이 줄이는 기반이 가상 포트 페어다.

## 계획 (착수 시 상세화)

1. **사용자 작업**: com0com 설치(Windows, 서명 드라이버 버전) → 가상 페어(COM10↔COM11 등) 생성.
2. 페어 존재 시에만 도는 pytest 마커 `@pytest.mark.virtual_serial` 신설 —
   포트 부재 시 자동 skip (CI·타 PC에서 실패하지 않도록).
3. 실환경 시나리오: 열기/닫기 반복, 에코 왕복(한쪽 write→다른 쪽 read), 대량 전송
   중 포트 강제 종료(경합 조건 — README §1.1 "스레드 안전 종료 보장" 실증),
   파일 전송 Backpressure 실측.
4. 결과에 따라 "실기기 미검증" 딱지를 갱신.

## Acceptance criteria

- [ ] 가상 페어에서 실환경 테스트가 통과하고, 페어 부재 환경에서는 전부 skip.
- [ ] 검증된 항목 목록을 tests/README.md에 기록.
