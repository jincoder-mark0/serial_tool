"""
설정 스키마 정의 모듈

설정 파일(settings.json)의 무결성을 검증하기 위한 JSON Schema를 정의합니다.

## WHY
* 설정 파일 검증 로직은 'Core' 계층의 역할입니다.
* 설정 관리자(SettingsManager)와 밀접한 관련이 있습니다.
* 테마/언어 허용값을 스키마에 문자열로 다시 나열하면 common enum과 조용히
  어긋날 수 있으므로 공통 타입 정의에서 허용값을 생성합니다.

## WHAT
* CORE_SETTINGS_SCHEMA: 필수 설정 필드 및 타입 정의

## HOW
* jsonschema 표준 형식을 준수하는 딕셔너리 정의
* 유한 상태값은 common.enums를 단일 정본으로 사용
"""
from common.enums import LanguageType, ThemeType


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
                "theme": {
                    "type": "string",
                    "enum": [theme.value for theme in ThemeType],
                },
                "language": {
                    "type": "string",
                    "enum": [language.value for language in LanguageType],
                },
            },
            "required": ["theme", "language"],
        },
        "ui": {"type": "object"},
        "command": {"type": "object"},
        "logging": {"type": "object"},
        "packet": {"type": "object"},
        "ports": {"type": "object"},
        "manual_control": {"type": "object"},
        "macro_list": {"type": "object"},
    },
    "required": ["version", "settings"],
}
