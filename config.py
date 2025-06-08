from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Основные настройки
    app_name: str = "Nuclei Controller"
    version: str = "1.0.0"
    
    # База данных
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./nuclei_controller.db")
    
    # Безопасность
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 часа
    
    # Админ по умолчанию
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # Сервер
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    
    # Пути
    upload_dir: str = "uploads"
    templates_dir: str = os.path.join(upload_dir, "templates")
    targets_dir: str = os.path.join(upload_dir, "targets")
    worker_scripts_dir: str = "worker_scripts"
    
    # Настройки воркеров
    worker_timeout: int = 300  # Таймаут SSH подключения в секундах
    max_workers: int = 50  # Максимальное количество воркеров
    
    # Nuclei настройки
    nuclei_rate_limit: int = 150  # Лимит запросов в секунду
    nuclei_concurrency: int = 50  # Количество параллельных процессов
    
    class Config:
        env_file = ".env"

settings = Settings()

# Создание необходимых директорий
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.templates_dir, exist_ok=True)
os.makedirs(settings.targets_dir, exist_ok=True)
os.makedirs(settings.worker_scripts_dir, exist_ok=True)