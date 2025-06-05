# worker/nuclei_runner/scanner.py - ИСПРАВЛЕННАЯ версия (исправлен синтаксис регулярного выражения)
import os
import json
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)

class NucleiScanner:
    """Класс для запуска Nuclei сканирования"""
    
    def __init__(self, nuclei_config: Dict[str, Any]):
        self.binary_path = nuclei_config['binary_path']
        self.templates_path = nuclei_config['templates_path']
        self.rate_limit = nuclei_config['rate_limit']
        self.timeout = nuclei_config['timeout']
        self.retries = nuclei_config['retries']
        self.threads = nuclei_config['threads']
        
        # Проверяем доступность Nuclei
        if not self.check_nuclei_availability():
            raise RuntimeError("Nuclei недоступен")
    
    def check_nuclei_availability(self) -> bool:
        """Проверка доступности Nuclei"""
        try:
            result = subprocess.run(
                [self.binary_path, '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"Nuclei доступен: {version}")
                return True
            else:
                logger.error(f"Ошибка проверки Nuclei: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка проверки доступности Nuclei: {e}")
            return False
    
    def scan_targets(self, target_ips: List[str]) -> List[Dict[str, Any]]:
        """Сканирование списка IP-адресов"""
        if not target_ips:
            logger.warning("Список целей пуст")
            return []
        
        logger.info(f"Начало сканирования {len(target_ips)} целей")
        
        try:
            # Создаем временный файл с целями
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for ip in target_ips:
                    f.write(f"{ip}\n")
                targets_file = f.name
            
            try:
                # Запускаем Nuclei
                results = self._run_nuclei_scan(targets_file)
                
                # Парсим результаты
                vulnerabilities = self._parse_results(results)
                
                logger.info(f"Сканирование завершено. Найдено уязвимостей: {len(vulnerabilities)}")
                return vulnerabilities
                
            finally:
                # Удаляем временный файл
                try:
                    os.unlink(targets_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка сканирования: {e}")
            return []
    
    def _run_nuclei_scan(self, targets_file: str) -> str:
        """Запуск Nuclei сканирования"""
        command = [
            self.binary_path,
            '-l', targets_file,
            '-t', self.templates_path,
            '-rate-limit', str(self.rate_limit),
            '-timeout', str(self.timeout),
            '-retries', str(self.retries),
            '-c', str(self.threads),
            '-json',
            '-silent',
            '-no-color'
        ]
        
        logger.debug(f"Команда Nuclei: {' '.join(command)}")
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"Nuclei завершился с кодом {process.returncode}")
                if stderr:
                    logger.warning(f"Stderr: {stderr}")
            
            return stdout
            
        except Exception as e:
            logger.error(f"Ошибка запуска Nuclei: {e}")
            raise
    
    def _parse_results(self, nuclei_output: str) -> List[Dict[str, Any]]:
        """Парсинг результатов Nuclei"""
        vulnerabilities = []
        
        if not nuclei_output.strip():
            return vulnerabilities
        
        for line in nuclei_output.strip().split('\n'):
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                
                # Извлекаем IP-адрес из host
                host = data.get('host', '')
                ip_address = self._extract_ip_from_host(host)
                
                vulnerability = {
                    'ip_address': ip_address,
                    'template_method': data.get('template-id', ''),
                    'connection_method': data.get('type', ''),
                    'severity_level': data.get('info', {}).get('severity', 'info'),
                    'url': data.get('matched-at', host),
                    'additional_info': json.dumps({
                        'matcher_name': data.get('matcher-name', ''),
                        'description': data.get('info', {}).get('description', ''),
                        'tags': data.get('info', {}).get('tags', []),
                        'reference': data.get('info', {}).get('reference', []),
                        'classification': data.get('info', {}).get('classification', {}),
                        'curl_command': data.get('curl-command', ''),
                        'extracted_results': data.get('extracted-results', [])
                    }, ensure_ascii=False),
                    'timestamp': data.get('timestamp', None)
                }
                
                vulnerabilities.append(vulnerability)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга JSON: {e}")
                logger.debug(f"Проблемная строка: {line}")
                continue
            except Exception as e:
                logger.error(f"Ошибка обработки результата: {e}")
                continue
        
        return vulnerabilities
    
    def _extract_ip_from_host(self, host: str) -> str:
        """Извлечение IP-адреса из поля host"""
        import re
        
        # Удаляем протокол
        host = re.sub(r'^https?://', '', host)
        
        # Удаляем порт и путь
        host = host.split(':')[0].split('/')[0]
        
        # Проверяем, является ли это IP-адресом (ИСПРАВЛЕНО: добавлен закрывающий $)
        ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
        if re.match(ip_pattern, host):
            return host
        
        # Если это доменное имя, пытаемся разрешить его в IP
        try:
            import socket
            ip = socket.gethostbyname(host)
            return ip
        except:
            # Если не удалось разрешить, возвращаем как есть
            return host
