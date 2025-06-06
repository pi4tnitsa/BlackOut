#!/bin/bash
# -*- coding: utf-8 -*-
# Исправленный скрипт деплоя центрального сервера Nuclei Scanner

set -e

echo "🚀 Развёртывание Nuclei Scanner - Центральный сервер (исправленная версия)"
echo "========================================================================="

# Переменные конфигурации
APP_DIR="/opt/nuclei-admin"
APP_USER="nuclei"
DB_NAME="nuclei_scanner"
DB_USER="nuclei_user"
PYTHON_VERSION="3.9"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
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

# Определение операционной системы
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

# Функция установки пакетов для Debian/Ubuntu
install_packages_debian() {
    print_status "Обновление списка пакетов..."
    apt-get update -qq

    print_status "Установка необходимых пакетов..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        postgresql \
        postgresql-contrib \
        nginx \
        supervisor \
        git \
        curl \
        wget \
        unzip \
        build-essential \
        libpq-dev \
        redis-server \
        golang-go \
        openssl
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
        python3-devel \
        postgresql-server \
        postgresql-contrib \
        nginx \
        supervisor \
        git \
        curl \
        wget \
        unzip \
        gcc \
        gcc-c++ \
        make \
        postgresql-devel \
        redis \
        golang \
        openssl
}

# Создание пользователя приложения
create_app_user() {
    print_status "Создание пользователя приложения..."
    
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash "$APP_USER"
        print_success "Пользователь $APP_USER создан"
    else
        print_warning "Пользователь $APP_USER уже существует"
    fi
}

# Настройка PostgreSQL
setup_postgresql() {
    print_status "Настройка PostgreSQL..."
    
    # Инициализация базы данных (для RedHat)
    if [ "$OS" = "redhat" ]; then
        postgresql-setup initdb || true
    fi
    
    # Запуск службы PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Создание базы данных и пользователя
    print_status "Создание базы данных и пользователя..."
    
    # Генерация случайного пароля
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Создание пользователя и баз данных
    sudo -u postgres psql << EOF
-- Удаляем пользователя если существует
DROP USER IF EXISTS $DB_USER;

-- Создаём нового пользователя
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER USER $DB_USER CREATEDB;

-- Удаляем базы если существуют
DROP DATABASE IF EXISTS nuclei_scanner_belarus;
DROP DATABASE IF EXISTS nuclei_scanner_russia;
DROP DATABASE IF EXISTS nuclei_scanner_kazakhstan;

-- Создаём новые базы данных
CREATE DATABASE nuclei_scanner_belarus OWNER $DB_USER;
CREATE DATABASE nuclei_scanner_russia OWNER $DB_USER;
CREATE DATABASE nuclei_scanner_kazakhstan OWNER $DB_USER;

-- Даём права
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_belarus TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_russia TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_kazakhstan TO $DB_USER;
\q
EOF

    # Сохранение данных доступа
    cat > /etc/nuclei-admin.env << EOF
DB_BELARUS=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_belarus
DB_RUSSIA=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_russia
DB_KAZAKHSTAN=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_kazakhstan
CURRENT_DB=belarus
DB_PASSWORD=$DB_PASSWORD
EOF
    
    chmod 600 /etc/nuclei-admin.env
    
    print_success "PostgreSQL настроен. Пароль сохранён в /etc/nuclei-admin.env"
}

# Создание директории приложения
setup_app_directory() {
    print_status "Создание директории приложения..."
    
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR/templates"
    mkdir -p "$APP_DIR/static"
    mkdir -p "$APP_DIR/static/css"
    mkdir -p "$APP_DIR/static/js"
    mkdir -p "$APP_DIR/static/img"
    mkdir -p "$APP_DIR/logs"
    
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    
    print_success "Директория приложения создана: $APP_DIR"
}

# Установка Nuclei
install_nuclei() {
    print_status "Установка Nuclei..."
    
    # Определяем архитектуру
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
    
    # Устанавливаем Nuclei через бинарный релиз
    print_status "Скачивание Nuclei..."
    NUCLEI_VERSION="v3.1.4"
    NUCLEI_URL="https://github.com/projectdiscovery/nuclei/releases/download/${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION#v}_${NUCLEI_ARCH}.zip"
    
    cd /tmp
    curl -L -o nuclei.zip "$NUCLEI_URL"
    
    if [ ! -f nuclei.zip ]; then
        print_error "Не удалось скачать Nuclei"
        exit 1
    fi
    
    # Распаковка и установка
    unzip -o nuclei.zip
    chmod +x nuclei
    mv nuclei /usr/local/bin/
    rm -f nuclei.zip README.md LICENSE.md
    
    # Проверка установки
    if nuclei -version >/dev/null 2>&1; then
        print_success "Nuclei установлен успешно: $(nuclei -version)"
    else
        print_error "Ошибка установки Nuclei"
        exit 1
    fi
    
    # Обновляем шаблоны
    print_status "Обновление шаблонов Nuclei..."
    sudo -u "$APP_USER" nuclei -update-templates -silent || true
}

# Установка Python-зависимостей
install_python_deps() {
    print_status "Установка Python зависимостей..."
    
    # Создание виртуального окружения
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
    
    # Создание requirements.txt
    cat > "$APP_DIR/requirements.txt" << 'EOF'
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Werkzeug==2.3.7
psycopg2-binary==2.9.7
SQLAlchemy==2.0.20
paramiko==3.3.1
requests==2.31.0
ipaddress==1.0.23
netaddr==0.8.0
gunicorn==21.2.0
gevent==23.7.0
celery==5.3.1
redis==4.6.0
python-dotenv==1.0.0
schedule==1.2.0
psutil==5.9.5
click==8.1.7
colorama==0.4.6
structlog==23.1.0
marshmallow==3.20.1
orjson==3.9.5
cryptography==41.0.4
python-dateutil==2.8.2
pytz==2023.3
EOF

    # Установка зависимостей
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    
    print_success "Python зависимости установлены"
}

# Создание файлов приложения
create_app_files() {
    print_status "Создание файлов приложения..."
    
    # Создаём app.py
    cat > "$APP_DIR/app.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import hashlib
import datetime
import threading
import subprocess
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import paramiko
import requests
import ipaddress
from sqlalchemy import text
import time
import sys
import signal

# Загружаем переменные окружения из .env файла
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nuclei-scanner-secret-key-2025')

# Конфигурация базы данных
DATABASE_URLS = {
    'belarus': os.environ.get('DB_BELARUS', 'postgresql://nuclei_user:password@localhost:5432/nuclei_scanner_belarus'),
    'russia': os.environ.get('DB_RUSSIA', 'postgresql://nuclei_user:password@localhost:5432/nuclei_scanner_russia'),
    'kazakhstan': os.environ.get('DB_KAZAKHSTAN', 'postgresql://nuclei_user:password@localhost:5432/nuclei_scanner_kazakhstan')
}

# Текущая активная база
current_db = os.environ.get('CURRENT_DB', 'belarus')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URLS[current_db]
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'connect_args': {
        'connect_timeout': 10,
        'application_name': 'nuclei_scanner'
    }
}

# Инициализация базы данных
db = SQLAlchemy()

def create_app():
    """Фабрика приложений Flask"""
    db.init_app(app)
    return app

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Модели данных
class Server(db.Model):
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    ssh_port = db.Column(db.Integer, default=22)
    status = db.Column(db.String(50), default='offline')
    capabilities = db.Column(db.JSON)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ScanTask(db.Model):
    __tablename__ = 'scan_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    target_ips = db.Column(db.JSON)
    template_ids = db.Column(db.JSON)
    server_ids = db.Column(db.JSON)
    priority = db.Column(db.Integer, default=1)
    status = db.Column(db.String(50), default='pending')
    schedule_time = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Vulnerability(db.Model):
    __tablename__ = 'vulnerabilities'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    template_id = db.Column(db.String(255))
    matcher_name = db.Column(db.String(255))
    severity_level = db.Column(db.String(20))
    url = db.Column(db.Text)
    request_data = db.Column(db.Text)
    response_data = db.Column(db.Text)
    vuln_metadata = db.Column(db.JSON)
    source_server_id = db.Column(db.Integer, db.ForeignKey('servers.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('scan_tasks.id'))
    discovered_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ScanTemplate(db.Model):
    __tablename__ = 'scan_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    severity = db.Column(db.String(20))
    tags = db.Column(db.JSON)
    content = db.Column(db.Text)
    checksum = db.Column(db.String(64))
    version = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Вспомогательные функции
def send_telegram_message(message):
    """Отправка уведомления в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return False

def parse_target_ips(target_string):
    """Парсинг целевых IP адресов из строки"""
    ips = []
    for target in target_string.replace(',', '\n').split('\n'):
        target = target.strip()
        if not target:
            continue
            
        try:
            # Проверяем CIDR
            if '/' in target:
                network = ipaddress.ip_network(target, strict=False)
                ips.extend([str(ip) for ip in network.hosts()])
            # Проверяем диапазон
            elif '-' in target and target.count('.') == 6:
                start_ip, end_ip = target.split('-')
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())
                
                if type(start) != type(end):
                    continue
                current = start
                while int(current) <= int(end):
                    ips.append(str(current))
                    current = ipaddress.ip_address(int(current) + 1)
            else:
                # Одиночный IP
                ip = ipaddress.ip_address(target)
                ips.append(str(ip))
        except ValueError:
            continue
    
    return list(set(ips))

def execute_ssh_command(server, command):
    """Выполнение команды на удалённом сервере через SSH"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=server.ip_address,
            port=server.ssh_port,
            username=os.environ.get('SSH_USER', 'root'),
            key_filename=os.path.expanduser(os.environ.get('SSH_KEY_PATH', '~/.ssh/id_rsa')),
            timeout=30
        )
        
        stdin, stdout, stderr = ssh.exec_command(command)
        result = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        
        return {'success': True, 'output': result, 'error': error}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def signal_handler(signum, frame):
    """Обработчик сигналов"""
    print(f"[INFO] Получен сигнал {signum}, завершение работы...")
    sys.exit(0)

# Аутентификация
@app.before_request
def require_login():
    """Проверка аутентификации пользователя"""
    if request.endpoint and request.endpoint not in ['login', 'static'] and not session.get('logged_in'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admin_user = os.environ.get('ADMIN_USER', 'admin')
        admin_pass = os.environ.get('ADMIN_PASS', 'admin123')
        
        if username == admin_user and password == admin_pass:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    return redirect(url_for('login'))

# Основные маршруты
@app.route('/')
def dashboard():
    """Главная панель управления"""
    try:
        vuln_stats = db.session.execute(text("""
            SELECT severity_level, COUNT(*) as count 
            FROM vulnerabilities 
            GROUP BY severity_level
        """)).fetchall()
        
        server_stats = db.session.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM servers 
            GROUP BY status
        """)).fetchall()
        
        active_tasks = ScanTask.query.filter(
            ScanTask.status.in_(['pending', 'running'])
        ).count()
        
        recent_vulns = Vulnerability.query.order_by(
            Vulnerability.discovered_at.desc()
        ).limit(10).all()
        
        return render_template('dashboard.html', 
                             vuln_stats=vuln_stats,
                             server_stats=server_stats,
                             active_tasks=active_tasks,
                             recent_vulns=recent_vulns)
    except Exception as e:
        flash(f'Ошибка загрузки данных: {str(e)}')
        return render_template('dashboard.html', 
                             vuln_stats=[],
                             server_stats=[],
                             active_tasks=0,
                             recent_vulns=[])

@app.route('/servers')
def servers():
    """Управление серверами"""
    servers_list = Server.query.all()
    return render_template('servers.html', servers=servers_list)

@app.route('/servers/add', methods=['POST'])
def add_server():
    """Добавление нового сервера"""
    try:
        server = Server(
            hostname=request.form['hostname'],
            ip_address=request.form['ip_address'],
            ssh_port=int(request.form.get('ssh_port', 22))
        )
        db.session.add(server)
        db.session.commit()
        
        flash('Сервер успешно добавлен')
        send_telegram_message(f"🖥️ Добавлен новый сервер: {server.hostname} ({server.ip_address})")
        
    except Exception as e:
        flash(f'Ошибка добавления сервера: {e}')
    
    return redirect(url_for('servers'))

@app.route('/servers/<int:server_id>/delete', methods=['POST'])
def delete_server(server_id):
    """Удаление сервера"""
    try:
        server = Server.query.get_or_404(server_id)
        hostname = server.hostname
        db.session.delete(server)
        db.session.commit()
        
        flash('Сервер успешно удалён')
        send_telegram_message(f"🗑️ Удалён сервер: {hostname}")
        
    except Exception as e:
        flash(f'Ошибка удаления сервера: {e}')
    
    return redirect(url_for('servers'))

@app.route('/tasks')
def tasks():
    """Управление задачами сканирования"""
    tasks_list = ScanTask.query.order_by(ScanTask.created_at.desc()).all()
    servers_list = Server.query.filter_by(status='online').all()
    templates_list = ScanTemplate.query.all()
    
    return render_template('tasks.html', 
                         tasks=tasks_list,
                         servers=servers_list,
                         templates=templates_list)

@app.route('/tasks/create', methods=['POST'])
def create_task():
    """Создание новой задачи сканирования"""
    try:
        target_ips = parse_target_ips(request.form['targets'])
        
        if not target_ips:
            flash('Не удалось распарсить целевые IP адреса')
            return redirect(url_for('tasks'))
        
        task = ScanTask(
            name=request.form['name'],
            target_ips=target_ips,
            template_ids=request.form.getlist('templates'),
            server_ids=[int(x) for x in request.form.getlist('servers')],
            priority=int(request.form.get('priority', 1)),
            created_by=session.get('username', 'unknown')
        )
        
        if request.form.get('schedule_time'):
            task.schedule_time = datetime.datetime.strptime(
                request.form['schedule_time'], '%Y-%m-%dT%H:%M'
            )
        
        db.session.add(task)
        db.session.commit()
        
        flash(f'Задача "{task.name}" успешно создана')
        send_telegram_message(f"📋 Создана новая задача: {task.name} ({len(target_ips)} целей)")
        
    except Exception as e:
        flash(f'Ошибка создания задачи: {e}')
    
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:task_id>/start', methods=['POST'])
def start_task(task_id):
    """Запуск задачи сканирования"""
    try:
        task = ScanTask.query.get_or_404(task_id)
        
        if task.status != 'pending':
            flash('Задача уже выполняется или завершена')
            return redirect(url_for('tasks'))
        
        available_servers = Server.query.filter(
            Server.id.in_(task.server_ids),
            Server.status == 'online'
        ).all()
        
        if not available_servers:
            flash('Нет доступных серверов для выполнения задачи')
            return redirect(url_for('tasks'))
        
        ips_per_server = len(task.target_ips) // len(available_servers)
        
        for i, server in enumerate(available_servers):
            start_idx = i * ips_per_server
            end_idx = start_idx + ips_per_server if i < len(available_servers) - 1 else len(task.target_ips)
            server_ips = task.target_ips[start_idx:end_idx]
            
            command = f"""
            cd /opt/nuclei-worker && python3 worker.py \
            --task-id {task.id} \
            --targets '{json.dumps(server_ips)}' \
            --templates '{json.dumps(task.template_ids)}' \
            --server-url '{request.url_root}' &
            """
            
            result = execute_ssh_command(server, command)
            if not result['success']:
                flash(f'Ошибка запуска на сервере {server.hostname}: {result["error"]}')
        
        task.status = 'running'
        task.started_at = datetime.datetime.utcnow()
        db.session.commit()
        
        flash(f'Задача "{task.name}" запущена')
        send_telegram_message(f"🚀 Запущена задача: {task.name}")
        
    except Exception as e:
        flash(f'Ошибка запуска задачи: {e}')
    
    return redirect(url_for('tasks'))

@app.route('/vulnerabilities')
def vulnerabilities():
    """Просмотр найденных уязвимостей"""
    page = request.args.get('page', 1, type=int)
    severity = request.args.get('severity', '')
    
    query = Vulnerability.query
    if severity:
        query = query.filter_by(severity_level=severity)
    
    vulns = query.order_by(Vulnerability.discovered_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('vulnerabilities.html', vulnerabilities=vulns)

# API для воркеров
@app.route('/api/worker/heartbeat', methods=['POST'])
def worker_heartbeat():
    """API для отправки heartbeat от воркеров"""
    try:
        data = request.get_json()
        server_id = data.get('server_id')
        
        server = Server.query.get(server_id)
        if server:
            server.status = 'online'
            server.last_seen = datetime.datetime.utcnow()
            db.session.commit()
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/worker/submit_vulnerability', methods=['POST'])
def submit_vulnerability():
    """API для отправки найденных уязвимостей"""
    try:
        data = request.get_json()
        
        vuln = Vulnerability(
            ip_address=data['ip_address'],
            template_id=data['template_id'],
            matcher_name=data.get('matcher_name'),
            severity_level=data['severity_level'],
            url=data.get('url'),
            request_data=data.get('request_data'),
            response_data=data.get('response_data'),
            vuln_metadata=data.get('metadata', {}),
            source_server_id=data.get('source_server_id'),
            task_id=data.get('task_id')
        )
        
        db.session.add(vuln)
        db.session.commit()
        
        if data['severity_level'] in ['critical', 'high']:
            message = f"🚨 Найдена {data['severity_level']} уязвимость!\n"
            message += f"IP: {data['ip_address']}\n"
            message += f"Шаблон: {data['template_id']}\n"
            if data.get('url'):
                message += f"URL: {data['url']}"
            
            send_telegram_message(message)
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/worker/task_complete', methods=['POST'])
def task_complete():    
    """API для уведомления о завершении задачи"""
    try:
        data = request.get_json()
        task_id = data.get('task_id')
        
        task = ScanTask.query.get(task_id)
        if task:
            task.status = 'completed'
            task.completed_at = datetime.datetime.utcnow()
            db.session.commit()
            
            send_telegram_message(f"✅ Задача завершена: {task.name}")
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def init_database():
    """Инициализация базы данных с созданием таблиц"""
    try:
        print("[INFO] Проверка подключения к базе данных...")
        
        db.session.execute(text("SELECT 1"))
        print("[SUCCESS] Подключение к базе данных успешно")
        
        db.create_all()
        print("[SUCCESS] Таблицы базы данных созданы")
        
        if not Server.query.first():
            sample_server = Server(
                hostname="nuclei-worker-example",
                ip_address="127.0.0.1",
                ssh_port=22,
                status="offline"
            )
            db.session.add(sample_server)
            
            sample_template = ScanTemplate(
                template_id="http-missing-security-headers",
                name="HTTP Missing Security Headers",
                description="Проверка отсутствующих заголовков безопасности",
                severity="info",
                tags=["http", "headers", "security"]
            )
            db.session.add(sample_template)
            
            try:
                db.session.commit()
                print("[SUCCESS] Тестовые данные созданы")
            except Exception as e:
                print(f"[WARNING] Ошибка создания тестовых данных: {e}")
                db.session.rollback()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации базы данных: {e}")
        print("[INFO] Проверьте:")
        print("  1. PostgreSQL запущен: sudo systemctl status postgresql")
        print("  2. База данных создана")
        print("  3. Права доступа пользователя")
        print("  4. Параметры подключения в .env файле")
        return False

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаём приложение
    app = create_app()
    
    try:
        with app.app_context():
            print("[INFO] Инициализация Nuclei Scanner...")
            
            if not init_database():
                print("[ERROR] Не удалось инициализировать базу данных")
                sys.exit(1)
            
            print("[SUCCESS] Nuclei Scanner готов к работе")
            print(f"[INFO] Веб-интерфейс: http://localhost:{os.environ.get('PORT', 5000)}")
            print(f"[INFO] Логин: {os.environ.get('ADMIN_USER', 'admin')}")
            print(f"[INFO] Пароль: {os.environ.get('ADMIN_PASS', 'admin123')}")
            
            app.run(
                host='0.0.0.0',
                port=int(os.environ.get('PORT', 5000)),
                debug=os.environ.get('DEBUG', 'False').lower() == 'true'
            )
            
    except Exception as e:
        print(f"[ERROR] Ошибка запуска приложения: {e}")
        sys.exit(1)
EOF

    chown "$APP_USER:$APP_USER" "$APP_DIR/app.py"
    chmod +x "$APP_DIR/app.py"
    
    print_success "Файл app.py создан"
}

# Создание HTML шаблонов
create_templates() {
    print_status "Создание HTML шаблонов..."
    
    # Создание base.html
    cat > "$APP_DIR/templates/base.html" << 'EOF'
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Nuclei Scanner{% endblock %}</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .sidebar {
            min-height: 100vh;
            background: #343a40;
        }
        .sidebar .nav-link {
            color: #fff;
            padding: 15px 20px;
            border-bottom: 1px solid #495057;
        }
        .sidebar .nav-link:hover, .sidebar .nav-link.active {
            background: #495057;
            color: #fff;
        }
        .main-content {
            background: #f8f9fa;
            min-height: 100vh;
        }
        .status-online {
            color: #28a745;
        }
        .status-offline {
            color: #dc3545;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-2 p-0">
                <nav class="sidebar">
                    <div class="p-3">
                        <h5 class="text-white">Nuclei Scanner</h5>
                        <small class="text-muted">Система сканирования уязвимостей</small>
                    </div>
                    
                    <ul class="nav flex-column">
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'dashboard' %}active{% endif %}" href="{{ url_for('dashboard') }}">
                                <i class="fas fa-tachometer-alt"></i> Панель управления
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'servers' %}active{% endif %}" href="{{ url_for('servers') }}">
                                <i class="fas fa-server"></i> Серверы
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'tasks' %}active{% endif %}" href="{{ url_for('tasks') }}">
                                <i class="fas fa-tasks"></i> Задачи сканирования
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link {% if request.endpoint == 'vulnerabilities' %}active{% endif %}" href="{{ url_for('vulnerabilities') }}">
                                <i class="fas fa-bug"></i> Уязвимости
                            </a>
                        </li>
                        <li class="nav-item mt-auto">
                            <a class="nav-link" href="{{ url_for('logout') }}">
                                <i class="fas fa-sign-out-alt"></i> Выход
                            </a>
                        </li>
                    </ul>
                </nav>
            </div>
            
            <div class="col-md-10 main-content">
                <nav class="navbar navbar-light bg-white border-bottom">
                    <div class="container-fluid">
                        <span class="navbar-brand mb-0 h1">
                            {% block page_title %}Nuclei Scanner{% endblock %}
                        </span>
                        <div class="d-flex align-items-center">
                            <span class="me-3">
                                <i class="fas fa-user"></i> {{ session.username }}
                            </span>
                        </div>
                    </div>
                </nav>
                
                <div class="container-fluid p-4">
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="alert alert-info alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    {% block content %}{% endblock %}
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
EOF

    # Создание login.html
    cat > "$APP_DIR/templates/login.html" << 'EOF'
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuclei Scanner - Вход в систему</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.1.3/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card {
            background: white;
            border-radius: 15px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="text-center mb-4">
            <i class="fas fa-shield-alt fa-3x text-primary mb-3"></i>
            <h2>Nuclei Scanner</h2>
            <p class="text-muted">Система сканирования уязвимостей</p>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-danger" role="alert">
                        <i class="fas fa-exclamation-triangle"></i> {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST">
            <div class="mb-3">
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="fas fa-user"></i>
                    </span>
                    <input type="text" class="form-control" name="username" placeholder="Логин" required>
                </div>
            </div>
            
            <div class="mb-4">
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="fas fa-lock"></i>
                    </span>
                    <input type="password" class="form-control" name="password" placeholder="Пароль" required>
                </div>
            </div>
            
            <button type="submit" class="btn btn-primary w-100">
                <i class="fas fa-sign-in-alt"></i> Войти в систему
            </button>
        </form>
    </div>
</body>
</html>
EOF

    # Создание dashboard.html
    cat > "$APP_DIR/templates/dashboard.html" << 'EOF'
{% extends "base.html" %}

{% block title %}Панель управления - Nuclei Scanner{% endblock %}
{% block page_title %}Панель управления{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-md-3 mb-3">
        <div class="card h-100">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h6 class="card-title text-muted">Критичные уязвимости</h6>
                        <h3 class="text-danger">
                            {% set critical = vuln_stats|selectattr('severity_level', 'equalto', 'critical')|map(attribute='count')|sum %}
                            {{ critical or 0 }}
                        </h3>
                    </div>
                    <div class="text-danger">
                        <i class="fas fa-exclamation-triangle fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card h-100">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h6 class="card-title text-muted">Высокие уязвимости</h6>
                        <h3 class="text-warning">
                            {% set high = vuln_stats|selectattr('severity_level', 'equalto', 'high')|map(attribute='count')|sum %}
                            {{ high or 0 }}
                        </h3>
                    </div>
                    <div class="text-warning">
                        <i class="fas fa-exclamation fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card h-100">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h6 class="card-title text-muted">Активные задачи</h6>
                        <h3 class="text-info">{{ active_tasks }}</h3>
                    </div>
                    <div class="text-info">
                        <i class="fas fa-tasks fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-3 mb-3">
        <div class="card h-100">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h6 class="card-title text-muted">Онлайн серверы</h6>
                        <h3 class="text-success">
                            {% set online = server_stats|selectattr('status', 'equalto', 'online')|map(attribute='count')|sum %}
                            {{ online or 0 }}
                        </h3>
                    </div>
                    <div class="text-success">
                        <i class="fas fa-server fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-bug"></i> Последние найденные уязвимости
                </h5>
            </div>
            <div class="card-body">
                {% if recent_vulns %}
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>IP адрес</th>
                                <th>Шаблон</th>
                                <th>Критичность</th>
                                <th>URL</th>
                                <th>Обнаружено</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for vuln in recent_vulns %}
                            <tr>
                                <td><code>{{ vuln.ip_address }}</code></td>
                                <td><span class="badge bg-secondary">{{ vuln.template_id }}</span></td>
                                <td>
                                    <span class="badge 
                                        {% if vuln.severity_level == 'critical' %}bg-danger
                                        {% elif vuln.severity_level == 'high' %}bg-warning text-dark
                                        {% elif vuln.severity_level == 'medium' %}bg-info
                                        {% else %}bg-success{% endif %}">
                                        {{ vuln.severity_level|title }}
                                    </span>
                                </td>
                                <td>
                                    {% if vuln.url %}
                                        <a href="{{ vuln.url }}" target="_blank">{{ vuln.url|truncate(50) }}</a>
                                    {% else %}
                                        <span class="text-muted">-</span>
                                    {% endif %}
                                </td>
                                <td><small class="text-muted">{{ vuln.discovered_at.strftime('%d.%m.%Y %H:%M') }}</small></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                <div class="text-center mt-3">
                    <a href="{{ url_for('vulnerabilities') }}" class="btn btn-outline-primary">
                        <i class="fas fa-list"></i> Просмотреть все уязвимости
                    </a>
                </div>
                {% else %}
                <div class="text-center text-muted py-4">
                    <i class="fas fa-shield-alt fa-3x mb-3"></i>
                    <h6>Уязвимости не найдены</h6>
                    <p>Это хорошо! Продолжайте мониторинг безопасности.</p>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="fas fa-bolt"></i> Быстрые действия</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-3 mb-2">
                        <a href="{{ url_for('tasks') }}" class="btn btn-primary w-100">
                            <i class="fas fa-plus"></i> Новая задача
                        </a>
                    </div>
                    <div class="col-md-3 mb-2">
                        <a href="{{ url_for('servers') }}" class="btn btn-success w-100">
                            <i class="fas fa-server"></i> Управление серверами
                        </a>
                    </div>
                    <div class="col-md-3 mb-2">
                        <a href="{{ url_for('vulnerabilities') }}" class="btn btn-warning w-100">
                            <i class="fas fa-bug"></i> Все уязвимости
                        </a>
                    </div>
                    <div class="col-md-3 mb-2">
                        <button class="btn btn-info w-100" onclick="location.reload()">
                            <i class="fas fa-sync"></i> Обновить данные
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
EOF

    # Создание остальных шаблонов
    cat > "$APP_DIR/templates/servers.html" << 'EOF'
{% extends "base.html" %}
{% block title %}Управление серверами - Nuclei Scanner{% endblock %}
{% block page_title %}Управление серверами{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <h4>Список серверов</h4>
        <p class="text-muted">Управление воркер-узлами для сканирования</p>
    </div>
    <div class="col-md-4 text-end">
        <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addServerModal">
            <i class="fas fa-plus"></i> Добавить сервер
        </button>
    </div>
</div>

<div class="card">
    <div class="card-body">
        {% if servers %}
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя хоста</th>
                        <th>IP адрес</th>
                        <th>SSH порт</th>
                        <th>Статус</th>
                        <th>Последняя активность</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for server in servers %}
                    <tr>
                        <td>{{ server.id }}</td>
                        <td><strong>{{ server.hostname }}</strong></td>
                        <td><code>{{ server.ip_address }}</code></td>
                        <td>{{ server.ssh_port }}</td>
                        <td>
                            {% if server.status == 'online' %}
                                <span class="badge bg-success">
                                    <i class="fas fa-circle"></i> Онлайн
                                </span>
                            {% else %}
                                <span class="badge bg-danger">
                                    <i class="fas fa-circle"></i> Оффлайн
                                </span>
                            {% endif %}
                        </td>
                        <td>
                            {% if server.last_seen %}
                                <small class="text-muted">{{ server.last_seen.strftime('%d.%m.%Y %H:%M') }}</small>
                            {% else %}
                                <small class="text-muted">Никогда</small>
                            {% endif %}
                        </td>
                        <td>
                            <form method="POST" action="{{ url_for('delete_server', server_id=server.id) }}" 
                                  style="display: inline;" 
                                  onsubmit="return confirm('Удалить сервер {{ server.hostname }}?')">
                                <button type="submit" class="btn btn-outline-danger btn-sm">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="text-center text-muted py-5">
            <i class="fas fa-server fa-3x mb-3"></i>
            <h6>Серверы не добавлены</h6>
            <p>Добавьте первый сервер для начала сканирования</p>
            <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addServerModal">
                <i class="fas fa-plus"></i> Добавить сервер
            </button>
        </div>
        {% endif %}
    </div>
</div>

<div class="modal fade" id="addServerModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="fas fa-plus"></i> Добавить новый сервер
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{{ url_for('add_server') }}">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="hostname" class="form-label">Имя хоста</label>
                        <input type="text" class="form-control" id="hostname" name="hostname" 
                               placeholder="nuclei-worker-01" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="ip_address" class="form-label">IP адрес</label>
                        <input type="text" class="form-control" id="ip_address" name="ip_address" 
                               placeholder="192.168.1.100" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="ssh_port" class="form-label">SSH порт</label>
                        <input type="number" class="form-control" id="ssh_port" name="ssh_port" 
                               value="22" min="1" max="65535">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-plus"></i> Добавить
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
EOF

    # Создание tasks.html и vulnerabilities.html (упрощенные версии)
    cat > "$APP_DIR/templates/tasks.html" << 'EOF'
{% extends "base.html" %}
{% block title %}Задачи сканирования - Nuclei Scanner{% endblock %}
{% block page_title %}Задачи сканирования{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <h4>Управление задачами</h4>
        <p class="text-muted">Создание и мониторинг задач сканирования</p>
    </div>
    <div class="col-md-4 text-end">
        <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#createTaskModal">
            <i class="fas fa-plus"></i> Создать задачу
        </button>
    </div>
</div>

<div class="card">
    <div class="card-body">
        {% if tasks %}
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>Цели</th>
                        <th>Статус</th>
                        <th>Создано</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for task in tasks %}
                    <tr>
                        <td>{{ task.id }}</td>
                        <td><strong>{{ task.name }}</strong></td>
                        <td><span class="badge bg-info">{{ task.target_ips|length }} IP</span></td>
                        <td>
                            {% if task.status == 'pending' %}
                                <span class="badge bg-warning">Ожидает</span>
                            {% elif task.status == 'running' %}
                                <span class="badge bg-primary">Выполняется</span>
                            {% elif task.status == 'completed' %}
                                <span class="badge bg-success">Завершена</span>
                            {% else %}
                                <span class="badge bg-danger">Ошибка</span>
                            {% endif %}
                        </td>
                        <td><small class="text-muted">{{ task.created_at.strftime('%d.%m.%Y %H:%M') }}</small></td>
                        <td>
                            {% if task.status == 'pending' %}
                            <form method="POST" action="{{ url_for('start_task', task_id=task.id) }}" style="display: inline;">
                                <button type="submit" class="btn btn-outline-success btn-sm">
                                    <i class="fas fa-play"></i>
                                </button>
                            </form>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="text-center text-muted py-5">
            <i class="fas fa-tasks fa-3x mb-3"></i>
            <h6>Задачи не созданы</h6>
            <p>Создайте первую задачу сканирования</p>
        </div>
        {% endif %}
    </div>
</div>

<div class="modal fade" id="createTaskModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Создать задачу сканирования</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="{{ url_for('create_task') }}">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="name" class="form-label">Название задачи</label>
                        <input type="text" class="form-control" id="name" name="name" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="targets" class="form-label">Целевые IP адреса</label>
                        <textarea class="form-control" id="targets" name="targets" rows="4" 
                                  placeholder="192.168.1.1&#10;192.168.1.0/24" required></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="servers" class="form-label">Серверы для выполнения</label>
                        <select class="form-select" id="servers" name="servers" multiple required>
                            {% for server in servers %}
                            <option value="{{ server.id }}" selected>
                                {{ server.hostname }} ({{ server.ip_address }})
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="priority" class="form-label">Приоритет</label>
                        <select class="form-select" id="priority" name="priority">
                            <option value="1">Низкий</option>
                            <option value="2" selected>Средний</option>
                            <option value="3">Высокий</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">Создать задачу</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
EOF

    cat > "$APP_DIR/templates/vulnerabilities.html" << 'EOF'
{% extends "base.html" %}
{% block title %}Уязвимости - Nuclei Scanner{% endblock %}
{% block page_title %}Найденные уязвимости{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <h4>Обнаруженные уязвимости</h4>
        <p class="text-muted">Результаты сканирования безопасности</p>
    </div>
    <div class="col-md-4">
        <select class="form-select" onchange="filterBySeverity(this.value)">
            <option value="">Все уровни критичности</option>
            <option value="critical">Критичные</option>
            <option value="high">Высокие</option>
            <option value="medium">Средние</option>
            <option value="low">Низкие</option>
        </select>
    </div>
</div>

<div class="card">
    <div class="card-body">
        {% if vulnerabilities.items %}
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>IP адрес</th>
                        <th>Шаблон</th>
                        <th>Критичность</th>
                        <th>URL</th>
                        <th>Обнаружено</th>
                    </tr>
                </thead>
                <tbody>
                    {% for vuln in vulnerabilities.items %}
                    <tr>
                        <td><code>{{ vuln.ip_address }}</code></td>
                        <td><span class="badge bg-secondary">{{ vuln.template_id }}</span></td>
                        <td>
                            <span class="badge 
                                {% if vuln.severity_level == 'critical' %}bg-danger
                                {% elif vuln.severity_level == 'high' %}bg-warning text-dark
                                {% elif vuln.severity_level == 'medium' %}bg-info
                                {% else %}bg-success{% endif %}">
                                {{ vuln.severity_level|title }}
                            </span>
                        </td>
                        <td>
                            {% if vuln.url %}
                                <a href="{{ vuln.url }}" target="_blank">{{ vuln.url|truncate(40) }}</a>
                            {% else %}
                                <span class="text-muted">-</span>
                            {% endif %}
                        </td>
                        <td><small class="text-muted">{{ vuln.discovered_at.strftime('%d.%m.%Y %H:%M') }}</small></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="text-center text-muted py-5">
            <i class="fas fa-shield-alt fa-3x mb-3 text-success"></i>
            <h6>Уязвимости не обнаружены</h6>
            <p>Это отличная новость! Ваша инфраструктура защищена.</p>
            <a href="{{ url_for('tasks') }}" class="btn btn-primary">
                <i class="fas fa-plus"></i> Запустить сканирование
            </a>
        </div>
        {% endif %}
    </div>
</div>

<script>
function filterBySeverity(severity) {
    const params = new URLSearchParams(window.location.search);
    if (severity) {
        params.set('severity', severity);
    } else {
        params.delete('severity');
    }
    window.location.search = params.toString();
}
</script>
{% endblock %}
EOF

    chown -R "$APP_USER:$APP_USER" "$APP_DIR/templates/"
    print_success "HTML шаблоны созданы"
}

# Настройка конфигурации
setup_config() {
    print_status "Создание конфигурационного файла..."
    
    # Загружаем пароль базы данных
    source /etc/nuclei-admin.env
    
    # Генерация секретного ключа
    SECRET_KEY=$(openssl rand -base64 64)
    
    # Создание .env файла
    cat > "$APP_DIR/.env" << EOF
# Конфигурация Nuclei Scanner
SECRET_KEY='$SECRET_KEY'

# Базы данных
DB_BELARUS=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_belarus
DB_RUSSIA=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_russia
DB_KAZAKHSTAN=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_kazakhstan
CURRENT_DB=belarus

# Аутентификация
ADMIN_USER=admin
ADMIN_PASS=admin123

# SSH настройки для воркеров
SSH_USER=root
SSH_KEY_PATH=/home/$APP_USER/.ssh/id_rsa

# Telegram уведомления (заполните при необходимости)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Настройки приложения
DEBUG=False
PORT=5000
EOF

    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    
    print_success "Конфигурация создана"
}

# Настройка SSH ключей
setup_ssh_keys() {
    print_status "Настройка SSH ключей..."
    
    SSH_DIR="/home/$APP_USER/.ssh"
    
    # Создание SSH директории
    sudo -u "$APP_USER" mkdir -p "$SSH_DIR"
    sudo -u "$APP_USER" chmod 700 "$SSH_DIR"
    
    # Генерация SSH ключа если не существует
    if [ ! -f "$SSH_DIR/id_rsa" ]; then
        sudo -u "$APP_USER" ssh-keygen -t rsa -b 4096 -f "$SSH_DIR/id_rsa" -N ""
        print_success "SSH ключ сгенерирован: $SSH_DIR/id_rsa.pub"
        print_warning "Не забудьте добавить публичный ключ на воркер-серверы!"
        echo "Публичный ключ:"
        cat "$SSH_DIR/id_rsa.pub"
    else
        print_warning "SSH ключ уже существует"
    fi
}

# Настройка Nginx
setup_nginx() {
    print_status "Настройка Nginx..."
    
    # Создание конфигурации Nginx
    cat > /etc/nginx/sites-available/nuclei-admin << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30;
        proxy_send_timeout 30;
        proxy_read_timeout 30;
    }
    
    location /static {
        alias /opt/nuclei-admin/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    client_max_body_size 10M;
    
    access_log /var/log/nginx/nuclei-admin.access.log;
    error_log /var/log/nginx/nuclei-admin.error.log;
}
EOF

    # Активация сайта
    if [ "$OS" = "debian" ]; then
        ln -sf /etc/nginx/sites-available/nuclei-admin /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
    fi
    
    # Проверка конфигурации
    nginx -t
    
    # Перезапуск Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    print_success "Nginx настроен"
}

# Настройка Supervisor
setup_supervisor() {
    print_status "Настройка Supervisor..."
    
    # Создание конфигурации Supervisor
    cat > /etc/supervisor/conf.d/nuclei-admin.conf << EOF
[program:nuclei-admin]
command=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --worker-class gevent --timeout 120 app:app
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/gunicorn.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin",PYTHONUNBUFFERED=1
EOF

    # Перезапуск Supervisor
    systemctl restart supervisor
    systemctl enable supervisor
    
    # Обновление конфигурации
    supervisorctl reread
    supervisorctl update
    
    print_success "Supervisor настроен"
}

# Инициализация базы данных
init_database() {
    print_status "Инициализация базы данных..."
    
    cd "$APP_DIR"
    
    # Создаём таблицы через приложение
    sudo -u "$APP_USER" bash -c "
        cd $APP_DIR
        source .env
        export SKIP_BACKGROUND_TASKS=1
        timeout 30 $APP_DIR/venv/bin/python app.py > /tmp/nuclei-init.log 2>&1 &
        APP_PID=\$!
        
        # Ждём инициализации (максимум 20 секунд)
        for i in {1..20}; do
            if grep -q 'Nuclei Scanner готов к работе' /tmp/nuclei-init.log 2>/dev/null; then
                kill \$APP_PID 2>/dev/null || true
                echo 'Инициализация завершена успешно'
                exit 0
            fi
            sleep 1
        done
        
        # Если не удалось инициализировать через приложение
        kill \$APP_PID 2>/dev/null || true
        echo 'Попытка прямой инициализации...'
        
        $APP_DIR/venv/bin/python -c \"
import sys, os
sys.path.insert(0, os.getcwd())
os.environ['SKIP_BACKGROUND_TASKS'] = '1'
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('Таблицы созданы успешно')
\" 2>/dev/null && echo 'База данных инициализирована' || echo 'Ошибка инициализации'
    "
    
    if [ $? -eq 0 ]; then
        print_success "База данных инициализирована"
    else
        print_warning "Возможны проблемы с инициализацией БД. Проверьте логи: /tmp/nuclei-init.log"
        print_status "Приложение попытается создать таблицы при первом запуске"
    fi
}

# Проверка состояния сервисов
check_services() {
    print_status "Проверка состояния сервисов..."
    
    echo "PostgreSQL: $(systemctl is-active postgresql)"
    echo "Nginx: $(systemctl is-active nginx)"
    echo "Supervisor: $(systemctl is-active supervisor)"
    echo "Redis: $(systemctl is-active redis-server || systemctl is-active redis || echo 'inactive')"
    
    # Проверяем запуск приложения
    sleep 5
    echo "Nuclei Admin: $(supervisorctl status nuclei-admin | awk '{print $2}' || echo 'not running')"
    
    print_success "Проверка завершена"
}

# Вывод финальной информации
print_final_info() {
    echo ""
    print_success "Установка Nuclei Scanner завершена!"
    echo "=========================================="
    echo ""
    echo "📋 Информация о развёртывании:"
    echo "   • Директория приложения: $APP_DIR"
    echo "   • Пользователь: $APP_USER"
    echo "   • Конфигурация: $APP_DIR/.env"
    echo "   • Логи: $APP_DIR/logs/"
    echo ""
    echo "🌐 Веб-интерфейс:"
    echo "   • URL: http://$(hostname -I | awk '{print $1}')"
    echo "   • Логин: admin"
    echo "   • Пароль: admin123"
    echo ""
    echo "🔑 SSH ключ для воркеров:"
    echo "   • Публичный ключ: /home/$APP_USER/.ssh/id_rsa.pub"
    echo ""
    echo "🛠️ Управление сервисом:"
    echo "   • Статус: supervisorctl status nuclei-admin"
    echo "   • Перезапуск: supervisorctl restart nuclei-admin"
    echo "   • Логи: tail -f $APP_DIR/logs/gunicorn.log"
    echo ""
    echo "🔧 Следующие шаги:"
    echo "   1. Настройте SSH ключи на воркер-серверах"
    echo "   2. Настройте SSL сертификат (опционально)"
    echo "   3. Настройте Telegram уведомления в .env файле"
    echo "   4. Добавьте воркер-серверы через веб-интерфейс"
    echo ""
    echo "📊 Информация о базе данных сохранена в /etc/nuclei-admin.env"
    echo ""
    print_warning "Не забудьте изменить пароль администратора!"
}

# Основная функция
main() {
    print_status "Начало установки Nuclei Scanner..."
    
    # Установка пакетов в зависимости от ОС
    if [ "$OS" = "debian" ]; then
        install_packages_debian
    elif [ "$OS" = "redhat" ]; then
        install_packages_redhat
    else
        print_error "Неподдерживаемая операционная система"
        exit 1
    fi
    
    create_app_user
    setup_postgresql
    setup_app_directory
    install_nuclei
    install_python_deps
    create_app_files
    create_templates
    setup_config
    setup_ssh_keys
    setup_nginx
    setup_supervisor
    init_database
    check_services
    print_final_info
}

# Обработка ошибок
trap 'print_error "Установка прервана из-за ошибки на строке $LINENO"' ERR

# Запуск основной функции
main "$@"