# services/task_distributor.py - Распределитель задач сканирования - ИСПРАВЛЕННАЯ версия
import ipaddress
import math
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.server import Server
from models.task import ScanTask
from models.vulnerability import Vulnerability
from services.database_service import DatabaseService
from services.ssh_service import SSHService
from services.telegram_service import TelegramService
from utils.logger import get_logger

logger = get_logger(__name__)

class TaskDistributor:
    """Распределитель задач сканирования по серверам"""
    
    def __init__(self, database_name: str = 'belarus'):
        self.database_name = database_name
        self.db_service = DatabaseService(database_name)
        self.ssh_service = None  # Инициализируется при необходимости
        self.telegram_service = TelegramService()
        
        # Конфигурация сканирования
        self.nuclei_config = {
            'rate_limit': 100,  # Запросов в секунду
            'timeout': 30,      # Таймаут соединения
            'retries': 2,       # Количество повторов
            'threads': 50       # Количество потоков
        }
    
    def set_ssh_service(self, ssh_service: SSHService):
        """Установка SSH сервиса"""
        self.ssh_service = ssh_service
    
    def distribute_ip_ranges(self, ip_ranges: List[str], servers: List[Server]) -> Dict[int, List[str]]:
        """Распределение IP-диапазонов по серверам"""
        if not servers:
            raise ValueError("Список серверов пуст")
        
        # Преобразуем диапазоны в список IP-адресов
        all_ips = []
        for ip_range in ip_ranges:
            all_ips.extend(self._expand_ip_range(ip_range))
        
        if not all_ips:
            return {}
        
        # Распределяем IP-адреса равномерно по серверам
        ips_per_server = math.ceil(len(all_ips) / len(servers))
        
        distribution = {}
        for i, server in enumerate(servers):
            start_idx = i * ips_per_server
            end_idx = min((i + 1) * ips_per_server, len(all_ips))
            distribution[server.id] = all_ips[start_idx:end_idx]
        
        logger.info(f"Распределено {len(all_ips)} IP-адресов по {len(servers)} серверам")
        return distribution
    
    def create_scan_task(self, 
                        name: str, 
                        ip_ranges: List[str], 
                        server_ids: List[int],
                        template_path: str = '/opt/custom-templates') -> Optional[int]:
        """Создание задачи сканирования"""
        try:
            # Получаем серверы
            all_servers = self.db_service.get_servers()
            selected_servers = [s for s in all_servers if s.id in server_ids]
            
            if not selected_servers:
                raise ValueError("Не найдены указанные серверы")
            
            # Распределяем IP-адреса
            ip_distribution = self.distribute_ip_ranges(ip_ranges, selected_servers)
            
            # Создаем задачу
            task = ScanTask(
                name=name,
                target_ips=ip_ranges,
                server_ids=server_ids,
                status='pending'
            )
            
            task_id = self.db_service.save_task(task)
            
            logger.info(f"Создана задача сканирования: {name} (ID: {task_id})")
            
            # Отправляем уведомление
            self.telegram_service.send_scan_notification(
                f"Создана задача '{name}'\n"
                f"Серверов: {len(selected_servers)}\n"
                f"IP-адресов: {sum(len(ips) for ips in ip_distribution.values())}"
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            raise
    
    def execute_scan_task(self, task_id: int) -> bool:
        """Выполнение задачи сканирования"""
        if not self.ssh_service:
            logger.error("SSH сервис не настроен")
            return False
        
        try:
            # Получаем задачу
            tasks = self.db_service.get_tasks()
            task = next((t for t in tasks if t.id == task_id), None)
            
            if not task:
                logger.error(f"Задача {task_id} не найдена")
                return False
            
            # Обновляем статус задачи
            self.db_service.update_task_status(task_id, 'running')
            
            # Получаем серверы
            all_servers = self.db_service.get_servers()
            selected_servers = [s for s in all_servers if s.id in task.server_ids]
            
            # Распределяем IP-адреса
            ip_distribution = self.distribute_ip_ranges(task.target_ips, selected_servers)
            
            logger.info(f"Начало выполнения задачи {task.name}")
            
            # Отправляем уведомление о начале
            self.telegram_service.send_scan_notification(
                f"Начато выполнение задачи '{task.name}'\n"
                f"Серверов: {len(selected_servers)}"
            )
            
            # Выполняем сканирование на всех серверах параллельно
            success_count = 0
            total_vulnerabilities = 0
            
            def process_server_results(server, result):
                nonlocal total_vulnerabilities
                if result['success']:
                    # Парсим результаты и сохраняем уязвимости
                    vulns = self._parse_nuclei_output(result['stdout'], server.id)
                    total_vulnerabilities += len(vulns)
                    
                    for vuln in vulns:
                        vuln_id = self.db_service.save_vulnerability(vuln)
                        if vuln_id and vuln.severity_level in ['critical', 'high']:
                            # Отправляем уведомление о найденной уязвимости
                            self.telegram_service.send_vulnerability_alert(vuln, self.database_name)
            
            # Запускаем сканирование на серверах
            for server in selected_servers:
                server_ips = ip_distribution.get(server.id, [])
                if server_ips:
                    scan_command = self._build_nuclei_command(server_ips, '/opt/custom-templates')
                    result = self.ssh_service.execute_command(server, scan_command)
                    
                    if result['success']:
                        success_count += 1
                        process_server_results(server, result)
                    else:
                        logger.error(f"Ошибка сканирования на сервере {server.hostname}: {result['error']}")
            
            # Обновляем статус задачи
            final_status = 'completed' if success_count > 0 else 'failed'
            self.db_service.update_task_status(task_id, final_status)
            
            # Отправляем итоговое уведомление
            self.telegram_service.send_scan_notification(
                f"Завершена задача '{task.name}'\n"
                f"Успешно выполнено на {success_count}/{len(selected_servers)} серверов\n"
                f"Найдено уязвимостей: {total_vulnerabilities}"
            )
            
            logger.info(f"Задача {task.name} завершена. Найдено уязвимостей: {total_vulnerabilities}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка выполнения задачи {task_id}: {e}")
            self.db_service.update_task_status(task_id, 'failed')
            return False
    
    def _expand_ip_range(self, ip_range: str) -> List[str]:
        """Расширение IP-диапазона в список адресов"""
        try:
            # Проверяем различные форматы
            if '/' in ip_range:
                # CIDR нотация (например, 192.168.1.0/24)
                network = ipaddress.ip_network(ip_range, strict=False)
                return [str(ip) for ip in network.hosts()]
            
            elif '-' in ip_range:
                # Диапазон (например, 192.168.1.1-192.168.1.100)
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
                ipaddress.ip_address(ip_range)
                return [ip_range]
                
        except Exception as e:
            logger.error(f"Ошибка обработки IP-диапазона {ip_range}: {e}")
            return []
    
    def _build_nuclei_command(self, target_ips: List[str], template_path: str) -> str:
        """Построение команды для запуска Nuclei"""
        # Создаем временный файл с IP-адресами
        ips_file = '/tmp/target_ips.txt'
        ips_content = '\n'.join(target_ips)
        
        # Основная команда Nuclei
        nuclei_cmd = f"""
echo '{ips_content}' > {ips_file} && \\
nuclei \\
  -l {ips_file} \\
  -t {template_path} \\
  -rate-limit {self.nuclei_config['rate_limit']} \\
  -timeout {self.nuclei_config['timeout']} \\
  -retries {self.nuclei_config['retries']} \\
  -c {self.nuclei_config['threads']} \\
  -json \\
  -silent \\
  -no-color \\
  && rm {ips_file}
        """.strip()
        
        return nuclei_cmd
    
    def _parse_nuclei_output(self, output: str, source_host_id: int) -> List[Vulnerability]:
        """Парсинг вывода Nuclei в формате JSON"""
        vulnerabilities = []
        
        try:
            for line in output.strip().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Извлекаем информацию об уязвимости
                    host = data.get('host', '')
                    ip_address = self._extract_ip_from_host(host)
                    
                    vuln = Vulnerability(
                        ip_address=ip_address,
                        template_method=data.get('template-id', ''),
                        connection_method=data.get('type', ''),
                        severity_level=data.get('info', {}).get('severity', 'info'),
                        url=data.get('matched-at', data.get('host', '')),
                        additional_info=json.dumps({
                            'matcher_name': data.get('matcher-name', ''),
                            'description': data.get('info', {}).get('description', ''),
                            'tags': data.get('info', {}).get('tags', []),
                            'reference': data.get('info', {}).get('reference', []),
                            'classification': data.get('info', {}).get('classification', {}),
                            'curl_command': data.get('curl-command', ''),
                            'extracted_results': data.get('extracted-results', [])
                        }, ensure_ascii=False),
                        source_host_id=source_host_id,
                        timestamp=datetime.utcnow()
                    )
                    
                    vulnerabilities.append(vuln)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Ошибка парсинга JSON строки: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка парсинга вывода Nuclei: {e}")
        
        return vulnerabilities
    
    def _extract_ip_from_host(self, host: str) -> str:
        """Извлечение IP-адреса из поля host"""
        import re
        
        if not host:
            return 'unknown'
        
        # Удаляем протокол
        clean_host = re.sub(r'^https?://', '', host)
        
        # Удаляем порт и путь
        clean_host = clean_host.split(':')[0].split('/')[0]
        
        # Проверяем, является ли это IP-адресом
        ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
        if re.match(ip_pattern, clean_host):
            return clean_host
        
        # Если это доменное имя, пытаемся разрешить его в IP
        try:
            import socket
            ip = socket.gethostbyname(clean_host)
            return ip
        except Exception:
            # Если не удалось разрешить, возвращаем как есть
            return clean_host