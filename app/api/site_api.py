import json
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.Base.db import get_session
from app.Base.models import DeviceStatus, RemoteCommand
from app.Base.stream_store import stream_frame_store

router = APIRouter()

ALLOWED_COMMANDS = {"lock_screen", "reboot", "shutdown", "sleep"}
STREAM_FPS = 15


class CreateCommandRequest(BaseModel):
    command: str


def build_placeholder_frame(device_name: str) -> bytes:
    image = Image.new("RGB", (960, 540), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    draw.text((30, 30), f"{device_name}: нет видеопотока", fill=(255, 255, 255))
    draw.text((30, 70), "Клиент еще не отправил кадры", fill=(200, 200, 200))
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


@router.get("/devices")
def get_latest_devices(session: Session = Depends(get_session)):
    subquery = (
        select(
            DeviceStatus.device_name,
            func.max(DeviceStatus.timestamp).label("max_time"),
        )
        .group_by(DeviceStatus.device_name)
        .subquery()
    )

    stmt = (
        select(DeviceStatus)
        .join(
            subquery,
            (DeviceStatus.device_name == subquery.c.device_name)
            & (DeviceStatus.timestamp == subquery.c.max_time),
        )
        .order_by(DeviceStatus.device_name)
    )

    results = session.exec(stmt).all()

    devices = []
    now = datetime.utcnow()
    for r in results:
        devices.append(
            {
                "id": r.id,
                "device_name": r.device_name,
                "battery": r.battery,
                "cpu": r.cpu,
                "gpu": r.gpu,
                "uptime": r.uptime,
                "top_processes": json.loads(r.top_processes),
                "timestamp": r.timestamp.isoformat(),
                "is_online": (now - r.timestamp) <= timedelta(seconds=90),
            }
        )

    return devices


@router.post("/devices/{device_name}/commands")
def create_remote_command(
    device_name: str,
    payload: CreateCommandRequest,
    session: Session = Depends(get_session),
):
    command_name = payload.command.strip().lower()
    if command_name not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=400, detail="Unsupported command")

    command = RemoteCommand(device_name=device_name, command=command_name)
    session.add(command)
    session.commit()
    session.refresh(command)

    return {"id": command.id, "status": command.status, "command": command.command}


@router.get("/devices/{device_name}/commands/latest")
def get_latest_command(device_name: str, session: Session = Depends(get_session)):
    stmt = (
        select(RemoteCommand)
        .where(RemoteCommand.device_name == device_name)
        .order_by(RemoteCommand.created_at.desc())
    )
    command: Optional[RemoteCommand] = session.exec(stmt).first()
    if not command:
        return {"command": None}

    return {
        "command": {
            "id": command.id,
            "name": command.command,
            "status": command.status,
            "output": command.output,
            "created_at": command.created_at.isoformat(),
            "executed_at": command.executed_at.isoformat() if command.executed_at else None,
        }
    }


@router.get('/devices/{device_name}/stream')
def get_device_stream(device_name: str):
    placeholder = build_placeholder_frame(device_name)

    def frame_generator():
        frame_delay = 1 / STREAM_FPS
        while True:
            frame = stream_frame_store.get_frame(device_name=device_name) or placeholder
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(frame_delay)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
