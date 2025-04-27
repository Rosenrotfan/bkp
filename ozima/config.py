import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Настройки авторизации
    API_TOKEN: str = "100500300"  # Замените на свой токен
    # Настройки логирования
    LOG_DIR: str = "logs"
    LOG_MAX_SIZE_MB: int = 5        # Макс. размер файла лога (в МБ)
    LOG_BACKUP_COUNT: int = 2       # Кол-во резервных копий (всего файлов: LOG_BACKUP_COUNT + 1)

    class Config:
        env_file = ".env"           # Можно переопределить настройки через .env файл
settings = Settings()
