# models/task.py - Модель задач сканирования
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class ScanTask:
    """Модель задачи сканирования"""
    id: Optional[int] = None
    name: str = None
    target_ips: List[str] = None
    server_ids: List[int] = None
    status: str = 'pending'
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Инициализация значений по умолчанию"""
        if self.target_ips is None:
            self.target_ips = []
        if self.server_ids is None:
            self.server_ids = []
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создание объекта из словаря"""
        return cls(
            id=data.get('id'),
            name=data.get('name'),
            target_ips=data.get('target_ips', []),
            server_ids=data.get('server_ids', []),
            status=data.get('status', 'pending'),
            started_at=data.get('started_at'),
            completed_at=data.get('completed_at'),
            created_at=data.get('created_at')
        )
    
    def to_dict(self) -> dict:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'target_ips': self.target_ips,
            'server_ids': self.server_ids,
            'status': self.status,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at
        }
