"""
코어 로직 정밀 테스트 모듈

애플리케이션의 기반이 되는 Core 유틸리티 및 매니저 클래스를 검증합니다.

## WHY
* 데이터 변환(CommandProcessor) 오류는 통신 전체의 신뢰성을 떨어뜨림
* 이벤트 버스(EventBus) 오류는 컴포넌트 간 통신 단절을 초래함
* 설정 관리(SettingsManager) 오류는 앱 초기화 실패의 원인이 됨

## WHAT
* CommandProcessor: ASCII/HEX 변환, 접두사/접미사 처리, 에러 핸들링
* EventBus: 구독/발행 메커니즘, 토픽 라우팅, 구독 취소
* SettingsManager: 싱글톤 패턴, 설정값 읽기/쓰기 무결성

## HOW
* 다양한 입력 케이스(정상/비정상)를 통한 CommandProcessor 검증
* Mock 콜백 함수를 이용한 EventBus 메시지 전달 확인
* pytest의 tmp_path와 patch를 활용한 설정 파일 I/O 격리 테스트

pytest tests/test_core_refinement.py -v
"""
import pytest
from unittest.mock import MagicMock, patch

from core.command_processor import CommandProcessor
from core.event_bus import EventBus
from core.settings_manager import SettingsManager
from common.constants import ConfigKeys


class TestCommandProcessor:
    """
    명령어 처리기(CommandProcessor)의 데이터 변환 로직을 검증합니다.
    """

    def test_process_ascii_command(self):
        """
        일반 ASCII 명령어 변환 테스트

        Logic:
            - 문자열 입력
            - HEX 모드 False
            - 바이트 변환 결과 확인 (UTF-8 인코딩)
        """
        # GIVEN: 일반 문자열
        cmd = "Hello World"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(cmd, hex_mode=False)

        # THEN: 바이트로 변환되어야 함
        assert result == b"Hello World"

    def test_process_hex_command_valid(self):
        """
        유효한 HEX 문자열 변환 테스트

        Logic:
            - 공백이 포함된 HEX 문자열 입력 ("AA BB")
            - HEX 모드 True
            - 바이너리 데이터 변환 확인
        """
        # GIVEN: HEX 문자열 (대소문자 혼용, 공백 포함)
        cmd = "AA bb 01"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(cmd, hex_mode=True)

        # THEN: 정확한 바이트 값이어야 함
        assert result == b'\xaa\xbb\x01'

    def test_process_hex_command_invalid(self):
        """
        유효하지 않은 HEX 문자열 처리 테스트

        Logic:
            - HEX가 아닌 문자('G') 포함
            - HEX 모드 True
            - ValueError 발생 확인
        """
        # GIVEN: 잘못된 HEX 문자열
        cmd = "ZZ Top"

        # WHEN & THEN: 변환 시도 시 예외 발생
        with pytest.raises(ValueError):
            CommandProcessor.process_command(cmd, hex_mode=True)

    def test_process_with_prefix_suffix(self):
        """
        접두사(Prefix) 및 접미사(Suffix) 결합 테스트

        Logic:
            - 명령어, 접두사, 접미사 입력
            - 모든 요소가 결합된 바이트 데이터 반환 확인
        """
        # GIVEN: 데이터 및 설정
        cmd = "DATA"
        prefix = "<STX>"
        suffix = "<ETX>"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(
            cmd,
            hex_mode=False,
            prefix=prefix,
            suffix=suffix
        )

        # THEN: 순서대로 결합되어야 함
        assert result == b"<STX>DATA<ETX>"

    def test_process_hex_with_prefix_suffix(self):
        """
        HEX 모드에서의 접두사/접미사 결합 테스트

        Logic:
            - 접두사/접미사는 항상 문자열로 처리됨을 가정 (또는 구현에 따라 다름)
            - CommandProcessor는 Prefix/Suffix를 ASCII로 처리한다고 가정
        """
        # GIVEN
        cmd = "FF 00"
        prefix = "A"
        suffix = "B"

        # WHEN
        result = CommandProcessor.process_command(
            cmd,
            hex_mode=True,
            prefix=prefix,
            suffix=suffix
        )

        # THEN: Prefix(A) + Hex(FF 00) + Suffix(B)
        # b'A' -> 0x41, b'B' -> 0x42
        expected = b'A\xff\x00B'
        assert result == expected


class TestEventBus:
    """
    이벤트 버스(EventBus)의 발행/구독 패턴을 검증합니다.
    """

    @pytest.fixture(autouse=True)
    def clean_event_bus(self):
        """테스트 전후로 EventBus 상태를 초기화합니다."""
        bus = EventBus()
        # 내부 저장소 초기화 (Singleton이므로 필수)
        if hasattr(bus, '_subscribers'):
            bus._subscribers.clear()
        yield bus
        if hasattr(bus, '_subscribers'):
            bus._subscribers.clear()

    def test_subscribe_and_publish(self):
        """
        이벤트 구독 및 발행 성공 테스트

        Logic:
            - 특정 토픽 구독
            - 해당 토픽으로 메시지 발행
            - 콜백 함수 호출 여부 및 전달 데이터 검증
        """
        # GIVEN
        bus = EventBus()
        topic = "test_topic"
        data = {"key": "value"}

        mock_callback = MagicMock()

        # WHEN: 구독 및 발행
        bus.subscribe(topic, mock_callback)
        bus.publish(topic, data)

        # THEN: 콜백 호출 확인
        mock_callback.assert_called_once_with(data)

    def test_publish_no_subscribers(self):
        """
        구독자가 없는 토픽 발행 테스트

        Logic:
            - 구독자 없이 발행
            - 에러 없이 정상 실행되어야 함 (Silent Ignore)
        """
        # GIVEN
        bus = EventBus()
        topic = "ghost_topic"

        # WHEN & THEN: 에러 발생하지 않아야 함
        try:
            bus.publish(topic, "some_data")
        except Exception as e:
            pytest.fail(f"Publishing to no subscribers raised exception: {e}")

    def test_unsubscribe(self):
        """
        구독 취소 기능 테스트

        Logic:
            - 구독 후 발행 (호출 확인)
            - 구독 취소 후 발행 (호출 안 됨 확인)
        """
        # GIVEN
        bus = EventBus()
        topic = "status_update"
        mock_callback = MagicMock()

        bus.subscribe(topic, mock_callback)

        # WHEN: 1차 발행
        bus.publish(topic, "msg1")
        assert mock_callback.call_count == 1

        # WHEN: 구독 취소 및 2차 발행
        bus.unsubscribe(topic, mock_callback)
        bus.publish(topic, "msg2")

        # THEN: 카운트가 증가하지 않아야 함
        assert mock_callback.call_count == 1

    def test_multiple_subscribers(self):
        """
        다중 구독자 처리 테스트

        Logic:
            - 하나의 토픽에 두 개의 콜백 등록
            - 메시지 발행 시 둘 다 호출되어야 함
        """
        # GIVEN
        bus = EventBus()
        topic = "broadcast"

        sub1 = MagicMock()
        sub2 = MagicMock()

        bus.subscribe(topic, sub1)
        bus.subscribe(topic, sub2)

        # WHEN
        bus.publish(topic, "payload")

        # THEN
        sub1.assert_called_once()
        sub2.assert_called_once()


class TestSettingsManager:
    """
    설정 관리자(SettingsManager)의 저장소 로직을 검증합니다.
    """

    def test_singleton_behavior(self):
        """
        싱글톤 패턴 동작 검증

        Logic:
            - 두 번 인스턴스 생성
            - 두 객체의 아이디(메모리 주소)가 동일한지 확인
        """
        # 싱글톤 인스턴스 초기화 (테스트 격리)
        SettingsManager._instance = None

        m1 = SettingsManager()
        m2 = SettingsManager()

        assert m1 is m2

        # 정리
        SettingsManager._instance = None

    def test_get_set_value(self):
        """
        설정값 읽기 및 쓰기 테스트 (메모리 상)

        Logic:
            - 설정값 set
            - get으로 읽었을 때 일치 확인
            - 존재하지 않는 키 get 시 기본값 반환 확인
        """
        SettingsManager._instance = None
        manager = SettingsManager()

        # Mocking load/save to avoid file I/O
        with patch.object(manager, 'load_settings'), \
             patch.object(manager, 'save_settings'):

            # WHEN: 값 설정
            manager.set(ConfigKeys.PORT_BAUDRATE, 9600)

            # THEN: 값 읽기
            assert manager.get(ConfigKeys.PORT_BAUDRATE) == 9600

            # THEN: 기본값 테스트
            assert manager.get("NON_EXISTENT_KEY", "DEFAULT") == "DEFAULT"

    def test_save_triggers_file_io(self, tmp_path):
        """
        저장 시 파일 쓰기 동작 검증 (Mocking 없이 tmp_path 사용)

        Logic:
            - tmp_path를 설정 파일 경로로 패치
            - save_settings() 호출
            - 파일이 생성되고 내용이 JSON으로 기록되었는지 확인
        """
        # GIVEN: 임시 파일 경로
        test_file = tmp_path / "config.json"

        SettingsManager._instance = None

        # CONFIG_FILE_PATH 패치
        with patch("core.settings_manager.CONFIG_FILE_PATH", str(test_file)):
            manager = SettingsManager()

            # WHEN: 설정 변경 및 저장 (자동 저장 여부에 따라 save 호출)
            manager.set("test_key", 12345)
            manager.save_settings()

            # THEN: 파일 생성 확인
            assert test_file.exists()

            # THEN: 내용 검증
            import json
            with open(test_file, 'r') as f:
                data = json.load(f)
                assert data["test_key"] == 12345