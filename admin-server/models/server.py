# admin-server/models/server.py - ИСПРАВЛЕННАЯ версия
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import ipaddress
from flask_login import UserMixin

@dataclass
class Server:
    """Модель сервера-воркера"""
    id: Optional[int] = None
    hostname: str = ""
    ip_address: str = ""
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
            hostname=data.get('hostname', ''),
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
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class User(UserMixin):
    """Модель пользователя для авторизации"""
    def __init__(self, username):
        self.id = "1"  # Строка для Flask-Login
        self.username = username
        self.is_active_user = True
        self.is_anonymous_user = False
        self.is_authenticated_user = True
    
    def is_authenticated(self):
        return self.is_authenticated_user
    
    def is_active(self):
        return self.is_active_user
    
    def is_anonymous(self):
        return self.is_anonymous_user
    
    def get_id(self):
        """Метод get_id() обязателен для Flask-Login"""
        return str(self.id)
    
    @staticmethod
    def get(user_id):
        """Статический метод для получения пользователя по ID"""
        # Простая проверка - в реальном приложении здесь была бы проверка БД
        if str(user_id) == "1":
            from config.settings import Config
            return User(Config.ADMIN_USERNAME)
        return None
