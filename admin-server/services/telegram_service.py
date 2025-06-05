# services/telegram_service.py - Сервис Telegram уведомлений
import requests
import json
from typing import Optional, Dict, Any
from config.settings import Config
from models.vulnerability import Vulnerability
from utils.logger import get_logger

logger = get_logger(__name__)

class TelegramService:
    """Сервис для отправки уведомлений в Telegram"""
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Настройки фильтрации по критичности
        self.severity_filter = ['high', 'critical']  # Отправлять только важные уязвимости
        
        # Эмодзи для разных уровней критичности
        self.severity_emojis = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢',
            'info': '🔵'
        }
    
    def send_vulnerability_alert(self, vulnerability: Vulnerability, database_name: str) -> bool:
        """Отправка уведомления о найденной уязвимости"""
        if not self._should_send_alert(vulnerability):
            return True  # Фильтрация - не отправляем
        
        message = self._format_vulnerability_message(vulnerability, database_name)
        return self._send_message(message)
    
    def send_scan_notification(self, message: str) -> bool:
        """Отправка уведомления о статусе сканирования"""
        return self._send_message(f"📊 Статус сканирования:\n{message}")
    
    def send_server_alert(self, server_name: str, status: str, details: str = "") -> bool:
        """Отправка уведомления о статусе сервера"""
        emoji = "✅" if status == "online" else "❌"
        message = f"{emoji} Сервер: {server_name}\nСтатус: {status}"
        if details:
            message += f"\nДетали: {details}"
        
        return self._send_message(message)
    
    def _should_send_alert(self, vulnerability: Vulnerability) -> bool:
        """Проверка, нужно ли отправлять уведомление"""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram не настроен")
            return False
        
        # Фильтрация по уровню критичности
        if vulnerability.severity_level not in self.severity_filter:
            return False
        
        return True
    
    def _format_vulnerability_message(self, vulnerability: Vulnerability, database_name: str) -> str:
        """Форматирование сообщения об уязвимости"""
        emoji = self.severity_emojis.get(vulnerability.severity_level, '⚪')
        
        message = f"""🚨 НАЙДЕНА УЯЗВИМОСТЬ {emoji}

📍 Регион: {database_name.upper()}
🎯 IP-адрес: {vulnerability.ip_address}
🔍 Шаблон: {vulnerability.template_method or 'Неизвестно'}
🌐 Метод: {vulnerability.connection_method or 'Неизвестно'}
⚠️ Критичность: {vulnerability.severity_level.upper()}
🔗 URL: {vulnerability.url or 'Не указан'}
🖥️ Источник: Сервер #{vulnerability.source_host_id or 'Неизвестно'}
⏰ Время: {vulnerability.timestamp.strftime('%Y-%m-%d %H:%M:%S') if vulnerability.timestamp else 'Неизвестно'}

📝 Дополнительно: {vulnerability.additional_info or 'Нет данных'}"""
        
        return message
    
    def _send_message(self, message: str) -> bool:
        """Отправка сообщения в Telegram"""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram не настроен")
            return False
        
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Уведомление отправлено в Telegram")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка Telegram: {e}")
            return False
    
    def test_connection(self) -> Dict[str, Any]:
        """Тестирование подключения к Telegram"""
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('ok'):
                return {
                    'success': True,
                    'bot_info': data.get('result', {})
                }
            else:
                return {
                    'success': False,
                    'error': data.get('description', 'Неизвестная ошибка')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }