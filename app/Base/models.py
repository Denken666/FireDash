from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class DeviceStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str
    battery: int
    cpu: float
    gpu: float
    uptime: str
    top_processes: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RemoteCommand(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str = Field(index=True)
    command: str
    status: str = Field(default="pending", index=True)
    output: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
