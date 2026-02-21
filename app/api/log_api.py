from datetime import datetime
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.Base.db import get_session
from app.Base.models import DeviceStatus, RemoteCommand

router = APIRouter()


class LogEntry(BaseModel):
    device_name: str
    battery: int
    cpu: float
    gpu: float
    uptime: str
    top_processes: List[str]


class CommandResult(BaseModel):
    status: str
    output: Optional[str] = None


@router.post("/")
def receive_log(log: LogEntry, session: Session = Depends(get_session)):
    log_record = DeviceStatus(
        device_name=log.device_name,
        battery=log.battery,
        cpu=log.cpu,
        gpu=log.gpu,
        uptime=log.uptime,
        top_processes=json.dumps(log.top_processes),
    )
    session.add(log_record)
    session.commit()
    return {"status": "saved"}


@router.get("/{device_name}/commands/next")
def get_next_command(device_name: str, session: Session = Depends(get_session)):
    stmt = (
        select(RemoteCommand)
        .where(
            RemoteCommand.device_name == device_name,
            RemoteCommand.status == "pending",
        )
        .order_by(RemoteCommand.created_at)
    )
    command = session.exec(stmt).first()
    if not command:
        return {"command": None}

    command.status = "in_progress"
    session.add(command)
    session.commit()
    return {"command": {"id": command.id, "name": command.command}}


@router.post("/commands/{command_id}/result")
def save_command_result(
    command_id: int,
    result: CommandResult,
    session: Session = Depends(get_session),
):
    command = session.get(RemoteCommand, command_id)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")

    command.status = result.status
    command.output = result.output
    command.executed_at = datetime.utcnow()
    session.add(command)
    session.commit()

    return {"status": "updated"}
