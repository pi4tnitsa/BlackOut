# utils/validators.py - Валидация данных
import ipaddress
import re
from typing import List, Tuple, Optional

def validate_ip_address(ip: str) -> bool:
    """Валидация IP-адреса"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_ip_range(ip_range: str) -> Tuple[bool, Optional[str]]:
    """Валидация IP-диапазона"""
    try:
        if '/' in ip_range:
            # CIDR нотация
            network = ipaddress.ip_network(ip_range, strict=False)
            if network.num_addresses > 65536:  # Ограничение на размер сети
                return False, "Слишком большой диапазон (максимум /16)"
            return True, None
        
        elif '-' in ip_range:
            # Диапазон
            parts = ip_range.split('-')
            if len(parts) != 2:
                return False, "Неверный формат диапазона"
            
            start_ip = parts[0].strip()
            end_ip = parts[1].strip()
            
            if not validate_ip_address(start_ip) or not validate_ip_address(end_ip):
                return False, "Некорректные IP-адреса в диапазоне"
            
            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)
            
            if start > end:
                return False, "Начальный IP больше конечного"
            
            if int(end) - int(start) > 65536:
                return False, "Слишком большой диапазон (максимум 65536 адресов)"
            
            return True, None
        
        else:
            # Одиночный IP
            if validate_ip_address(ip_range):
                return True, None
            else:
                return False, "Некорректный IP-адрес"
                
    except Exception as e:
        return False, f"Ошибка валидации: {str(e)}"

def validate_hostname(hostname: str) -> bool:
    """Валидация имени хоста"""
    if len(hostname) > 253:
        return False
    
    if hostname[-1] == ".":
        hostname = hostname[:-1]
    
    allowed = re.compile("(?!-)[A-Z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))

def validate_port(port: int) -> bool:
    """Валидация номера порта"""
    return 1 <= port <= 65535

def validate_severity_level(severity: str) -> bool:
    """Валидация уровня критичности"""
    allowed_severities = ['info', 'low', 'medium', 'high', 'critical']
    return severity.lower() in allowed_severities

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Очистка пользовательского ввода"""
    if not text:
        return ""
    
    # Удаляем опасные символы
    text = re.sub(r'[<>"\';()&+]', '', text)
    
    # Ограничиваем длину
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()