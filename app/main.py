#uvicorn app.main:app --reload
from fastapi import FastAPI
from app.api import log_api, site_api
from app.Base.db import create_db_and_tables
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="FireDash",
    description="Дашборд мониторинга устройств",
    version="1.0.0"
)

# Подключение index.html как сайт
app.mount("/static", StaticFiles(directory="app/frontend"), name="static")

@app.get("/dashboard", include_in_schema=False)
def dashboard():
    path = os.path.join("app", "frontend", "index.html")
    return FileResponse(path, media_type="text/html")

# Подключение роутов
app.include_router(log_api.router, prefix="/api/logs", tags=["Logs"])
app.include_router(site_api.router, prefix="/api/site", tags=["Site"])

@app.on_event("startup")
def on_startup():
    create_db_and_tables()  # Это создаёт таблицы!

# Корневая страница (можно вернуть frontend в будущем)
@app.get("/")
async def root():
    return {"message": "FireDash API запущен"}