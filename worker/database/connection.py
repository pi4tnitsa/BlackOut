# database/connection.py - Подключение к PostgreSQL
import psycopg2
import psycopg2.extras
from typing import Dict, Any, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseConnection:
    """Класс для работы с базой данных PostgreSQL"""
    
    def __init__(self, db_config: Dict[str, Any]):
        self.config = db_config
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Установка соединения с базой данных"""
        try:
            self.connection = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['name'],
                user=self.config['user'],
                password=self.config['password'],
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            
            # Проверяем подключение
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            
            logger.info(f"Подключение к базе данных {self.config['name']} установлено")
            
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            self.connection = None
            raise
    
    def test_connection(self) -> bool:
        """Тестирование подключения к базе данных"""
        try:
            if not self.connection:
                self._connect()
            
            with self.connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                return True
                
        except Exception as e:
            logger.error(f"Ошибка тестирования подключения: {e}")
            return False
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Выполнение SQL запроса"""
        try:
            # Проверяем соединение
            if not self.connection or self.connection.closed:
                self._connect()
            
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                
                # Если это SELECT запрос, возвращаем результаты
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                else:
                    # Для других запросов коммитим изменения
                    self.connection.commit()
                    return cursor.rowcount
                    
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"Ошибка выполнения запроса: {e}")
            raise
    
    def close(self):
        """Закрытие соединения"""
        if self.connection:
            self.connection.close()
            logger.info("Соединение с базой данных закрыто")