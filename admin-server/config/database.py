import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseManager:
    """Менеджер подключений к базам данных"""
    
    def __init__(self):
        self.config = Config.DB_CONFIG
        self.connections = {}
    
    def get_connection(self, database_name):
        """Получение подключения к указанной базе данных"""
        if database_name not in self.connections or self.connections[database_name].closed:
            try:
                conn = psycopg2.connect(
                    host=self.config['host'],
                    port=self.config['port'],
                    database=self.config['databases'][database_name],
                    user=self.config['user'],
                    password=self.config['password'],
                    cursor_factory=RealDictCursor
                )
                self.connections[database_name] = conn
                logger.info(f"Подключение к базе {database_name} установлено")
            except Exception as e:
                logger.error(f"Ошибка подключения к базе {database_name}: {e}")
                raise
        
        return self.connections[database_name]
    
    def execute_query(self, database_name, query, params=None):
        """Выполнение SQL запроса"""
        conn = self.get_connection(database_name)
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка выполнения запроса: {e}")
            raise
    
    def close_all_connections(self):
        """Закрытие всех подключений"""
        for name, conn in self.connections.items():
            if conn and not conn.closed:
                conn.close()
                logger.info(f"Подключение к базе {name} закрыто")
        self.connections.clear()

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

def init_db(app):
    """Инициализация базы данных"""
    with app.app_context():
        # Создание таблиц в каждой базе данных
        create_tables_query = """
        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id SERIAL PRIMARY KEY,
            ip_address INET NOT NULL,
            template_method TEXT,
            connection_method TEXT,
            severity_level TEXT,
            url TEXT,
            additional_info TEXT,
            source_host_id INTEGER,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS servers (
            id SERIAL PRIMARY KEY,
            hostname VARCHAR(255) NOT NULL,
            ip_address INET NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            status VARCHAR(50) DEFAULT 'offline',
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS scan_tasks (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            target_ips TEXT[],
            server_ids INTEGER[],
            status VARCHAR(50) DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_vulnerabilities_ip ON vulnerabilities(ip_address);
        CREATE INDEX IF NOT EXISTS idx_vulnerabilities_severity ON vulnerabilities(severity_level);
        CREATE INDEX IF NOT EXISTS idx_vulnerabilities_timestamp ON vulnerabilities(timestamp);
        """
        
        for db_name in Config.DB_CONFIG['databases'].keys():
            try:
                db_manager.execute_query(db_name, create_tables_query)
                logger.info(f"Таблицы в базе {db_name} созданы успешно")
            except Exception as e:
                logger.error(f"Ошибка создания таблиц в базе {db_name}: {e}")
                # Не прерываем работу приложения, если одна БД недоступна
                continue
