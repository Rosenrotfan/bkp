from fastapi import FastAPI, HTTPException, Depends, Header, Request
import os
import shutil
from typing import Optional
import logging
from logging.handlers import RotatingFileHandler
import time

# Импортируем настройки из config.py
from config import settings  # Убедитесь, что config.py в той же директории

# --- Настройка логирования ---
def setup_logging():
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    
    rotating_handler = RotatingFileHandler(
        filename=f"{settings.LOG_DIR}/api.log",
        maxBytes=settings.LOG_MAX_SIZE_MB * 1024 * 1024,
        backupCount=settings.LOG_BACKUP_COUNT,
    )
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            rotating_handler,
            logging.StreamHandler()
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

# Проверка токена (используем settings.API_TOKEN)
def verify_token(authorization: str = Header(...)):
    if authorization != f"Bearer {settings.API_TOKEN}":  # Исправлено здесь
        logger.warning(f"Invalid token attempt: {authorization}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(
        f"Request: {request.method} {request.url} - "
        f"Status: {response.status_code} - "
        f"Process time: {process_time:.2f}ms"
    )
    return response

# Эндпоинт для получения размера директории
@app.get("/directory_size/")
async def get_directory_size(
    path: str,
    authorization: str = Depends(verify_token)
):
    try:
        logger.info(f"Запрос размера директории: {path}")
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        logger.info(f"Успешно: размер {path} = {total_size} байт")
        return {"directory_path": path, "size_bytes": total_size}
    except Exception as e:
        logger.error(f"Ошибка при запросе размера директории: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# Эндпоинт для копирования файла
@app.post("/copy_file/")
async def copy_file(
    source: str,
    destination: str,
    overwrite: Optional[bool] = False,
    authorization: str = Depends(verify_token)
):
    try:
        logger.info(f"Запрос копирования: {source} -> {destination} (overwrite={overwrite})")
        if not os.path.exists(source):
            logger.error(f"Файл не найден: {source}")
            raise HTTPException(status_code=404, detail="Source file not found")
        if os.path.exists(destination) and not overwrite:
            logger.warning(f"Файл уже существует: {destination}")
            raise HTTPException(
                status_code=400,
                detail="Destination file already exists. Use 'overwrite=true' to replace it."
            )
        shutil.copy2(source, destination)
        logger.info(f"Успешно скопировано: {source} -> {destination}")
        return {
            "status": "success",
            "source": source,
            "destination": destination,
            "overwrite": overwrite
        }
    except Exception as e:
        logger.error(f"Ошибка при копировании: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
