from enum import Enum
class PortState(Enum):
    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    ERROR = 'error'