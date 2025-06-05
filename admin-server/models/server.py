# models/server.py - Модель серверов
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from flask_login import UserMixin

@dataclass
class Server:
    """Модель сервера-воркера"""
    id: Optional[int] = None
    hostname: str = None
    ip_address: str = None
    ssh_port: int = 22
    status: str = 'offline'
    last_seen: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Валидация данных"""
        if self.ip_address:
            try:
                ipaddress.ip_address(self.ip_address)
            except ValueError:
                raise ValueError(f"Некорректный IP-адрес: {self.ip_address}")
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создание объекта из словаря"""
        return cls(
            id=data.get('id'),
            hostname=data.get('hostname'),
            ip_address=str(data.get('ip_address', '')),
            ssh_port=data.get('ssh_port', 22),
            status=data.get('status', 'offline'),
            last_seen=data.get('last_seen'),
            created_at=data.get('created_at')
        )
    
    def to_dict(self) -> dict:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'ssh_port': self.ssh_port,
            'status': self.status,
            'last_seen': self.last_seen,
            'created_at': self.created_at
        }

class User(UserMixin):
    """Модель пользователя для авторизации"""
    def __init__(self, username):
        self.id = 1  # Единственный администратор
        self.username = username
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
