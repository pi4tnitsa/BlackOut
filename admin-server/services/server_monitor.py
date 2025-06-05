# services/server_monitor.py - Мониторинг серверов
import time
import threading
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
from services.database_service import DatabaseService
from services.ssh_service import SSHService
from services.telegram_service import TelegramService
from models.server import Server
from utils.logger import get_logger

logger = get_logger(__name__)

class ServerMonitor:
    """Сервис мониторинга серверов"""
    
    def __init__(self, database_name: str = 'belarus'):
        self.database_name = database_name
        self.db_service = DatabaseService(database_name)
        self.ssh_service = None
        self.telegram_service = TelegramService()
        
        # Настройки мониторинга
        self.check_interval = 300  # 5 минут между проверками
        self.offline_threshold = 600  # 10 минут до пометки как offline
        
        # Флаг для остановки мониторинга
        self._stop_monitoring = False
        self._monitoring_thread = None
        
        # Кэш статусов серверов
        self._server_statuses = {}
    
    def set_ssh_service(self, ssh_service: SSHService):
        """Установка SSH сервиса"""
        self.ssh_service = ssh_service
    
    def start_monitoring(self):
        """Запуск мониторинга в отдельном потоке"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Мониторинг уже запущен")
            return
        
        self._stop_monitoring = False
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ServerMonitor"
        )
        self._monitoring_thread.start()
        logger.info("Мониторинг серверов запущен")
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        self._stop_monitoring = True
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=30)
        logger.info("Мониторинг серверов остановлен")
    
    def check_all_servers(self) -> Dict[int, Dict[str, Any]]:
        """Проверка состояния всех серверов"""
        if not self.ssh_service:
            logger.error("SSH сервис не настроен")
            return {}
        
        servers = self.db_service.get_servers()
        results = {}
        
        for server in servers:
            try:
                status_info = self.ssh_service.check_server_status(server)
                
                # Определяем статус сервера
                if status_info.get('online', False):
                    new_status = 'online'
                    self.db_service.update_server_status(server.id, 'online')
                else:
                    new_status = 'offline'
                    self.db_service.update_server_status(server.id, 'offline')
                
                # Проверяем изменение статуса для уведомлений
                old_status = self._server_statuses.get(server.id)
                if old_status != new_status:
                    self._server_statuses[server.id] = new_status
                    
                    # Отправляем уведомление об изменении статуса
                    if old_status is not None:  # Не отправляем при первой проверке
                        self.telegram_service.send_server_alert(
                            server.hostname,
                            new_status,
                            status_info.get('error', '')
                        )
                
                results[server.id] = {
                    'server': server,
                    'status': new_status,
                    'info': status_info,
                    'last_check': datetime.utcnow()
                }
                
            except Exception as e:
                logger.error(f"Ошибка проверки сервера {server.hostname}: {e}")
                results[server.id] = {
                    'server': server,
                    'status': 'error',
                    'info': {'error': str(e)},
                    'last_check': datetime.utcnow()
                }
        
        return results
    
    def get_server_metrics(self, server_id: int) -> Dict[str, Any]:
        """Получение метрик конкретного сервера"""
        if not self.ssh_service:
            return {'error': 'SSH сервис не настроен'}
        
        servers = self.db_service.get_servers()
        server = next((s for s in servers if s.id == server_id), None)
        
        if not server:
            return {'error': 'Сервер не найден'}
        
        try:
            # Получаем детальную информацию о сервере
            commands = {
                'system_info': 'uname -a',
                'uptime': 'uptime -p',
                'cpu_count': 'nproc',
                'cpu_usage': "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
                'memory_total': "free -m | grep Mem | awk '{print $2}'",
                'memory_used': "free -m | grep Mem | awk '{print $3}'",
                'memory_percent': "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100.0}'",
                'disk_usage': "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1",
                'disk_total': "df -h / | tail -1 | awk '{print $2}'",
                'disk_available': "df -h / | tail -1 | awk '{print $4}'",
                'network_connections': 'ss -tuln | wc -l',
                'processes': 'ps aux | wc -l',
                'load_average': "uptime | awk -F'load average:' '{print $2}'",
                'nuclei_version': 'nuclei -version 2>/dev/null || echo "Не установлен"',
                'python_version': 'python3 --version 2>/dev/null || echo "Не установлен"',
                'go_version': 'go version 2>/dev/null || echo "Не установлен"'
            }
            
            metrics = {'server_id': server_id, 'hostname': server.hostname}
            
            for key, command in commands.items():
                result = self.ssh_service.execute_command(server, command)
                if result['success']:
                    metrics[key] = result['stdout'].strip()
                else:
                    metrics[key] = f"Ошибка: {result['error']}"
            
            # Добавляем временную метку
            metrics['collected_at'] = datetime.utcnow().isoformat()
            
            return metrics
            
        except Exception as e:
            logger.error(f"Ошибка получения метрик сервера {server.hostname}: {e}")
            return {'error': str(e)}
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Получение сводки мониторинга"""
        servers = self.db_service.get_servers()
        
        summary = {
            'total_servers': len(servers),
            'online_servers': 0,
            'offline_servers': 0,
            'error_servers': 0,
            'last_update': datetime.utcnow().isoformat(),
            'servers_detail': []
        }
        
        for server in servers:
            status = self._server_statuses.get(server.id, 'unknown')
            
            if status == 'online':
                summary['online_servers'] += 1
            elif status == 'offline':
                summary['offline_servers'] += 1
            else:
                summary['error_servers'] += 1
            
            summary['servers_detail'].append({
                'id': server.id,
                'hostname': server.hostname,
                'ip_address': server.ip_address,
                'status': status,
                'last_seen': server.last_seen.isoformat() if server.last_seen else None
            })
        
        return summary
    
    def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("Запущен цикл мониторинга серверов")
        
        while not self._stop_monitoring:
            try:
                start_time = time.time()
                
                # Проверяем все серверы
                self.check_all_servers()
                
                # Вычисляем время выполнения
                execution_time = time.time() - start_time
                logger.debug(f"Проверка серверов завершена за {execution_time:.2f} секунд")
                
                # Ожидаем до следующей проверки
                sleep_time = max(0, self.check_interval - execution_time)
                
                for _ in range(int(sleep_time)):
                    if self._stop_monitoring:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(60)  # Ждем минуту перед повторной попыткой
        
        logger.info("Цикл мониторинга серверов завершен")