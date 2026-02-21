import json
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel
from sqlmodel import Session, delete, func, select

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


def command_status_label(status: str) -> str:
    mapping = {
        "pending": "🕒 В очереди",
        "in_progress": "⚙️ Выполняется",
        "waiting": "✅ Завершена",
    }
    return mapping.get(status, status)


@router.get("/devices")
def get_latest_devices(session: Session = Depends(get_session)):
    status_subquery = (
        select(
            DeviceStatus.device_name,
            func.max(DeviceStatus.timestamp).label("max_status_time"),
        )
        .group_by(DeviceStatus.device_name)
        .subquery()
    )

    command_subquery = (
        select(
            RemoteCommand.device_name,
            func.max(RemoteCommand.created_at).label("max_command_time"),
        )
        .group_by(RemoteCommand.device_name)
        .subquery()
    )

    status_stmt = (
        select(DeviceStatus)
        .join(
            status_subquery,
            (DeviceStatus.device_name == status_subquery.c.device_name)
            & (DeviceStatus.timestamp == status_subquery.c.max_status_time),
        )
        .order_by(DeviceStatus.device_name)
    )
    statuses = session.exec(status_stmt).all()

    latest_command_stmt = (
        select(RemoteCommand)
        .join(
            command_subquery,
            (RemoteCommand.device_name == command_subquery.c.device_name)
            & (RemoteCommand.created_at == command_subquery.c.max_command_time),
        )
    )
    commands = session.exec(latest_command_stmt).all()
    command_by_device = {c.device_name: c for c in commands}

    devices = []
    now = datetime.utcnow()
    for r in statuses:
        latest_command = command_by_device.get(r.device_name)
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
                "latest_command": {
                    "id": latest_command.id,
                    "name": latest_command.command,
                    "status": latest_command.status,
                    "status_label": command_status_label(latest_command.status),
                    "output": latest_command.output,
                    "created_at": latest_command.created_at.isoformat(),
                    "executed_at": latest_command.executed_at.isoformat()
                    if latest_command.executed_at
                    else None,
                }
                if latest_command
                else None,
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


@router.delete("/devices/{device_name}")
def delete_device(device_name: str, session: Session = Depends(get_session)):
    deleted_statuses = session.exec(
        delete(DeviceStatus).where(DeviceStatus.device_name == device_name)
    )
    deleted_commands = session.exec(
        delete(RemoteCommand).where(RemoteCommand.device_name == device_name)
    )
    session.commit()
    stream_frame_store.remove_frame(device_name)

    return {
        "status": "deleted",
        "device_name": device_name,
        "deleted_logs": deleted_statuses.rowcount or 0,
        "deleted_commands": deleted_commands.rowcount or 0,
    }


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
            "status_label": command_status_label(command.status),
            "output": command.output,
            "created_at": command.created_at.isoformat(),
            "executed_at": command.executed_at.isoformat() if command.executed_at else None,
        }
    }


@router.get("/devices/{device_name}/stream")
def get_device_stream(device_name: str):
    placeholder = build_placeholder_frame(device_name)

    def frame_generator():
        frame_delay = 1 / STREAM_FPS
        while True:
            frame = stream_frame_store.get_frame(device_name=device_name) or placeholder
            yield b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            time.sleep(frame_delay)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
