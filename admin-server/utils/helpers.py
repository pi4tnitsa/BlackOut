# utils/helpers.py - Вспомогательные функции - ИСПРАВЛЕННАЯ версия
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Форматирование даты и времени"""
    if dt is None:
        return "Неизвестно"
    return dt.strftime(format_str)

def format_uptime(seconds: int) -> str:
    """Форматирование времени работы"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин {seconds % 60} сек"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days} дн {hours} ч"

def format_bytes(bytes_value: int) -> str:
    """Форматирование размера в байтах"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def generate_task_id() -> str:
    """Генерация уникального ID задачи"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:8]
    return f"scan_{timestamp}_{hash_suffix}"

def parse_nuclei_template_info(template_path: str) -> Dict[str, Any]:
    """Парсинг информации из шаблона Nuclei"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем метаданные из YAML заголовка
        if content.startswith('id:'):
            lines = content.split('\n')
            info = {}
            
            for line in lines:
                if line.startswith('id:'):
                    info['id'] = line.split(':', 1)[1].strip()
                elif line.startswith('  name:'):
                    info['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('  severity:'):
                    info['severity'] = line.split(':', 1)[1].strip()
                elif line.startswith('  description:'):
                    info['description'] = line.split(':', 1)[1].strip()
            
            return info
    except Exception:
        pass
    
    return {'id': 'unknown', 'name': 'Unknown Template', 'severity': 'info'}

def calculate_scan_eta(total_ips: int, rate_limit: int, num_servers: int) -> timedelta:
    """Расчет предполагаемого времени сканирования"""
    ips_per_server = total_ips / max(num_servers, 1)
    seconds_per_server = ips_per_server / rate_limit
    
    # Добавляем накладные расходы (инициализация, завершение)
    overhead_seconds = 60  # 1 минута накладных расходов
    
    total_seconds = seconds_per_server + overhead_seconds
    return timedelta(seconds=int(total_seconds))

def export_vulnerabilities_to_json(vulnerabilities: List[Dict[str, Any]]) -> str:
    """Экспорт уязвимостей в JSON"""
    export_data = {
        'export_date': datetime.utcnow().isoformat(),
        'total_count': len(vulnerabilities),
        'vulnerabilities': vulnerabilities
    }
    
    return json.dumps(export_data, indent=2, ensure_ascii=False, default=str)

def import_ip_list_from_file(file_content: str) -> List[str]:
    """Импорт списка IP из файла"""
    from utils.validators import validate_ip_address
    ips = []
    
    for line in file_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            # Пытаемся извлечь IP из строки
            if validate_ip_address(line):
                ips.append(line)
            else:
                # Пытаемся найти IP в строке с помощью регулярного выражения
                import re
                ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                matches = re.findall(ip_pattern, line)
                for match in matches:
                    if validate_ip_address(match):
                        ips.append(match)
    
    return list(set(ips))  # Удаляем дубликаты

def safe_str(value: Any) -> str:
    """Безопасное преобразование в строку"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)