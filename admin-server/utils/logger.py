# utils/logger.py - Система логирования
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(app=None):
    """Настройка системы логирования"""
    # Создаем директорию для логов
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка форматирования
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
    )
    
    # Настройка обработчика файлов с ротацией
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, 'nuclei_scanner.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Настройка консольного вывода
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    if app:
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)

def get_logger(name):
    """Получение логгера для модуля"""
    return logging.getLogger(name)