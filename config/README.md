# 설정 파일 (Configuration Files)

이 디렉토리는 애플리케이션의 설정 파일들을 포함합니다.

## 파일 목록

### 1. color_rules.json
ReceivedArea에서 수신된 텍스트에 자동으로 색상을 적용하는 규칙을 정의합니다.

### 2. default_settings.json
애플리케이션의 기본 설정 값을 정의합니다. (포트 설정, UI 설정 등)

---

## color_rules.json

이 파일은 ReceivedArea에서 수신된 텍스트에 자동으로 색상을 적용하는 규칙을 정의합니다.

## 파일 위치
`config/color_rules.json`

## 형식

```json
{
  "color_rules": [
    {
      "name": "규칙 이름",
      "pattern": "정규식 또는 문자열 패턴",
      "color": "#RRGGBB",
      "is_regex": true/false,
      "enabled": true/false
    }
  ]
}
```

## 기본 제공 규칙

| 이름 | 패턴 | 색상 | 설명 |
|------|------|------|------|
| AT_OK | `\bOK\b` | #4CAF50 (녹색) | AT 명령 성공 응답 |
| AT_ERROR | `\bERROR\b` | #F44336 (빨강) | AT 명령 에러 응답 |
| URC | `(\+\w+:)` | #FFEB3B (노랑) | +로 시작하는 URC 메시지 |
| PROMPT | `^>` | #00BCD4 (청록) | 프롬프트 기호 |
| INFO | `\bINFO\b` | #2196F3 (파랑) | 정보 메시지 |
| WARNING | `\b(WARN|WARNING)\b` | #FF9800 (주황) | 경고 메시지 |

## 사용자 정의 규칙 추가

이 파일을 직접 수정하여 새로운 규칙을 추가할 수 있습니다.

### 예시: TIMEOUT 패턴 추가

```json
{
  "name": "TIMEOUT",
  "pattern": "\\bTIMEOUT\\b",
  "color": "#9C27B0",
  "is_regex": true,
  "enabled": true
}
```

### 참고사항

- `pattern`: 정규식을 사용할 경우 백슬래시를 이중으로 입력 (`\\b` 등)
- `color`: HTML 색상 코드 형식 (#RRGGBB)
- `is_regex`: false인 경우 단순 문자열 매칭
- `enabled`: false로 설정하면 규칙이 비활성화됨

## 자동 로드

애플리케이션 시작 시 이 파일이 자동으로 로드됩니다.
파일이 없으면 기본 규칙으로 자동 생성됩니다.
