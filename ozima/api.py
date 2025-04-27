from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
import os
import tarfile
import tempfile
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import settings  # Теперь будет работать с pydantic-settings

# Настройка логирования
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
        handlers=[rotating_handler, logging.StreamHandler()]
    )

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

# Проверка токена
def verify_token(authorization: str = Header(...)):
    if authorization != f"Bearer {settings.API_TOKEN}":
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
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"{process_time:.2f}ms"
    )
    return response

# Эндпоинты
@app.get("/directory_size/")
async def get_directory_size(path: str, authorization: str = Depends(verify_token)):
    try:
        total_size = sum(
            f.stat().st_size 
            for f in Path(path).rglob('*') 
            if f.is_file() and not f.is_symlink()
        )
        return {"path": path, "size_bytes": total_size}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download_directory/")
async def download_directory(path: str, authorization: str = Depends(verify_token)):
    try:
        if not os.path.isdir(path):
            raise HTTPException(status_code=404, detail="Directory not found")
        
        dir_name = os.path.basename(path.rstrip("/"))
        temp_path = f"{tempfile.gettempdir()}/{dir_name}.tar"

        with tarfile.open(temp_path, "w") as tar:
            tar.add(path, arcname=dir_name)

        def cleanup():
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return FileResponse(
            path=temp_path,
            filename=f"{dir_name}.tar",
            media_type="application/x-tar",
            background=BackgroundTask(cleanup)
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
