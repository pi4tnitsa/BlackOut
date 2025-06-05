# utils/logger.py для воркера
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

def setup_logger(logging_config: Dict[str, Any]):
    """Настройка логирования для воркера"""
    level = getattr(logging, logging_config['level'].upper(), logging.INFO)
    log_file = logging_config['file']
    max_size = logging_config['max_size_mb'] * 1024 * 1024  # Конвертируем в байты
    backup_count = logging_config['backup_count']
    
    # Создаем директорию для логов
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Форматтер
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
    )
    
    # Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_size,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Очищаем предыдущие обработчики
    root_logger.handlers.clear()
    
    # Добавляем новые обработчики
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def get_logger(name: str):
    """Получение логгера для модуля"""
    return logging.getLogger(name)
