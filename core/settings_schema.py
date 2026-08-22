"""
설정 스키마 정의 모듈

설정 파일(settings.json)의 무결성을 검증하기 위한 JSON Schema를 정의합니다.

## WHY
* 설정 파일 검증 로직은 'Core' 계층의 역할입니다.
* 설정 관리자(SettingsManager)와 밀접한 관련이 있습니다.

## WHAT
* CORE_SETTINGS_SCHEMA: 필수 설정 필드 및 타입 정의

## HOW
* jsonschema 표준 형식을 준수하는 딕셔너리 정의
"""

# 핵심 설정 스키마 정의
# 정본 네임스페이스는 settings.*(S-027, S-016 확정) — 실사용 키(theme/language)만
# 엄격 검증하고, 나머지 블록은 존재 여부(type: object)만 느슨하게 확인한다(과잉 고정 금지).
CORE_SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "settings": {
            "type": "object",
            "properties": {
                "theme": {"type": "string", "enum": ["dark", "light", "dracula"]},
                "language": {"type": "string", "enum": ["en", "ko"]}
            },
            "required": ["theme", "language"]
        },
        "ui": {"type": "object"},
        "serial": {"type": "object"},
        "command": {"type": "object"},
        "logging": {"type": "object"},
        "packet": {"type": "object"},
        "ports": {"type": "object"},
        "manual_control": {"type": "object"},
        "macro_list": {"type": "object"}
    },
    "required": ["version", "settings"]
}