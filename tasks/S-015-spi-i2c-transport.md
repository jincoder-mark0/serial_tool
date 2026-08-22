# S-015 — SPI/I2C Transport 확장

- Status: ⛔ 보류 (요구 미확정 — 대상 하드웨어/어댑터 칩·유스케이스 미정)
- Recommended model: **상위 전용**
- 선행: 요구 확정 (사용자)
- Skills to load: task-done

## 목적 (Why)

README §1.4: "SPI/I2C, 플러그인 시스템 … 향후 작업입니다." 통신 계층은 이미
`core/transport/base_transport.py:21 BaseTransport(ABC)`(open/close/is_open/read/write/
in_waiting + 선택 훅 set_broadcast/set_dtr/set_rts) 뒤로 추상화되어 있어 구조적 준비는 끝났다.

## 착수 전 확정 필요 (사용자에게 질의)

1. 대상 브리지 하드웨어 (FT4222? MCP2221? Aardvark? …) — 드라이버/파이썬 바인딩이 달라진다.
2. 유스케이스: 마스터 폴링만인지, 레지스터 맵 UI가 필요한지.
3. UI 통합 형태: 기존 포트 탭에 프로토콜 추가(현재 PortConfig 콤보에 'Serial' 고정)인지 별도 패널인지.

## 원칙

- 구현은 반드시 `BaseTransport` 구현체로만 (상위 계층 무수정이 목표).
- read/write 의미론이 스트림이 아니므로(트랜잭션 단위) 인터페이스 적합성 판단이 선행 —
  맞지 않으면 인터페이스 확장을 별도 결정.

## Acceptance criteria

- [ ] 요구 확정 기록 후 상세 태스크로 재작성.
