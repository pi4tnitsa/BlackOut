# worker/nuclei_runner/scanner.py - ИСПРАВЛЕННАЯ версия
import os
import subprocess
import tempfile
from typing import List, Dict, Any
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)

class NucleiScanner:
    """Класс для запуска Nuclei сканирования"""
    
    def __init__(self, nuclei_config: Dict[str, Any]):
        self.binary_path = nuclei_config.get('binary_path', '/usr/local/bin/nuclei')
        self.templates_path = nuclei_config.get('templates_path', '/opt/custom-templates')
        self.rate_limit = nuclei_config.get('rate_limit', 100)
        self.timeout = nuclei_config.get('timeout', 30)
        self.retries = nuclei_config.get('retries', 2)
        self.threads = nuclei_config.get('threads', 50)
        
        # Проверяем доступность Nuclei
        if not self.check_nuclei_availability():
            logger.warning("Nuclei недоступен при инициализации")

    def check_nuclei_availability(self) -> bool:
        """Проверка доступности Nuclei"""
        try:
            if not os.path.exists(self.binary_path):
                logger.error(f"Бинарный файл Nuclei не найден: {self.binary_path}")
                return False
                
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
                
        except FileNotFoundError:
            logger.error(f"Nuclei не найден: {self.binary_path}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при проверке Nuclei")
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки доступности Nuclei: {e}")
            return False
    
    def scan_targets(self, target_ips: List[str]) -> str:
        """Сканирование списка IP-адресов, возвращает JSON строку"""
        if not target_ips:
            logger.warning("Список целей пуст")
            return ""
        
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
                
                logger.info(f"Сканирование завершено")
                return results
                
            finally:
                # Удаляем временный файл
                try:
                    os.unlink(targets_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка сканирования: {e}")
            return ""
    
    def _run_nuclei_scan(self, targets_file: str) -> str:
        """Запуск Nuclei сканирования"""
        command = [
            self.binary_path,
            '-l', targets_file,
            '-rate-limit', str(self.rate_limit),
            '-timeout', str(self.timeout),
            '-retries', str(self.retries),
            '-c', str(self.threads),
            '-json',
            '-silent',
            '-no-color'
        ]
        
        # Добавляем шаблоны, если директория существует
        if os.path.exists(self.templates_path) and os.listdir(self.templates_path):
            command.extend(['-t', self.templates_path])
        else:
            logger.warning(f"Директория шаблонов {self.templates_path} пуста или не существует")
            # Используем встроенные шаблоны Nuclei
            command.extend(['-t', 'http,ssl,dns'])
        
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