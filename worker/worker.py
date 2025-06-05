# worker.py - Основной скрипт воркера
import os
import sys
import time
import yaml
import signal
import threading
from datetime import datetime
from pathlib import Path

# Добавляем текущую директорию в Python path
sys.path.append(str(Path(__file__).parent))

from nuclei_runner.scanner import NucleiScanner
from database.connection import DatabaseConnection
from database.uploader import ResultUploader
from utils.logger import setup_logger, get_logger

class NucleiWorker:
    """Основной класс воркера Nuclei"""
    
    def __init__(self, config_path='config.yaml'):
        # Загрузка конфигурации
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Настройка логирования
        setup_logger(self.config['logging'])
        self.logger = get_logger(__name__)
        
        # Инициализация компонентов
        self.db_connection = DatabaseConnection(self.config['database'])
        self.scanner = NucleiScanner(self.config['nuclei'])
        self.uploader = ResultUploader(self.db_connection, self.config['worker']['server_id'])
        
        # Флаги управления
        self._running = False
        self._shutdown = False
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"Воркер {self.config['worker']['hostname']} инициализирован")
    
    def start(self):
        """Запуск воркера"""
        self.logger.info("Запуск воркера Nuclei")
        self._running = True
        
        try:
            # Проверяем подключение к базе данных
            if not self.db_connection.test_connection():
                self.logger.error("Не удалось подключиться к базе данных")
                return False
            
            # Проверяем доступность Nuclei
            if not self.scanner.check_nuclei_availability():
                self.logger.error("Nuclei недоступен")
                return False
            
            # Обновляем статус сервера в БД
            self._update_server_status('online')
            
            # Основной цикл работы
            self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Критическая ошибка воркера: {e}")
            return False
        finally:
            self._cleanup()
        
        return True
    
    def stop(self):
        """Остановка воркера"""
        self.logger.info("Получен сигнал остановки воркера")
        self._shutdown = True
    
    def _main_loop(self):
        """Основной цикл обработки задач"""
        check_interval = self.config['worker']['check_interval']
        
        while self._running and not self._shutdown:
            try:
                # Получаем задачи для выполнения
                tasks = self._get_pending_tasks()
                
                if tasks:
                    self.logger.info(f"Найдено {len(tasks)} задач для выполнения")
                    
                    # Выполняем задачи
                    for task in tasks:
                        if self._shutdown:
                            break
                        self._execute_task(task)
                else:
                    self.logger.debug("Новых задач не найдено")
                
                # Обновляем статус сервера
                self._update_server_status('online')
                
                # Ожидаем до следующей проверки
                for _ in range(check_interval):
                    if self._shutdown:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(60)  # Ждем минуту при ошибке
    
    def _get_pending_tasks(self):
        """Получение задач, ожидающих выполнения"""
        try:
            query = """
            SELECT id, name, target_ips, status, created_at
            FROM scan_tasks 
            WHERE status = 'pending' 
            AND %s = ANY(server_ids)
            ORDER BY created_at ASC
            LIMIT %s
            """
            
            server_id = self.config['worker']['server_id']
            max_tasks = self.config['worker']['max_concurrent_scans']
            
            return self.db_connection.execute_query(query, (server_id, max_tasks))
            
        except Exception as e:
            self.logger.error(f"Ошибка получения задач: {e}")
            return []
    
    def _execute_task(self, task):
        """Выполнение задачи сканирования"""
        task_id = task['id']
        task_name = task['name']
        target_ips = task['target_ips']
        
        self.logger.info(f"Начало выполнения задачи: {task_name} (ID: {task_id})")
        
        try:
            # Обновляем статус задачи
            self._update_task_status(task_id, 'running')
            
            # Выполняем сканирование
            scan_results = self.scanner.scan_targets(target_ips)
            
            # Загружаем результаты в базу данных
            uploaded_count = 0
            for result in scan_results:
                if self.uploader.upload_vulnerability(result):
                    uploaded_count += 1
            
            # Обновляем статус задачи на завершенную
            self._update_task_status(task_id, 'completed')
            
            self.logger.info(f"Задача {task_name} завершена. Загружено уязвимостей: {uploaded_count}")
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения задачи {task_name}: {e}")
            self._update_task_status(task_id, 'failed')
    
    def _update_task_status(self, task_id, status):
        """Обновление статуса задачи"""
        try:
            query = """
            UPDATE scan_tasks 
            SET status = %s,
                started_at = CASE WHEN %s = 'running' THEN %s ELSE started_at END,
                completed_at = CASE WHEN %s IN ('completed', 'failed') THEN %s ELSE NULL END
            WHERE id = %s
            """
            now = datetime.utcnow()
            self.db_connection.execute_query(query, (status, status, now, status, now, task_id))
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса задачи {task_id}: {e}")
    
    def _update_server_status(self, status):
        """Обновление статуса сервера"""
        try:
            query = """
            UPDATE servers 
            SET status = %s, last_seen = %s 
            WHERE id = %s
            """
            server_id = self.config['worker']['server_id']
            self.db_connection.execute_query(query, (status, datetime.utcnow(), server_id))
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса сервера: {e}")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов остановки"""
        self.logger.info(f"Получен сигнал {signum}")
        self.stop()
    
    def _cleanup(self):
        """Очистка ресурсов при завершении"""
        self.logger.info("Очистка ресурсов воркера")
        
        try:
            # Обновляем статус сервера на offline
            self._update_server_status('offline')
            
            # Закрываем соединение с БД
            self.db_connection.close()
            
        except Exception as e:
            self.logger.error(f"Ошибка при очистке ресурсов: {e}")
        
        self._running = False
        self.logger.info("Воркер завершен")

def main():
    """Точка входа"""
    worker = NucleiWorker()
    success = worker.start()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

