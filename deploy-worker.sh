#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт деплоя воркера Nuclei Scanner
# Использование: ./deploy-worker.sh [ADMIN_SERVER_URL]

set -e

echo "🔧 Развёртывание Nuclei Scanner - Воркер (исправленная версия)"
echo "=============================================================="

# Переменные конфигурации
WORKER_DIR="/opt/nuclei-worker"
WORKER_USER="nuclei"
NUCLEI_VERSION="v3.1.4"  # Обновленная версия
TEMPLATES_DIR="/opt/nuclei-templates"

# URL администраторского сервера (можно передать как аргумент)
ADMIN_SERVER_URL="${1:-http://192.168.1.100:5000}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода сообщений
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Запустите скрипт с правами root"
    exit 1
fi

# Определение операционной системы и архитектуры
if [ -f /etc/debian_version ]; then
    OS="debian"
    print_status "Обнаружена Debian/Ubuntu система"
elif [ -f /etc/redhat-release ]; then
    OS="redhat"
    print_status "Обнаружена RedHat/CentOS система"
else
    print_warning "Неизвестная операционная система. Продолжаем с настройками по умолчанию..."
    OS="unknown"
fi

# Определение архитектуры
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        NUCLEI_ARCH="linux_amd64"
        ;;
    aarch64|arm64)
        NUCLEI_ARCH="linux_arm64"
        ;;
    *)
        print_error "Неподдерживаемая архитектура: $ARCH"
        exit 1
        ;;
esac

print_status "Архитектура: $ARCH -> $NUCLEI_ARCH"

# Функция установки пакетов для Debian/Ubuntu
install_packages_debian() {
    print_status "Обновление списка пакетов..."
    apt-get update -qq

    print_status "Установка необходимых пакетов..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        wget \
        unzip \
        git \
        supervisor \
        openssh-server \
        cron \
        logrotate \
        htop \
        nmap \
        net-tools
}

# Функция установки пакетов для RedHat/CentOS
install_packages_redhat() {
    print_status "Обновление списка пакетов..."
    yum update -y

    print_status "Установка EPEL репозитория..."
    yum install -y epel-release

    print_status "Установка необходимых пакетов..."
    yum install -y \
        python3 \
        python3-pip \
        curl \
        wget \
        unzip \
        git \
        supervisor \
        openssh-server \
        cronie \
        logrotate \
        htop \
        nmap \
        net-tools
}

# Создание пользователя воркера
create_worker_user() {
    print_status "Создание пользователя воркера..."
    
    if ! id "$WORKER_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash "$WORKER_USER"
        print_success "Пользователь $WORKER_USER создан"
    else
        print_warning "Пользователь $WORKER_USER уже существует"
    fi
}

# Создание рабочих директорий
setup_directories() {
    print_status "Создание рабочих директорий..."
    
    # Удаляем старые директории если есть проблемы
    rm -rf "$WORKER_DIR" "$TEMPLATES_DIR" 2>/dev/null || true
    
    # Создаём директории
    mkdir -p "$WORKER_DIR"
    mkdir -p "$WORKER_DIR/logs"
    mkdir -p "$WORKER_DIR/results"
    mkdir -p "$TEMPLATES_DIR"
    mkdir -p "/home/$WORKER_USER/.nuclei"
    
    # Устанавливаем права
    chown -R "$WORKER_USER:$WORKER_USER" "$WORKER_DIR"
    chown -R "$WORKER_USER:$WORKER_USER" "$TEMPLATES_DIR"
    chown -R "$WORKER_USER:$WORKER_USER" "/home/$WORKER_USER/.nuclei"
    
    print_success "Рабочие директории созданы"
}

# Установка Nuclei
install_nuclei() {
    print_status "Установка Nuclei $NUCLEI_VERSION..."
    
    NUCLEI_URL="https://github.com/projectdiscovery/nuclei/releases/download/$NUCLEI_VERSION/nuclei_${NUCLEI_VERSION#v}_${NUCLEI_ARCH}.zip"
    TEMP_DIR=$(mktemp -d)
    
    # Скачивание Nuclei
    cd "$TEMP_DIR"
    print_status "Скачивание с $NUCLEI_URL"
    curl -L -o nuclei.zip "$NUCLEI_URL" || {
        print_error "Не удалось скачать Nuclei"
        exit 1
    }
    
    # Распаковка и установка
    unzip nuclei.zip
    chmod +x nuclei
    mv nuclei /usr/local/bin/
    
    # Проверка установки
    if nuclei -version >/dev/null 2>&1; then
        print_success "Nuclei успешно установлен: $(nuclei -version 2>&1 | head -1)"
    else
        print_error "Ошибка установки Nuclei"
        exit 1
    fi
    
    # Очистка временных файлов
    rm -rf "$TEMP_DIR"
}

# Установка шаблонов Nuclei
install_nuclei_templates() {
    print_status "Установка шаблонов Nuclei..."
    
    # Сначала обновляем шаблоны через Nuclei (они сохраняются в ~/.nuclei)
    print_status "Обновление встроенных шаблонов..."
    sudo -u "$WORKER_USER" nuclei -update-templates -silent || {
        print_warning "Не удалось обновить встроенные шаблоны"
    }
    
    # Теперь клонируем репозиторий шаблонов в отдельную директорию
    print_status "Клонирование репозитория шаблонов..."
    
    # Переходим в безопасную директорию перед клонированием
    cd /tmp
    
    # Удаляем существующую директорию если есть
    rm -rf "$TEMPLATES_DIR" 2>/dev/null || true
    
    # Клонируем репозиторий как root, потом меняем права
    if git clone https://github.com/projectdiscovery/nuclei-templates.git "$TEMPLATES_DIR"; then
        # Меняем владельца на пользователя воркера
        chown -R "$WORKER_USER:$WORKER_USER" "$TEMPLATES_DIR"
        print_success "Репозиторий шаблонов успешно клонирован"
    else
        print_warning "Не удалось клонировать репозиторий шаблонов"
        print_status "Создаём пустую директорию шаблонов..."
        mkdir -p "$TEMPLATES_DIR"
        chown -R "$WORKER_USER:$WORKER_USER" "$TEMPLATES_DIR"
    fi
    
    print_success "Шаблоны Nuclei установлены"
}

# Установка Python зависимостей
install_python_deps() {
    print_status "Установка Python зависимостей..."
    
    # Создание виртуального окружения
    sudo -u "$WORKER_USER" python3 -m venv "$WORKER_DIR/venv"
    
    # Создание requirements.txt
    cat > "$WORKER_DIR/requirements.txt" << 'EOF'
requests==2.31.0
paramiko==3.3.1
python-dotenv==1.0.0
psutil==5.9.5
schedule==1.2.0
ipaddress==1.0.23
EOF

    # Установка зависимостей
    sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install -r "$WORKER_DIR/requirements.txt"
    
    print_success "Python зависимости установлены"
}

# Развёртывание скрипта воркера
deploy_worker_script() {
    print_status "Развёртывание скрипта воркера..."
    
    # Создаём полный рабочий скрипт воркера
    cat > "$WORKER_DIR/worker.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
        logging.FileHandler('/opt/nuclei-worker/logs/worker.log'),
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
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
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
            
            time.sleep(30)
    
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
                logger.error(f"Ошибка отправки уязвимости: {response.status_code}")
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
            if output_line.strip().startswith('{') and output_line.strip().endswith('}'):
                data = json.loads(output_line.strip())
                
                vulnerability = {
                    'ip_address': data.get('host', '').replace('http://', '').replace('https://', '').split(':')[0],
                    'template_id': data.get('template-id', ''),
                    'matcher_name': data.get('matcher-name', ''),
                    'severity_level': data.get('info', {}).get('severity', 'unknown'),
                    'url': data.get('matched-at', ''),
                    'request_data': json.dumps(data.get('request', {})),
                    'response_data': json.dumps(data.get('response', {})),
                    'vuln_metadata': {
                        'template_info': data.get('info', {}),
                        'curl_command': data.get('curl-command', ''),
                        'raw_data': data
                    }
                }
                
                return vulnerability
                
        except json.JSONDecodeError:
            logger.debug(f"Не удалось распарсить как JSON: {output_line}")
        except Exception as e:
            logger.error(f"Ошибка парсинга вывода Nuclei: {e}")
        
        return None
    
    def run_nuclei_scan(self, targets, templates, task_id):
        """Выполнение сканирования Nuclei"""
        logger.info(f"Запуск сканирования задачи {task_id}: {len(targets)} целей")
        
        targets_file = f'/tmp/nuclei-targets-{task_id}.txt'
        with open(targets_file, 'w') as f:
            for target in targets:
                f.write(f"{target}\n")
        
        try:
            cmd = [
                self.nuclei_path,
                '-l', targets_file,
                '-json',
                '-silent',
                '-timeout', '10',
                '-retries', '1',
                '-rate-limit', '100'
            ]
            
            if templates and templates != ['']:
                for template in templates:
                    if template:
                        cmd.extend(['-t', template])
            
            logger.info(f"Команда Nuclei: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            vulnerabilities_found = 0
            
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not self.running:
                        process.terminate()
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    vulnerability = self.parse_nuclei_output(line)
                    if vulnerability:
                        vulnerability['task_id'] = task_id
                        
                        if self.submit_vulnerability(vulnerability):
                            vulnerabilities_found += 1
                        
                        logger.info(f"Найдена уязвимость: {vulnerability['template_id']} -> {vulnerability['ip_address']}")
            
            process.wait()
            
            logger.info(f"Сканирование задачи {task_id} завершено. Найдено уязвимостей: {vulnerabilities_found}")
            
            self.notify_task_complete(task_id)
            
            return vulnerabilities_found
            
        except Exception as e:
            logger.error(f"Ошибка выполнения сканирования: {e}")
            return 0
        finally:
            try:
                os.remove(targets_file)
            except:
                pass
    
    def start_daemon_mode(self):
        """Запуск воркера в режиме демона"""
        logger.info("Запуск воркера в режиме демона")
        
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        self.update_nuclei_templates()
        
        while self.running:
            try:
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
            heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
            heartbeat_thread.start()
            
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
        
        try:
            response = requests.get(f"{self.server_url}/", timeout=10)
            if response.status_code == 200:
                logger.info("Центральный сервер доступен")
            else:
                logger.warning(f"Сервер вернул код: {response.status_code}")
        except Exception as e:
            logger.error(f"Центральный сервер недоступен: {e}")
            return False
        
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
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    worker = NucleiWorker(args.server_url, args.server_id)
    
    try:
        if args.diagnostics:
            success = worker.self_diagnostics()
            sys.exit(0 if success else 1)
        
        elif args.update_templates:
            worker.update_nuclei_templates()
            sys.exit(0)
        
        elif args.daemon:
            worker.start_daemon_mode()
        
        elif args.task_id and args.targets:
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
EOF
    
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/worker.py"
    chmod +x "$WORKER_DIR/worker.py"
    
    print_success "Скрипт воркера развёрнут"
}

# Создание конфигурации
setup_config() {
    print_status "Создание конфигурации воркера..."
    
    cat > "$WORKER_DIR/.env" << EOF
# Конфигурация Nuclei Worker
ADMIN_SERVER_URL=$ADMIN_SERVER_URL
WORKER_ID=1
NUCLEI_PATH=/usr/local/bin/nuclei
TEMPLATES_PATH=$TEMPLATES_DIR
RESULTS_PATH=$WORKER_DIR/results

# Логирование
LOG_LEVEL=INFO
LOG_FILE=$WORKER_DIR/logs/worker.log

# Производительность
MAX_CONCURRENT_SCANS=5
SCAN_TIMEOUT=3600
HEARTBEAT_INTERVAL=30

# Самодиагностика
SELF_CHECK_INTERVAL=300
AUTO_RESTART_ON_ERROR=true
EOF

    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/.env"
    chmod 600 "$WORKER_DIR/.env"
    
    print_success "Конфигурация создана"
}

# Настройка SSH
setup_ssh() {
    print_status "Настройка SSH доступа..."
    
    SSH_DIR="/home/$WORKER_USER/.ssh"
    sudo -u "$WORKER_USER" mkdir -p "$SSH_DIR"
    sudo -u "$WORKER_USER" chmod 700 "$SSH_DIR"
    
    sudo -u "$WORKER_USER" touch "$SSH_DIR/authorized_keys"
    sudo -u "$WORKER_USER" chmod 600 "$SSH_DIR/authorized_keys"
    
    if ! grep -q "^AllowUsers.*$WORKER_USER" /etc/ssh/sshd_config; then
        echo "AllowUsers root $WORKER_USER" >> /etc/ssh/sshd_config
        systemctl restart sshd || systemctl restart ssh
    fi
    
    print_success "SSH настроен"
    print_warning "Добавьте публичный ключ администратора в $SSH_DIR/authorized_keys"
}

# Настройка Supervisor
setup_supervisor() {
    print_status "Настройка Supervisor..."
    
    cat > /etc/supervisor/conf.d/nuclei-worker.conf << EOF
[program:nuclei-worker]
command=$WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --daemon --server-url $ADMIN_SERVER_URL
directory=$WORKER_DIR
user=$WORKER_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$WORKER_DIR/logs/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$WORKER_DIR/venv/bin"
EOF

    systemctl restart supervisor
    systemctl enable supervisor
    
    supervisorctl reread || true
    supervisorctl update || true
    
    print_success "Supervisor настроен"
}

# Создание скрипта диагностики
create_diagnostic_script() {
    print_status "Создание скрипта диагностики..."
    
    cat > "$WORKER_DIR/diagnostics.sh" << 'EOF'
#!/bin/bash
# Скрипт диагностики воркера

WORKER_DIR="/opt/nuclei-worker"

echo "🔍 Диагностика Nuclei Worker"
echo "============================"

echo "Nuclei версия:"
nuclei -version 2>/dev/null || echo "❌ Nuclei недоступен"

echo -e "\nPython версия:"
"$WORKER_DIR/venv/bin/python" --version 2>/dev/null || echo "❌ Python недоступен"

echo -e "\nДисковое пространство:"
df -h "$WORKER_DIR" | tail -1

echo -e "\nИспользование памяти:"
free -h

echo -e "\nПроцессы воркера:"
ps aux | grep -E "(nuclei|worker)" | grep -v grep

echo -e "\nПоследние записи в логах:"
if [ -f "$WORKER_DIR/logs/worker.log" ]; then
    tail -5 "$WORKER_DIR/logs/worker.log"
else
    echo "Логи не найдены"
fi

echo -e "\nПроверка связи с центральным сервером:"
if [ -f "$WORKER_DIR/.env" ]; then
    ADMIN_URL=$(grep ADMIN_SERVER_URL "$WORKER_DIR/.env" | cut -d'=' -f2)
    if curl -s --connect-timeout 5 "$ADMIN_URL" >/dev/null; then
        echo "✅ Связь с $ADMIN_URL установлена"
    else
        echo "❌ Нет связи с $ADMIN_URL"
    fi
else
    echo "❌ Конфигурация не найдена"
fi

echo -e "\nШаблоны Nuclei:"
TEMPLATE_COUNT=$(find /opt/nuclei-templates -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l)
echo "Найдено шаблонов: $TEMPLATE_COUNT"

echo -e "\n✅ Диагностика завершена"
EOF

    chmod +x "$WORKER_DIR/diagnostics.sh"
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/diagnostics.sh"
    
    print_success "Скрипт диагностики создан"
}

# Создание скрипта обновления
create_update_script() {
    print_status "Создание скрипта обновления..."
    
    cat > "$WORKER_DIR/update.sh" << 'EOF'
#!/bin/bash
# Скрипт обновления воркера

WORKER_DIR="/opt/nuclei-worker"
WORKER_USER="nuclei"

echo "🔄 Обновление Nuclei Worker..."

# Остановка сервиса
echo "Остановка сервиса..."
supervisorctl stop nuclei-worker 2>/dev/null || true

# Обновление шаблонов
echo "Обновление шаблонов Nuclei..."
sudo -u "$WORKER_USER" nuclei -update-templates -silent

# Обновление зависимостей Python
echo "Обновление Python зависимостей..."
sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install --upgrade -r "$WORKER_DIR/requirements.txt"

# Обновление репозитория шаблонов
if [ -d "/opt/nuclei-templates/.git" ]; then
    echo "Обновление репозитория шаблонов..."
    cd /opt/nuclei-templates
    sudo -u "$WORKER_USER" git pull
fi

# Запуск сервиса
echo "Запуск сервиса..."
supervisorctl start nuclei-worker 2>/dev/null || true

echo "✅ Обновление завершено"
EOF

    chmod +x "$WORKER_DIR/update.sh"
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/update.sh"
    
    print_success "Скрипт обновления создан"
}

# Настройка cron задач
setup_cron() {
    print_status "Настройка cron задач..."
    
    cat > /tmp/nuclei-worker-cron << EOF
# Обновление шаблонов каждый день в 3:00
0 3 * * * $WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --update-templates >/dev/null 2>&1

# Самодиагностика каждые 30 минут
*/30 * * * * $WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --diagnostics >/dev/null 2>&1

# Очистка старых результатов раз в неделю
0 2 * * 0 find $WORKER_DIR/results -name "*.json" -mtime +7 -delete >/dev/null 2>&1
EOF

    sudo -u "$WORKER_USER" crontab /tmp/nuclei-worker-cron
    rm /tmp/nuclei-worker-cron
    
    print_success "Cron задачи настроены"
}

# Настройка логротации
setup_logrotate() {
    print_status "Настройка ротации логов..."
    
    cat > /etc/logrotate.d/nuclei-worker << EOF
$WORKER_DIR/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $WORKER_USER $WORKER_USER
    postrotate
        supervisorctl restart nuclei-worker 2>/dev/null || true
    endscript
}
EOF

    print_success "Логротация настроена"
}

# Настройка firewall
setup_firewall() {
    print_status "Настройка firewall..."
    
    if command -v ufw >/dev/null 2>&1; then
        ufw allow ssh
        ufw --force enable
        print_success "UFW firewall настроен"
    elif command -v firewall-cmd >/dev/null 2>&1; then
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --reload
        print_success "Firewalld настроен"
    else
        print_warning "Firewall не обнаружен. Настройте вручную порт 22"
    fi
}

# Первоначальная проверка системы
initial_check() {
    print_status "Проверка системных требований..."
    
    if ! curl -s --connect-timeout 5 google.com >/dev/null; then
        print_warning "Нет подключения к интернету"
    fi
    
    DISK_SPACE=$(df / | tail -1 | awk '{print $4}')
    if [ "$DISK_SPACE" -lt 1000000 ]; then
        print_warning "Мало свободного места на диске"
    fi
    
    TOTAL_RAM=$(free | grep Mem | awk '{print $2}')
    if [ "$TOTAL_RAM" -lt 1000000 ]; then
        print_warning "Мало оперативной памяти"
    fi
    
    print_success "Системные требования проверены"
}

# Проверка сервисов
check_services() {
    print_status "Проверка состояния сервисов..."
    
    echo "SSH: $(systemctl is-active sshd || systemctl is-active ssh)"
    echo "Supervisor: $(systemctl is-active supervisor)"
    echo "Cron: $(systemctl is-active cron || systemctl is-active crond)"
    
    if supervisorctl status nuclei-worker >/dev/null 2>&1; then
        echo "Nuclei Worker: $(supervisorctl status nuclei-worker | awk '{print $2}')"
    else
        echo "Nuclei Worker: не настроен"
    fi
    
    print_success "Проверка сервисов завершена"
}

# Тестирование воркера
test_worker() {
    print_status "Тестирование воркера..."
    
    if [ -f "$WORKER_DIR/worker.py" ]; then
        sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/python" "$WORKER_DIR/worker.py" --diagnostics || true
    fi
    
    if curl -s --connect-timeout 10 "$ADMIN_SERVER_URL" >/dev/null; then
        print_success "Связь с админ сервером установлена"
    else
        print_warning "Нет связи с админ сервером: $ADMIN_SERVER_URL"
    fi
    
    print_success "Тестирование завершено"
}

# Вывод финальной информации
print_final_info() {
    echo ""
    print_success "Установка Nuclei Worker завершена!"
    echo "====================================="
    echo ""
    echo "📋 Информация о развёртывании:"
    echo "   • Директория воркера: $WORKER_DIR"
    echo "   • Пользователь: $WORKER_USER"
    echo "   • Nuclei версия: $NUCLEI_VERSION"
    echo "   • Админ сервер: $ADMIN_SERVER_URL"
    echo ""
    echo "🔧 Управление сервисом:"
    echo "   • Статус: supervisorctl status nuclei-worker"
    echo "   • Запуск: supervisorctl start nuclei-worker"
    echo "   • Остановка: supervisorctl stop nuclei-worker"
    echo "   • Перезапуск: supervisorctl restart nuclei-worker"
    echo ""
    echo "📊 Мониторинг:"
    echo "   • Логи: tail -f $WORKER_DIR/logs/supervisor.log"
    echo "   • Диагностика: $WORKER_DIR/diagnostics.sh"
    echo ""
    echo "🔄 Обслуживание:"
    echo "   • Обновление: $WORKER_DIR/update.sh"
    echo "   • Обновление шаблонов: nuclei -update-templates"
    echo ""
    echo "🔑 SSH настройка:"
    echo "   • Добавьте публичный ключ админа в:"
    echo "     /home/$WORKER_USER/.ssh/authorized_keys"
    echo ""
    echo "📈 Следующие шаги:"
    echo "   1. Добавьте SSH ключ администратора"
    echo "   2. Добавьте воркер в админ панели"
    echo "   3. Запустите тестовое сканирование"
    echo ""
    
    echo "💻 Информация о системе:"
    echo "   • Hostname: $(hostname)"
    echo "   • IP адрес: $(hostname -I | awk '{print $1}')"
    echo "   • Архитектура: $ARCH"
    echo "   • ОС: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2 || echo 'Unknown')"
    echo ""
    
    # Показываем публичный ключ центрального сервера для копирования
    echo "🔑 Для подключения к воркеру добавьте этот ключ в authorized_keys:"
    echo "   Скопируйте публичный ключ с центрального сервера:"
    echo "   sudo cat /home/nuclei/.ssh/id_rsa.pub"
    echo ""
    echo "   И добавьте его на воркере:"
    echo "   echo 'ПУБЛИЧНЫЙ_КЛЮЧ' >> /home/$WORKER_USER/.ssh/authorized_keys"
    echo ""
}

# Основная функция
main() {
    print_status "Начало установки Nuclei Worker..."
    
    initial_check
    
    if [ "$OS" = "debian" ]; then
        install_packages_debian
    elif [ "$OS" = "redhat" ]; then
        install_packages_redhat
    else
        print_error "Неподдерживаемая операционная система"
        exit 1
    fi
    
    create_worker_user
    setup_directories
    install_nuclei
    install_nuclei_templates
    install_python_deps
    deploy_worker_script
    setup_config
    setup_ssh
    setup_supervisor
    create_diagnostic_script
    create_update_script
    setup_cron
    setup_logrotate
    setup_firewall
    check_services
    test_worker
    print_final_info
}

# Обработка ошибок
trap 'print_error "Установка прервана из-за ошибки на строке $LINENO"' ERR

# Проверка аргументов
if [ $# -gt 1 ]; then
    print_error "Использование: $0 [ADMIN_SERVER_URL]"
    exit 1
fi

# Запуск основной функции
main "$@"