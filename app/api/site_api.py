from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from typing import List
from datetime import datetime, timedelta
from app.Base.db import get_session
from app.Base.models import DeviceStatus
import json

router = APIRouter()

@router.get("/devices")
def get_latest_devices(session: Session = Depends(get_session)):
    # Получаем последние логи по каждому устройству
    subquery = select(
        DeviceStatus.device_name,
        func.max(DeviceStatus.timestamp).label("max_time")
    ).group_by(DeviceStatus.device_name).subquery()

    stmt = select(DeviceStatus).join(
        subquery,
        (DeviceStatus.device_name == subquery.c.device_name) &
        (DeviceStatus.timestamp == subquery.c.max_time)
    ).order_by(DeviceStatus.device_name)

    results = session.exec(stmt).all()

    devices = []
    now = datetime.utcnow()
    for r in results:
        devices.append({
            "id": r.id,
            "device_name": r.device_name,
            "battery": r.battery,
            "cpu": r.cpu,
            "gpu": r.gpu,
            "uptime": r.uptime,
            "top_processes": json.loads(r.top_processes),
            "timestamp": r.timestamp.isoformat(),
            "is_online": (now - r.timestamp) <= timedelta(seconds=90)
        })

    return devices
