"""
View 서비스 패키지

UI와 관련된 로직 처리, 계산, 데이터 변환 등을 담당하는 서비스 클래스들을 포함합니다.
Service 계층은 상태를 저장하지 않고(Stateless), 입력에 대한 출력을 반환하는 로직 중심의 모듈입니다.
"""
from .color_service import ColorService

__all__ = [
    'ColorService',
]