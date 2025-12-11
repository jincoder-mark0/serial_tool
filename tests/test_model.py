import unittest
from model.packet_parser import ExpectMatcher, ParserType, ParserFactory, ATParser

class TestCoreRefinement(unittest.TestCase):
    def test_expect_matcher_buffer_limit(self):
        # 10바이트 제한
        matcher = ExpectMatcher("target", max_buffer_size=10)
        
        # 5바이트 추가
        matcher.match(b"12345")
        self.assertEqual(matcher._buffer, b"12345")
        
        # 6바이트 추가 (총 11바이트 -> 10바이트로 잘려야 함)
        matcher.match(b"678901")
        # 예상: "2345678901" (앞의 '1'이 잘림)
        self.assertEqual(len(matcher._buffer), 10)
        self.assertEqual(matcher._buffer, b"2345678901")

    def test_parser_type_constants(self):
        self.assertEqual(ParserType.AT, "AT")
        self.assertEqual(ParserType.RAW, "Raw")
        
        parser = ParserFactory.create_parser(ParserType.AT)
        self.assertIsInstance(parser, ATParser)

if __name__ == '__main__':
    unittest.main()
