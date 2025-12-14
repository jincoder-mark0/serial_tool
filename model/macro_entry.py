"""
매크로 엔트리 모듈

매크로 명령의 데이터 구조를 정의합니다.

## WHY
* 매크로 명령의 속성을 구조화
* 직렬화/역직렬화 지원 (설정 저장/로드)
* 타입 안전성 보장
* 불변 데이터 구조로 안정성 향상

## WHAT
* 매크로 명령 속성 정의
  - enabled: 활성화 여부
  - command: 전송할 명령어
  - is_hex: HEX 모드 여부
  - prefix/suffix: 접두사/접미사 사용 여부
  - delay_ms: 다음 명령까지 대기 시간
  - expect: 기대하는 응답 패턴
  - timeout_ms: 응답 대기 시간
* Dictionary 변환 메서드

## HOW
* dataclass로 간결한 정의
* to_dict/from_dict로 직렬화 지원
* 기본값 제공으로 편의성 향상
"""
from dataclasses import dataclass

@dataclass
class MacroEntry:
    """
    매크로 항목 데이터 클래스

    Attributes:
        enabled: 활성화 여부
        command: 전송할 명령어
        is_hex: HEX 모드 여부
        prefix: 접두사 사용 여부
        suffix: 접미사 사용 여부
        delay_ms: 다음 명령까지 대기 시간 (ms)
        expect: 기대하는 응답 패턴 (Expect 기능)
        timeout_ms: 응답 대기 시간 (ms)
    """
    enabled: bool = True
    command: str = ""
    is_hex: bool = False
    prefix: bool = False
    suffix: bool = False
    delay_ms: int = 0
    expect: str = ""
    timeout_ms: int = 5000

    def to_dict(self) -> dict:
        """
        Dictionary로 변환 (설정 저장용)

        Returns:
            dict: 모든 속성을 포함하는 Dictionary
        """
        return {
            "enabled": self.enabled,
            "command": self.command,
            "is_hex": self.is_hex,
            "prefix": self.prefix,
            "suffix": self.suffix,
            "delay_ms": self.delay_ms,
            "expect": self.expect,
            "timeout_ms": self.timeout_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MacroEntry':
        """
        Dictionary에서 MacroEntry 생성 (설정 로드용)

        Args:
            data: 매크로 데이터 Dictionary

        Returns:
            MacroEntry: 생성된 인스턴스
        """
        return cls(
            enabled=data.get("enabled", True),
            command=data.get("command", ""),
            is_hex=data.get("is_hex", False),
            prefix=data.get("prefix", False),
            suffix=data.get("suffix", False),
            delay_ms=data.get("delay_ms", 0),
            expect=data.get("expect", ""),
            timeout_ms=data.get("timeout_ms", 5000)
        )
