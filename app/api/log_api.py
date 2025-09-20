from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from typing import List
from sqlmodel import Session
from app.Base.db import get_session
from app.Base.models import DeviceStatus
import json

router = APIRouter()

class LogEntry(BaseModel):
    device_name: str
    battery: int
    cpu: float
    gpu: float
    uptime: str
    top_processes: List[str]

@router.post("/")
def receive_log(log: LogEntry, session: Session = Depends(get_session)):
    log_record = DeviceStatus(
        device_name=log.device_name,
        battery=log.battery,
        cpu=log.cpu,
        gpu=log.gpu,
        uptime=log.uptime,
        top_processes=json.dumps(log.top_processes)
    )
    session.add(log_record)
    session.commit()
    return {"status": "saved"}
