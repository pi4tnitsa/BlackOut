# config/settings.py - Конфигурация приложения
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация приложения"""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    
    # Настройки базы данных
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
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