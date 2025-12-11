"""
Core Refinement 테스트
ExpectMatcher 및 ParserType 상수 테스트
"""
import sys
import unittest
sys.path.insert(0, 'c:\\Users\\lkj01\\Desktop\\Serial_Tool')

from model.packet_parser import ExpectMatcher, ParserType, ParserFactory

class TestExpectMatcher(unittest.TestCase):
    """ExpectMatcher 클래스 테스트"""
    
    def test_basic_match(self):
        """기본 문자열 매칭 테스트"""
        matcher = ExpectMatcher("OK")
        
        # 매칭되지 않는 경우
        result = matcher.match(b"HEL")
        self.assertFalse(result)
        
        # 매칭되는 경우
        result = matcher.match(b"LO OK\r\n")
        self.assertTrue(result)
        
    def test_regex_match(self):
        """정규식 매칭 테스트"""
        matcher = ExpectMatcher(r"OK|ERROR", is_regex=True)
        
        # OK 매칭
        result = matcher.match(b"Response: OK\r\n")
        self.assertTrue(result)
        
    def test_buffer_limit(self):
        """버퍼 크기 제한 테스트"""
        matcher = ExpectMatcher("NEVER", max_buffer_size=100)
        
        # 버퍼 크기를 초과하는 데이터 추가
        for _ in range(20):
            matcher.match(b"A" * 10)
        
        # 버퍼가 max_buffer_size를 초과하지 않아야 함
        self.assertLessEqual(len(matcher._buffer), 100)
        
    def test_reset(self):
        """리셋 테스트"""
        matcher = ExpectMatcher("OK")
        matcher.match(b"some data")
        matcher.reset()
        
        self.assertEqual(len(matcher._buffer), 0)


class TestParserType(unittest.TestCase):
    """ParserType 상수 테스트"""
    
    def test_parser_type_values(self):
        """ParserType 상수값 확인"""
        self.assertEqual(ParserType.RAW, "Raw")
        self.assertEqual(ParserType.AT, "AT")
        self.assertEqual(ParserType.DELIMITER, "Delimiter")
        self.assertEqual(ParserType.FIXED_LENGTH, "FixedLength")
        
    def test_parser_factory_creation(self):
        """ParserFactory로 파서 생성 테스트"""
        # RAW 파서
        raw_parser = ParserFactory.create_parser(ParserType.RAW)
        self.assertIsNotNone(raw_parser)
        
        # AT 파서
        at_parser = ParserFactory.create_parser(ParserType.AT)
        self.assertIsNotNone(at_parser)
        
        # Delimiter 파서
        delim_parser = ParserFactory.create_parser(ParserType.DELIMITER, delimiter=b'\n')
        self.assertIsNotNone(delim_parser)
        
        # Fixed Length 파서
        fixed_parser = ParserFactory.create_parser(ParserType.FIXED_LENGTH, length=10)
        self.assertIsNotNone(fixed_parser)


if __name__ == '__main__':
    unittest.main()
