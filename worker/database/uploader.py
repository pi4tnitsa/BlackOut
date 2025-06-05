# database/uploader.py - ИСПРАВЛЕННАЯ версия с импортом List
from typing import Dict, Any, Optional, List
from datetime import datetime
from .connection import DatabaseConnection
from utils.logger import get_logger

logger = get_logger(__name__)

class ResultUploader:
    """Класс для загрузки результатов сканирования в базу данных"""
    
    def __init__(self, db_connection: DatabaseConnection, source_host_id: int):
        self.db_connection = db_connection
        self.source_host_id = source_host_id
    
    def upload_vulnerability(self, vulnerability: Dict[str, Any]) -> bool:
        """Загрузка уязвимости в базу данных"""
        try:
            query = """
            INSERT INTO vulnerabilities 
            (ip_address, template_method, connection_method, severity_level, url, additional_info, source_host_id, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """
            
            # Подготавливаем данные
            timestamp = vulnerability.get('timestamp')
            if timestamp is None:
                timestamp = datetime.utcnow()
            elif isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp = datetime.utcnow()
            
            params = (
                vulnerability['ip_address'],
                vulnerability['template_method'],
                vulnerability['connection_method'],
                vulnerability['severity_level'],
                vulnerability['url'],
                vulnerability['additional_info'],
                self.source_host_id,
                timestamp
            )
            
            result = self.db_connection.execute_query(query, params)
            
            if result:
                vuln_id = result[0]['id'] if isinstance(result, list) else None
                logger.debug(f"Уязвимость загружена с ID: {vuln_id}")
                return True
            else:
                logger.warning("Не удалось получить ID загруженной уязвимости")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка загрузки уязвимости: {e}")
            logger.debug(f"Данные уязвимости: {vulnerability}")
            return False
    
    def upload_batch_vulnerabilities(self, vulnerabilities: List[Dict[str, Any]]) -> int:
        """Пакетная загрузка уязвимостей"""
        uploaded_count = 0
        
        for vulnerability in vulnerabilities:
            if self.upload_vulnerability(vulnerability):
                uploaded_count += 1
        
        logger.info(f"Загружено {uploaded_count} из {len(vulnerabilities)} уязвимостей")
        return uploaded_count