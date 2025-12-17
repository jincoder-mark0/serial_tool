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
# 필수 필드만 엄격하게 검사하고, 나머지는 허용(additionalProperties: True)
CORE_SETTINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "global": {
            "type": "object",
            "properties": {
                "theme": {"type": "string"},
                "language": {"type": "string"}
            },
            "required": ["theme", "language"]
        },
        "ui": {
            "type": "object",
            "properties": {
                "rx_max_lines": {"type": "integer"},
                "proportional_font_family": {"type": "string"},
                "proportional_font_size": {"type": "integer"},
                "fixed_font_family": {"type": "string"},
                "fixed_font_size": {"type": "integer"}
            }
        },
        "ports": {
            "type": "object",
            "properties": {
                "default_config": {
                    "type": "object",
                    "properties": {
                        "baudrate": {"type": "integer"},
                        "parity": {"type": "string"},
                        "bytesize": {"type": "integer"},
                        "stopbits": {"type": "number"}
                    }
                }
            }
        }
    },
    "required": ["version", "global"]
}