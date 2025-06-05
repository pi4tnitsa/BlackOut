# utils/helpers.py для воркера
import ipaddress
import hashlib
from typing import List
from utils.logger import get_logger

logger = get_logger(__name__)

def validate_ip_address(ip: str) -> bool:
    """Валидация IP-адреса"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def expand_ip_range(ip_range: str) -> List[str]:
    """Расширение IP-диапазона в список адресов"""
    try:
        if '/' in ip_range:
            # CIDR нотация
            network = ipaddress.ip_network(ip_range, strict=False)
            return [str(ip) for ip in network.hosts()]
        
        elif '-' in ip_range:
            # Диапазон
            start_ip, end_ip = ip_range.split('-')
            start = ipaddress.ip_address(start_ip.strip())
            end = ipaddress.ip_address(end_ip.strip())
            
            if start > end:
                start, end = end, start
            
            ips = []
            current = start
            while current <= end:
                ips.append(str(current))
                current += 1
            return ips
        
        else:
            # Одиночный IP
            if validate_ip_address(ip_range):
                return [ip_range]
            else:
                return []
                
    except Exception as e:
        logger.error(f"Ошибка обработки IP-диапазона {ip_range}: {e}")
        return []

def calculate_file_hash(file_path: str) -> str:
    """Вычисление хеша файла"""
    hash_md5 = hashlib.md5()
    
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Ошибка вычисления хеша файла {file_path}: {e}")
        return ""
