#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nuclei Scanner Worker - Воркер для выполнения сканирования
Автономный модуль для выполнения задач сканирования с помощью Nuclei
"""

import os
import sys
import json
import time
import argparse
import subprocess
import threading
import requests
import logging
from datetime import datetime
import signal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/nuclei-worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class NucleiWorker:
    def __init__(self, server_url, server_id=None):
        self.server_url = server_url.rstrip('/')
        self.server_id = server_id or self._get_server_id()
        self.running = True
        self.nuclei_path = self._find_nuclei_binary()
        self.templates_path = '/opt/nuclei-templates'
        
        # Создаём директории если не существуют
        os.makedirs('/tmp/nuclei-results', exist_ok=True)
        os.makedirs(self.templates_path, exist_ok=True)
        
        logger.info(f"Воркер инициализирован. Server ID: {self.server_id}")
    
    def _get_server_id(self):
        """Получение ID сервера по IP адресу"""
        try:
            # Простой способ получить внешний IP
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Можно добавить логику определения ID сервера по IP
            # Пока возвращаем заглушку
            return 1
        except Exception as e:
            logger.error(f"Ошибка получения server_id: {e}")
            return 1
    
    def _find_nuclei_binary(self):
        """Поиск исполняемого файла Nuclei"""
        paths = ['/usr/local/bin/nuclei', '/usr/bin/nuclei', '/opt/nuclei/nuclei', 'nuclei']
        
        for path in paths:
            try:
                result = subprocess.run([path, '-version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"Найден Nuclei: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        logger.error("Nuclei не найден в системе!")
        sys.exit(1)
    
    def update_nuclei_templates(self):
        """Обновление шаблонов Nuclei"""
        try:
            logger.info("Обновление шаблонов Nuclei...")
            
            # Обновляем встроенные шаблоны
            result = subprocess.run([
                self.nuclei_path, '-update-templates', '-silent'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("Шаблоны Nuclei успешно обновлены")
            else:
                logger.warning(f"Предупреждение при обновлении шаблонов: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при обновлении шаблонов")
        except Exception as e:
            logger.error(f"Ошибка обновления шаблонов: {e}")
    
    def send_heartbeat(self):
        """Отправка heartbeat на центральный сервер"""
        while self.running:
            try:
                data = {
                    'server_id': self.server_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'status': 'online'
                }
                
                response = requests.post(
                    f"{self.server_url}/api/worker/heartbeat",
                    json=data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.debug("Heartbeat отправлен успешно")
                else:
                    logger.warning(f"Ошибка отправки heartbeat: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Ошибка отправки heartbeat: {e}")
            
            time.sleep(30)  # Отправляем каждые 30 секунд
    
    def submit_vulnerability(self, vulnerability_data):
        """Отправка найденной уязвимости на сервер"""
        try:
            vulnerability_data['source_server_id'] = self.server_id
            
            response = requests.post(
                f"{self.server_url}/api/worker/submit_vulnerability",
                json=vulnerability_data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Уязвимость отправлена: {vulnerability_data['template_id']} -> {vulnerability_data['ip_address']}")
                return True
            else:
                logger.error(f"Ошибка отправки уязвимости: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка отправки уязвимости: {e}")
            return False
    
    def notify_task_complete(self, task_id):
        """Уведомление о завершении задачи"""
        try:
            data = {
                'task_id': task_id,
                'server_id': self.server_id,
                'completed_at': datetime.utcnow().isoformat()
            }
            
            response = requests.post(
                f"{self.server_url}/api/worker/task_complete",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Уведомление о завершении задачи {task_id} отправлено")
            else:
                logger.error(f"Ошибка отправки уведомления о завершении: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о завершении: {e}")
    
    def parse_nuclei_output(self, output_line):
        """Парсинг вывода Nuclei"""
        try:
            # Nuclei может выводить результаты в JSON формате
            if output_line.strip().startswith('[') and output_line.strip().endswith(']'):
                data = json.loads(output_line.strip())
                
                # Преобразуем в наш формат
                vulnerability = {
                    'ip_address': data.get('host', '').replace('http://', '').replace('https://', '').split(':')[0],
                    'template_id': data.get('template-id', ''),
                    'matcher_name': data.get('matcher-name', ''),
                    'severity_level': data.get('info', {}).get('severity', 'unknown'),
                    'url': data.get('matched-at', ''),
                    'request_data': json.dumps(data.get('request', {})),
                    'response_data': json.dumps(data.get('response', {})),
                    'metadata': {
                        'template_info': data.get('info', {}),
                        'curl_command': data.get('curl-command', ''),
                        'raw_data': data
                    }
                }
                
                return vulnerability
                
            # Альтернативный парсинг для простого формата
            elif '[' in output_line and ']' in output_line:
                parts = output_line.strip().split()
                if len(parts) >= 3:
                    return {
                        'ip_address': parts[-1].replace('http://', '').replace('https://', '').split(':')[0],
                        'template_id': parts[0].strip('[]'),
                        'matcher_name': '',
                        'severity_level': 'info',
                        'url': parts[-1] if parts[-1].startswith('http') else '',
                        'request_data': '',
                        'response_data': '',
                        'metadata': {'raw_output': output_line.strip()}
                    }
                    
        except json.JSONDecodeError:
            logger.debug(f"Не удалось распарсить как JSON: {output_line}")
        except Exception as e:
            logger.error(f"Ошибка парсинга вывода Nuclei: {e}")
        
        return None
    
    def run_nuclei_scan(self, targets, templates, task_id):
        """Выполнение сканирования Nuclei"""
        logger.info(f"Запуск сканирования задачи {task_id}: {len(targets)} целей, {len(templates)} шаблонов")
        
        # Создаём временный файл с целями
        targets_file = f'/tmp/nuclei-targets-{task_id}.txt'
        with open(targets_file, 'w') as f:
            for target in targets:
                f.write(f"{target}\n")
        
        try:
            # Формируем команду Nuclei
            cmd = [
                self.nuclei_path,
                '-l', targets_file,
                '-json',  # Вывод в JSON формате
                '-silent',  # Тихий режим
                '-o', f'/tmp/nuclei-results/task-{task_id}-results.json'
            ]
            
            # Добавляем шаблоны
            if templates:
                if isinstance(templates, list):
                    for template in templates:
                        cmd.extend(['-t', template])
                else:
                    cmd.extend(['-t', templates])
            else:
                # Используем все шаблоны по умолчанию
                cmd.extend(['-t', f"{self.templates_path}/"])
            
            # Дополнительные параметры
            cmd.extend([
                '-timeout', '10',  # Таймаут для каждого запроса
                '-retries', '1',   # Количество повторов
                '-rate-limit', '100',  # Ограничение скорости
                '-bulk-size', '25'     # Размер пакета
            ])
            
            logger.info(f"Команда Nuclei: {' '.join(cmd)}")
            
            # Запускаем Nuclei
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Читаем вывод в реальном времени
            vulnerabilities_found = 0
            
            for line in iter(process.stdout.readline, ''):
                if not self.running:
                    process.terminate()
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Парсим найденную уязвимость
                vulnerability = self.parse_nuclei_output(line)
                if vulnerability:
                    vulnerability['task_id'] = task_id
                    
                    # Отправляем уязвимость на сервер
                    if self.submit_vulnerability(vulnerability):
                        vulnerabilities_found += 1
                    
                    logger.info(f"Найдена уязвимость: {vulnerability['template_id']} -> {vulnerability['ip_address']}")
            
            # Ждём завершения процесса
            process.wait()
            
            # Читаем ошибки если есть
            stderr_output = process.stderr.read()
            if stderr_output:
                logger.warning(f"Nuclei stderr: {stderr_output}")
            
            logger.info(f"Сканирование задачи {task_id} завершено. Найдено уязвимостей: {vulnerabilities_found}")
            
            # Уведомляем сервер о завершении
            self.notify_task_complete(task_id)
            
            return vulnerabilities_found
            
        except Exception as e:
            logger.error(f"Ошибка выполнения сканирования: {e}")
            return 0
        finally:
            # Удаляем временные файлы
            try:
                os.remove(targets_file)
            except:
                pass
    
    def start_daemon_mode(self):
        """Запуск воркера в режиме демона"""
        logger.info("Запуск воркера в режиме демона")
        
        # Запускаем heartbeat в отдельном потоке
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        # Обновляем шаблоны при запуске
        self.update_nuclei_templates()
        
        # Основной цикл работы
        while self.running:
            try:
                # Здесь можно добавить логику получения задач с сервера
                # Пока просто ждём
                time.sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки")
                self.stop()
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(5)
    
    def execute_single_task(self, task_id, targets, templates):
        """Выполнение одной задачи сканирования"""
        try:
            # Запускаем heartbeat
            heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
            heartbeat_thread.start()
            
            # Выполняем сканирование
            results = self.run_nuclei_scan(targets, templates, task_id)
            
            logger.info(f"Задача {task_id} выполнена. Результатов: {results}")
            
        except Exception as e:
            logger.error(f"Ошибка выполнения задачи {task_id}: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Остановка воркера"""
        logger.info("Остановка воркера...")
        self.running = False
    
    def self_diagnostics(self):
        """Самодиагностика воркера"""
        logger.info("Запуск самодиагностики...")
        
        # Проверяем доступность Nuclei
        try:
            result = subprocess.run([self.nuclei_path, '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"Nuclei доступен: {result.stdout.strip()}")
            else:
                logger.error(f"Проблема с Nuclei: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Nuclei недоступен: {e}")
            return False
        
        # Проверяем доступность сервера
        try:
            response = requests.get(f"{self.server_url}/", timeout=10)
            if response.status_code == 200:
                logger.info("Центральный сервер доступен")
            else:
                logger.warning(f"Сервер вернул код: {response.status_code}")
        except Exception as e:
            logger.error(f"Центральный сервер недоступен: {e}")
            return False
        
        # Проверяем дисковое пространство
        try:
            statvfs = os.statvfs('/')
            free_space = statvfs.f_bavail * statvfs.f_frsize / (1024**3)  # GB
            if free_space < 1:
                logger.warning(f"Мало свободного места: {free_space:.2f} GB")
            else:
                logger.info(f"Свободное место: {free_space:.2f} GB")
        except Exception as e:
            logger.error(f"Ошибка проверки дискового пространства: {e}")
        
        logger.info("Самодиагностика завершена")
        return True

def signal_handler(signum, frame):
    """Обработчик сигналов"""
    logger.info(f"Получен сигнал {signum}")
    sys.exit(0)

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Nuclei Scanner Worker')
    
    parser.add_argument('--server-url', required=True,
                       help='URL центрального сервера')
    parser.add_argument('--server-id', type=int,
                       help='ID данного сервера')
    parser.add_argument('--task-id', type=int,
                       help='ID задачи для выполнения')
    parser.add_argument('--targets',
                       help='JSON строка с целевыми IP адресами')
    parser.add_argument('--templates',
                       help='JSON строка с ID шаблонов')
    parser.add_argument('--daemon', action='store_true',
                       help='Запуск в режиме демона')
    parser.add_argument('--diagnostics', action='store_true',
                       help='Выполнить самодиагностику')
    parser.add_argument('--update-templates', action='store_true',
                       help='Обновить шаблоны Nuclei')
    
    args = parser.parse_args()
    
    # Настройка обработчика сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Создаём экземпляр воркера
    worker = NucleiWorker(args.server_url, args.server_id)
    
    try:
        if args.diagnostics:
            # Выполняем самодиагностику
            success = worker.self_diagnostics()
            sys.exit(0 if success else 1)
        
        elif args.update_templates:
            # Обновляем шаблоны
            worker.update_nuclei_templates()
            sys.exit(0)
        
        elif args.daemon:
            # Запускаем в режиме демона
            worker.start_daemon_mode()
        
        elif args.task_id and args.targets:
            # Выполняем конкретную задачу
            targets = json.loads(args.targets)
            templates = json.loads(args.templates) if args.templates else []
            
            worker.execute_single_task(args.task_id, targets, templates)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Прерывание работы пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        worker.stop()

if __name__ == '__main__':
    main()