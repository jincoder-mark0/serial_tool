"""
공통 데이터 스키마 정의 모듈

JSON 파일 검증을 위한, jsonschema 정의를 포함
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
