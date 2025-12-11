from dataclasses import dataclass

@dataclass
class MacroEntry:
    """매크로 항목 데이터 클래스"""
    enabled: bool = True
    command: str = ""
    is_hex: bool = False
    prefix: bool = False
    suffix: bool = False
    delay_ms: int = 0
    expect: str = ""
    timeout_ms: int = 5000

    def to_dict(self) -> dict:
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
