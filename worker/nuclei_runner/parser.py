# worker/nuclei_runner/parser.py - РЕАЛИЗАЦИЯ ОТСУТСТВУЮЩЕГО ФАЙЛА
"""
Парсер результатов Nuclei сканирования
"""

import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

class NucleiResultParser:
    """Парсер результатов сканирования Nuclei"""
    
    def __init__(self):
        self.ip_pattern = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')
    
    def parse_json_output(self, nuclei_output: str, source_host_id: int) -> List[Dict[str, Any]]:
        """
        Парсинг JSON вывода Nuclei в список уязвимостей
        
        Args:
            nuclei_output: Строка с выводом Nuclei в JSON формате
            source_host_id: ID источника сканирования
            
        Returns:
            Список словарей с информацией об уязвимостях
        """
        vulnerabilities = []
        
        if not nuclei_output.strip():
            logger.warning("Пустой вывод Nuclei")
            return vulnerabilities
        
        for line_num, line in enumerate(nuclei_output.strip().split('\n'), 1):
            if not line.strip():
                continue
            
            try:
                vulnerability = self._parse_json_line(line, source_host_id)
                if vulnerability:
                    vulnerabilities.append(vulnerability)
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга JSON на строке {line_num}: {e}")
                logger.debug(f"Проблемная строка: {line}")
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке строки {line_num}: {e}")
                continue
        
        logger.info(f"Распарсено {len(vulnerabilities)} уязвимостей из {line_num} строк")
        return vulnerabilities
    
    def _parse_json_line(self, json_line: str, source_host_id: int) -> Optional[Dict[str, Any]]:
        """
        Парсинг одной JSON строки от Nuclei
        
        Args:
            json_line: JSON строка с результатом
            source_host_id: ID источника сканирования
            
        Returns:
            Словарь с данными уязвимости или None
        """
        try:
            data = json.loads(json_line)
            
            # Извлекаем основные поля
            host = data.get('host', '')
            template_id = data.get('template-id', '')
            matcher_name = data.get('matcher-name', '')
            
            # Получаем информацию о шаблоне
            info = data.get('info', {})
            severity = info.get('severity', 'info')
            description = info.get('description', '')
            tags = info.get('tags', [])
            references = info.get('reference', [])
            classification = info.get('classification', {})
            
            # Извлекаем IP-адрес
            ip_address = self._extract_ip_from_host(host)
            
            # Формируем URL
            url = data.get('matched-at', host)
            
            # Собираем дополнительную информацию
            additional_info = {
                'matcher_name': matcher_name,
                'description': description,
                'tags': tags,
                'reference': references,
                'classification': classification,
                'curl_command': data.get('curl-command', ''),
                'extracted_results': data.get('extracted-results', []),
                'request': data.get('request', ''),
                'response': data.get('response', '')
            }
            
            # Создаем объект уязвимости
            vulnerability = {
                'ip_address': ip_address,
                'template_method': template_id,
                'connection_method': data.get('type', ''),
                'severity_level': severity,
                'url': url,
                'additional_info': json.dumps(additional_info, ensure_ascii=False),
                'source_host_id': source_host_id,
                'timestamp': self._parse_timestamp(data.get('timestamp'))
            }
            
            return vulnerability
            
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return None
    
    def _extract_ip_from_host(self, host: str) -> str:
        """
        Извлечение IP-адреса из поля host
        
        Args:
            host: URL или IP-адрес
            
        Returns:
            IP-адрес в виде строки
        """
        if not host:
            return 'unknown'
        
        # Удаляем протокол
        clean_host = re.sub(r'^https?://', '', host)
        
        # Удаляем порт и путь
        clean_host = clean_host.split(':')[0].split('/')[0]
        
        # Проверяем, является ли это IP-адресом
        if self.ip_pattern.match(clean_host):
            return clean_host
        
        # Если это доменное имя, пытаемся разрешить его в IP
        try:
            import socket
            ip = socket.gethostbyname(clean_host)
            return ip
        except Exception as e:
            logger.debug(f"Не удалось разрешить домен {clean_host}: {e}")
            # Возвращаем как есть, если не удалось разрешить
            return clean_host
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> datetime:
        """
        Парсинг временной метки из Nuclei
        
        Args:
            timestamp_str: Строка с временной меткой
            
        Returns:
            Объект datetime
        """
        if not timestamp_str:
            return datetime.utcnow()
        
        # Пытаемся распарсить различные форматы времени
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO формат с микросекундами
            '%Y-%m-%dT%H:%M:%SZ',     # ISO формат без микросекунд
            '%Y-%m-%d %H:%M:%S',      # Простой формат
            '%Y-%m-%dT%H:%M:%S.%f',   # ISO без Z
            '%Y-%m-%dT%H:%M:%S'       # ISO без Z и микросекунд
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Не удалось распарсить временную метку: {timestamp_str}")
        return datetime.utcnow()
