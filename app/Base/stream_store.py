import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class StreamFrame:
    frame: bytes
    timestamp: datetime


class StreamFrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._frames: Dict[str, StreamFrame] = {}

    def set_frame(self, device_name: str, frame: bytes):
        with self._lock:
            self._frames[device_name] = StreamFrame(frame=frame, timestamp=datetime.utcnow())

    def get_frame(self, device_name: str, max_age_seconds: int = 5) -> Optional[bytes]:
        with self._lock:
            item = self._frames.get(device_name)
            if not item:
                return None
            if datetime.utcnow() - item.timestamp > timedelta(seconds=max_age_seconds):
                return None
            return item.frame

    def remove_frame(self, device_name: str):
        with self._lock:
            self._frames.pop(device_name, None)


stream_frame_store = StreamFrameStore()
