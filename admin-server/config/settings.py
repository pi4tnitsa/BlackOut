import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения
env_file = Path('.env')
if env_file.exists():
    load_dotenv(env_file)

class Config:
    """Конфигурация приложения с валидацией"""
    
    # Flask настройки
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-me')
    
    # Настройки базы данных
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'user': os.getenv('DB_ADMIN_USER', 'admin'),
        'password': os.getenv('DB_ADMIN_PASSWORD', 'password'),
        'databases': {
            'russia': os.getenv('DB_RUSSIA', 'russia'),
            'belarus': os.getenv('DB_BELARUS', 'belarus'),
            'kazakhstan': os.getenv('DB_KAZAKHSTAN', 'kazakhstan')
        }
    }
    
    # Настройки авторизации
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
    
    # Настройки Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Настройки Redis/Celery
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Настройки Nuclei
    NUCLEI_TEMPLATES_PATH = os.getenv('NUCLEI_TEMPLATES_PATH', '/opt/nuclei-templates')
    CUSTOM_TEMPLATES_PATH = os.getenv('CUSTOM_TEMPLATES_PATH', '/opt/custom-templates')
    
    # SSH настройки
    SSH_USERNAME = os.getenv('SSH_USERNAME', 'root')
    SSH_KEY_PATH = os.getenv('SSH_KEY_PATH')
    SSH_PASSWORD = os.getenv('SSH_PASSWORD')
    
    @classmethod
    def validate_config(cls):
        """Валидация конфигурации"""
        errors = []
        
        # Проверяем обязательные настройки
        if cls.SECRET_KEY == 'dev-secret-key-change-me':
            errors.append("FLASK_SECRET_KEY должен быть изменен в продакшене")
        
        if not cls.DB_CONFIG['password'] or cls.DB_CONFIG['password'] == 'password':
            errors.append("DB_ADMIN_PASSWORD должен быть установлен")
        
        if cls.ADMIN_PASSWORD == 'admin':
            errors.append("ADMIN_PASSWORD должен быть изменен")
        
        # Проверяем пути
        templates_path = Path(cls.NUCLEI_TEMPLATES_PATH)
        if not templates_path.exists():
            errors.append(f"Директория шаблонов не существует: {cls.NUCLEI_TEMPLATES_PATH}")
        
        custom_path = Path(cls.CUSTOM_TEMPLATES_PATH)
        if not custom_path.exists():
            errors.append(f"Директория кастомных шаблонов не существует: {cls.CUSTOM_TEMPLATES_PATH}")
        
        # Проверяем SSH настройки
        if cls.SSH_KEY_PATH:
            key_path = Path(cls.SSH_KEY_PATH)
            if not key_path.exists():
                errors.append(f"SSH ключ не найден: {cls.SSH_KEY_PATH}")
        
        return errors
