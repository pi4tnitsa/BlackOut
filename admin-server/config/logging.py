import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

class LoggingConfig:
    """Централизованная конфигурация логирования"""
    
    @staticmethod
    def setup_app_logging(app=None, log_level='INFO'):
        """Настройка логирования для Flask приложения"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Форматирование
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
        )
        
        # Файловый обработчик
        file_handler = RotatingFileHandler(
            log_dir / 'nuclei_scanner.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Консольный обработчик
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Очищаем существующие обработчики
        root_logger.handlers.clear()
        
        # Добавляем новые
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Настройка Flask логгера
        if app:
            app.logger.handlers.clear()
            app.logger.addHandler(file_handler)
            app.logger.addHandler(console_handler)
            app.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Отключаем чрезмерно подробные логи библиотек
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('paramiko').setLevel(logging.WARNING)
        
        return root_logger
