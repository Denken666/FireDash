from fastapi import APIRouter, Request

from app.Base.stream_store import stream_frame_store

router = APIRouter()


@router.post('/{device_name}/frame')
async def upload_frame(device_name: str, request: Request):
    body = await request.body()
    if body:
        stream_frame_store.set_frame(device_name=device_name, frame=body)
    return {'status': 'ok'}
