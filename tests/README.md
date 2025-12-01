# View 컴포넌트 테스트

이 디렉토리는 View 계층의 각 컴포넌트를 독립적으로 테스트할 수 있는 테스트 애플리케이션을 포함합니다.

## 파일

### test_view.py
View 컴포넌트 테스트 애플리케이션

**실행 방법:**
```bash
cd tests
python test_view.py
```

**테스트 가능한 컴포넌트:**

1. **ReceivedArea Test**
   - 색상 규칙 테스트 (OK, ERROR, URC 등)
   - Trim 로직 테스트 (2000줄 제한)
   - 타임스탬프 옵션
   - HEX 모드
   - Pause 기능

2. **ManualControl Test**
   - Send 버튼
   - HEX 모드 전환
   - Enter 추가 옵션
   - 파일 선택/전송
   - 활성화/비활성화 테스트

3. **CommandList Test**
   - 행 추가/삭제/이동
   - Select All 기능
   - Send 버튼 테스트

4. **StatusArea Test**
   - INFO, ERROR, WARN, SUCCESS 로그
   - 색상별 표시
   - 타임스탬프

5. **PortPanel Test**
   - 전체 패널 통합 테스트
   - 포트 설정 + ReceivedArea + StatusArea

## 주요 기능

- ✅ MainWindow 없이 개별 위젯 테스트 가능
- ✅ 탭 기반으로 각 컴포넌트 분리
- ✅ 테스트 버튼으로 데이터 주입
- ✅ SettingsManager 통합 테스트
- ✅ 종료 시 창 크기 저장

## 장점

1. **안전성**: MainWindow 손상 없이 테스트 가능
2. **독립성**: 각 위젯을 독립적으로 테스트
3. **신속성**: 특정 기능만 빠르게 테스트
4. **디버깅**: 문제 발생 시 원인 파악 용이
