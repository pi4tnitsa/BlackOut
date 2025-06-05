# services/ssh_service.py - Сервис SSH управления серверами
import paramiko
import threading
import time
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.server import Server
from utils.logger import get_logger

logger = get_logger(__name__)

class SSHService:
    """Сервис для SSH управления серверами"""
    
    def __init__(self, ssh_username: str, ssh_key_path: Optional[str] = None, ssh_password: Optional[str] = None):
        self.ssh_username = ssh_username
        self.ssh_key_path = ssh_key_path
        self.ssh_password = ssh_password
        self.connection_timeout = 30
        self.command_timeout = 300  # 5 минут для выполнения команд
    
    def execute_command(self, server: Server, command: str) -> Dict[str, Any]:
        """Выполнение команды на удаленном сервере"""
        ssh_client = None
        try:
            ssh_client = self._create_ssh_client(server)
            if not ssh_client:
                return {
                    'success': False,
                    'error': 'Не удалось подключиться к серверу',
                    'stdout': '',
                    'stderr': ''
                }
            
            logger.info(f"Выполнение команды на {server.hostname}: {command}")
            
            stdin, stdout, stderr = ssh_client.exec_command(
                command, 
                timeout=self.command_timeout
            )
            
            # Ожидание завершения команды
            exit_status = stdout.channel.recv_exit_status()
            
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            
            success = exit_status == 0
            
            logger.info(f"Команда {'выполнена успешно' if success else 'завершилась с ошибкой'} на {server.hostname}")
            
            return {
                'success': success,
                'exit_status': exit_status,
                'stdout': stdout_data,
                'stderr': stderr_data,
                'error': stderr_data if not success else None
            }
            
        except paramiko.AuthenticationException as e:
            logger.error(f"Ошибка аутентификации SSH на {server.hostname}: {e}")
            return {
                'success': False,
                'error': f'Ошибка аутентификации: {e}',
                'stdout': '',
                'stderr': ''
            }
        except paramiko.SSHException as e:
            logger.error(f"Ошибка SSH на {server.hostname}: {e}")
            return {
                'success': False,
                'error': f'Ошибка SSH: {e}',
                'stdout': '',
                'stderr': ''
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка SSH на {server.hostname}: {e}")
            return {
                'success': False,
                'error': f'Неожиданная ошибка: {e}',
                'stdout': '',
                'stderr': ''
            }
        finally:
            if ssh_client:
                ssh_client.close()
    
    def execute_command_on_servers(self, 
                                  servers: List[Server], 
                                  command: str,
                                  progress_callback: Optional[Callable] = None) -> Dict[int, Dict[str, Any]]:
        """Выполнение команды на множестве серверов параллельно"""
        results = {}
        
        def execute_on_server(server):
            result = self.execute_command(server, command)
            if progress_callback:
                progress_callback(server, result)
            return server.id, result
        
        # Выполняем команды параллельно
        with ThreadPoolExecutor(max_workers=min(len(servers), 10)) as executor:
            future_to_server = {
                executor.submit(execute_on_server, server): server 
                for server in servers
            }
            
            for future in as_completed(future_to_server):
                server = future_to_server[future]
                try:
                    server_id, result = future.result()
                    results[server_id] = result
                except Exception as e:
                    logger.error(f"Ошибка выполнения команды на сервере {server.hostname}: {e}")
                    results[server.id] = {
                        'success': False,
                        'error': str(e),
                        'stdout': '',
                        'stderr': ''
                    }
        
        return results
    
    def check_server_status(self, server: Server) -> Dict[str, Any]:
        """Проверка статуса сервера"""
        try:
            ssh_client = self._create_ssh_client(server)
            if not ssh_client:
                return {
                    'online': False,
                    'error': 'Не удалось подключиться'
                }
            
            # Получаем системную информацию
            commands = {
                'uptime': 'uptime',
                'cpu_usage': "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
                'memory_usage': "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100.0}'",
                'disk_usage': "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1",
                'nuclei_version': 'nuclei -version 2>/dev/null || echo "Не установлен"'
            }
            
            info = {'online': True}
            
            for key, cmd in commands.items():
                try:
                    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=10)
                    result = stdout.read().decode('utf-8', errors='ignore').strip()
                    info[key] = result
                except Exception as e:
                    info[key] = f'Ошибка: {e}'
            
            ssh_client.close()
            return info
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса сервера {server.hostname}: {e}")
            return {
                'online': False,
                'error': str(e)
            }
    
    def install_nuclei(self, server: Server) -> Dict[str, Any]:
        """Установка Nuclei на сервер"""
        install_commands = [
            # Обновление системы
            'sudo apt-get update -y',
            # Установка Go если не установлен
            'which go || (wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz && sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz)',
            # Добавление Go в PATH
            'echo "export PATH=$PATH:/usr/local/go/bin" >> ~/.bashrc',
            'export PATH=$PATH:/usr/local/go/bin',
            # Установка Nuclei
            'go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest',
            # Создание символической ссылки
            'sudo ln -sf ~/go/bin/nuclei /usr/local/bin/nuclei',
            # Обновление шаблонов
            'nuclei -update-templates'
        ]
        
        logger.info(f"Начало установки Nuclei на {server.hostname}")
        
        for i, command in enumerate(install_commands, 1):
            logger.info(f"Шаг {i}/{len(install_commands)}: {command}")
            result = self.execute_command(server, command)
            
            if not result['success'] and 'already exists' not in result['stderr'].lower():
                logger.error(f"Ошибка на шаге {i}: {result['error']}")
                return {
                    'success': False,
                    'error': f"Ошибка на шаге {i}: {result['error']}",
                    'step': i
                }
        
        # Проверка установки
        check_result = self.execute_command(server, 'nuclei -version')
        if check_result['success']:
            logger.info(f"Nuclei успешно установлен на {server.hostname}")
            return {
                'success': True,
                'version': check_result['stdout'].strip()
            }
        else:
            return {
                'success': False,
                'error': 'Не удалось проверить установку Nuclei'
            }
    
    def update_nuclei_templates(self, server: Server) -> Dict[str, Any]:
        """Обновление шаблонов Nuclei"""
        result = self.execute_command(server, 'nuclei -update-templates')
        
        if result['success']:
            logger.info(f"Шаблоны Nuclei обновлены на {server.hostname}")
        else:
            logger.error(f"Ошибка обновления шаблонов на {server.hostname}: {result['error']}")
        
        return result
    
    def deploy_custom_templates(self, server: Server, templates_archive_path: str) -> Dict[str, Any]:
        """Развертывание кастомных шаблонов на сервер"""
        try:
            ssh_client = self._create_ssh_client(server)
            if not ssh_client:
                return {
                    'success': False,
                    'error': 'Не удалось подключиться к серверу'
                }
            
            # Создание директории для кастомных шаблонов
            mkdir_result = self.execute_command(server, 'mkdir -p /opt/custom-templates')
            if not mkdir_result['success']:
                return mkdir_result
            
            # Загрузка архива с шаблонами
            sftp = ssh_client.open_sftp()
            remote_path = '/tmp/custom-templates.tar.gz'
            sftp.put(templates_archive_path, remote_path)
            sftp.close()
            
            # Извлечение архива
            extract_commands = [
                f'cd /opt/custom-templates && sudo tar -xzf {remote_path}',
                f'sudo rm {remote_path}',
                'sudo chown -R $(whoami):$(whoami) /opt/custom-templates'
            ]
            
            for command in extract_commands:
                result = self.execute_command(server, command)
                if not result['success']:
                    return result
            
            ssh_client.close()
            logger.info(f"Кастомные шаблоны развернуты на {server.hostname}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Ошибка развертывания шаблонов на {server.hostname}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_ssh_client(self, server: Server) -> Optional[paramiko.SSHClient]:
        """Создание SSH подключения"""
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Аутентификация по ключу или паролю
            if self.ssh_key_path:
                ssh_client.connect(
                    hostname=server.ip_address,
                    port=server.ssh_port,
                    username=self.ssh_username,
                    key_filename=self.ssh_key_path,
                    timeout=self.connection_timeout
                )
            elif self.ssh_password:
                ssh_client.connect(
                    hostname=server.ip_address,
                    port=server.ssh_port,
                    username=self.ssh_username,
                    password=self.ssh_password,
                    timeout=self.connection_timeout
                )
            else:
                logger.error("Не указан ни ключ, ни пароль для SSH")
                return None
            
            return ssh_client
            
        except Exception as e:
            logger.error(f"Ошибка создания SSH подключения к {server.hostname}: {e}")
            return None