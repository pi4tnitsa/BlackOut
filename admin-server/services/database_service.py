# services/database_service.py - Сервис работы с базой данных
from typing import List, Optional, Dict, Any
from datetime import datetime
from config.database import db_manager
from models.vulnerability import Vulnerability
from models.server import Server
from models.task import ScanTask
from utils.logger import get_logger

logger = get_logger(__name__)

class DatabaseService:
    """Сервис для работы с базой данных"""
    
    def __init__(self, database_name: str = 'belarus'):
        self.database_name = database_name
    
    # Методы для работы с уязвимостями
    def save_vulnerability(self, vulnerability: Vulnerability) -> int:
        """Сохранение уязвимости в базу данных"""
        query = """
        INSERT INTO vulnerabilities 
        (ip_address, template_method, connection_method, severity_level, url, additional_info, source_host_id, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        params = (
            vulnerability.ip_address,
            vulnerability.template_method,
            vulnerability.connection_method,
            vulnerability.severity_level,
            vulnerability.url,
            vulnerability.additional_info,
            vulnerability.source_host_id,
            vulnerability.timestamp or datetime.utcnow()
        )
        
        try:
            result = db_manager.execute_query(self.database_name, query, params)
            logger.info(f"Уязвимость сохранена: {vulnerability.ip_address}")
            return result[0]['id'] if result else None
        except Exception as e:
            logger.error(f"Ошибка сохранения уязвимости: {e}")
            raise
    
    def get_vulnerabilities(self, 
                          ip_filter: Optional[str] = None,
                          severity_filter: Optional[str] = None,
                          limit: int = 100,
                          offset: int = 0) -> List[Vulnerability]:
        """Получение списка уязвимостей с фильтрацией"""
        query = "SELECT * FROM vulnerabilities WHERE 1=1"
        params = []
        
        if ip_filter:
            query += " AND ip_address::text LIKE %s"
            params.append(f"%{ip_filter}%")
        
        if severity_filter:
            query += " AND severity_level = %s"
            params.append(severity_filter)
        
        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        try:
            results = db_manager.execute_query(self.database_name, query, params)
            return [Vulnerability.from_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Ошибка получения уязвимостей: {e}")
            return []
    
    def get_vulnerability_stats(self) -> Dict[str, Any]:
        """Получение статистики по уязвимостям"""
        stats_query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN severity_level = 'critical' THEN 1 END) as critical,
            COUNT(CASE WHEN severity_level = 'high' THEN 1 END) as high,
            COUNT(CASE WHEN severity_level = 'medium' THEN 1 END) as medium,
            COUNT(CASE WHEN severity_level = 'low' THEN 1 END) as low,
            COUNT(CASE WHEN severity_level = 'info' THEN 1 END) as info,
            COUNT(DISTINCT ip_address) as unique_ips,
            DATE(MAX(timestamp)) as last_scan
        FROM vulnerabilities;
        """
        
        try:
            result = db_manager.execute_query(self.database_name, stats_query)
            return dict(result[0]) if result else {}
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
    
    # Методы для работы с серверами
    def save_server(self, server: Server) -> int:
        """Сохранение сервера"""
        query = """
        INSERT INTO servers (hostname, ip_address, ssh_port, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """
        params = (
            server.hostname,
            server.ip_address,
            server.ssh_port,
            server.status,
            datetime.utcnow()
        )
        
        try:
            result = db_manager.execute_query(self.database_name, query, params)
            logger.info(f"Сервер сохранен: {server.hostname}")
            return result[0]['id'] if result else None
        except Exception as e:
            logger.error(f"Ошибка сохранения сервера: {e}")
            raise
    
    def get_servers(self) -> List[Server]:
        """Получение списка серверов"""
        query = "SELECT * FROM servers ORDER BY hostname"
        
        try:
            results = db_manager.execute_query(self.database_name, query)
            return [Server.from_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Ошибка получения серверов: {e}")
            return []
    
    def update_server_status(self, server_id: int, status: str) -> bool:
        """Обновление статуса сервера"""
        query = """
        UPDATE servers 
        SET status = %s, last_seen = %s 
        WHERE id = %s
        """
        params = (status, datetime.utcnow(), server_id)
        
        try:
            db_manager.execute_query(self.database_name, query, params)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса сервера: {e}")
            return False
    
    # Методы для работы с задачами
    def save_task(self, task: ScanTask) -> int:
        """Сохранение задачи сканирования"""
        query = """
        INSERT INTO scan_tasks (name, target_ips, server_ids, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """
        params = (
            task.name,
            task.target_ips,
            task.server_ids,
            task.status,
            datetime.utcnow()
        )
        
        try:
            result = db_manager.execute_query(self.database_name, query, params)
            logger.info(f"Задача сохранена: {task.name}")
            return result[0]['id'] if result else None
        except Exception as e:
            logger.error(f"Ошибка сохранения задачи: {e}")
            raise
    
    def get_tasks(self, status_filter: Optional[str] = None) -> List[ScanTask]:
        """Получение списка задач"""
        query = "SELECT * FROM scan_tasks"
        params = []
        
        if status_filter:
            query += " WHERE status = %s"
            params.append(status_filter)
        
        query += " ORDER BY created_at DESC"
        
        try:
            results = db_manager.execute_query(self.database_name, query, params)
            return [ScanTask.from_dict(row) for row in results]
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            return []
    
    def update_task_status(self, task_id: int, status: str) -> bool:
        """Обновление статуса задачи"""
        query = """
        UPDATE scan_tasks 
        SET status = %s, 
            started_at = CASE WHEN %s = 'running' THEN %s ELSE started_at END,
            completed_at = CASE WHEN %s IN ('completed', 'failed') THEN %s ELSE NULL END
        WHERE id = %s
        """
        now = datetime.utcnow()
        params = (status, status, now, status, now, task_id)
        
        try:
            db_manager.execute_query(self.database_name, query, params)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса задачи: {e}")
            return False