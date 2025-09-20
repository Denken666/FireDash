from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class DeviceStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str
    battery: int
    cpu: float
    gpu: float
    uptime: str
    top_processes: str  # JSON-строка, можно хранить как текст
    timestamp: datetime = Field(default_factory=datetime.utcnow)
