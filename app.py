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

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'nuclei-scanner-secret-key-2025')

# Конфигурация базы данных
DATABASE_URLS = {
    'belarus': os.environ.get('DB_BELARUS', 'postgresql://user:pass@localhost:5432/nuclei_belarus'),
    'russia': os.environ.get('DB_RUSSIA', 'postgresql://user:pass@localhost:5433/nuclei_russia'),
    'kazakhstan': os.environ.get('DB_KAZAKHSTAN', 'postgresql://user:pass@localhost:5434/nuclei_kazakhstan')
}

# Текущая активная база (можно переключать через админку)
current_db = os.environ.get('CURRENT_DB', 'belarus')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URLS[current_db]
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    target_ips = db.Column(db.JSON)  # Список IP адресов
    template_ids = db.Column(db.JSON)  # Список ID шаблонов
    server_ids = db.Column(db.JSON)  # Список ID серверов
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
            elif '-' in target and target.count('.') == 6:  # IP1-IP2 формат
                start_ip, end_ip = target.split('-')
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())
                
                # Проверяем, что оба адреса одного типа (IPv4 или IPv6)
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
    
    return list(set(ips))  # Убираем дубли

def execute_ssh_command(server, command):
    """Выполнение команды на удалённом сервере через SSH"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=server.ip_address,
            port=server.ssh_port,
            username=os.environ.get('SSH_USER', 'root'),
            key_filename=os.environ.get('SSH_KEY_PATH', '~/.ssh/id_rsa')
        )
        
        stdin, stdout, stderr = ssh.exec_command(command)
        result = stdout.read().decode()
        error = stderr.read().decode()
        ssh.close()
        
        return {'success': True, 'output': result, 'error': error}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def update_server_status():
    """Фоновая задача обновления статуса серверов"""
    while True:
        try:
            with app.app_context():  # Add app context for thread
                servers = Server.query.all()
                for server in servers:
                    result = execute_ssh_command(server, 'echo "ping"')
                    if result['success']:
                        server.status = 'online'
                        server.last_seen = datetime.datetime.utcnow()
                    else:
                        server.status = 'offline'
                
                db.session.commit()
        except Exception as e:
            print(f"[ERROR] Ошибка обновления статуса серверов: {e}")
        
        time.sleep(30)  # Проверяем каждые 30 секунд

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
        
        # Проверка логина/пароля с использованием хеширования
        admin_user = os.environ.get('ADMIN_USER', 'admin')
        admin_pass = os.environ.get('ADMIN_PASS', 'admin123')
        
        if username == admin_user and check_password_hash(
            generate_password_hash(admin_pass), password
        ):
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
    # Статистика уязвимостей
    vuln_stats = db.session.execute(text("""
        SELECT severity_level, COUNT(*) as count 
        FROM vulnerabilities 
        GROUP BY severity_level
    """)).fetchall()
    
    # Статус серверов
    server_stats = db.session.execute(text("""
        SELECT status, COUNT(*) as count 
        FROM servers 
        GROUP BY status
    """)).fetchall()
    
    # Активные задачи
    active_tasks = ScanTask.query.filter(
        ScanTask.status.in_(['pending', 'running'])
    ).count()
    
    # Последние уязвимости
    recent_vulns = Vulnerability.query.order_by(
        Vulnerability.discovered_at.desc()
    ).limit(10).all()
    
    return render_template('dashboard.html', 
                         vuln_stats=vuln_stats,
                         server_stats=server_stats,
                         active_tasks=active_tasks,
                         recent_vulns=recent_vulns)

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
        
        # Распределяем IP адреса по серверам
        available_servers = Server.query.filter(
            Server.id.in_(task.server_ids),
            Server.status == 'online'
        ).all()
        
        if not available_servers:
            flash('Нет доступных серверов для выполнения задачи')
            return redirect(url_for('tasks'))
        
        # Простое распределение нагрузки
        ips_per_server = len(task.target_ips) // len(available_servers)
        
        for i, server in enumerate(available_servers):
            start_idx = i * ips_per_server
            end_idx = start_idx + ips_per_server if i < len(available_servers) - 1 else len(task.target_ips)
            server_ips = task.target_ips[start_idx:end_idx]
            
            # Отправляем команду на сервер
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
    data = request.get_json()
    server_id = data.get('server_id')
    
    server = Server.query.get(server_id)
    if server:
        server.status = 'online'
        server.last_seen = datetime.datetime.utcnow()
        db.session.commit()
    
    return jsonify({'status': 'ok'})

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
        
        # Уведомление о критичных уязвимостях
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
    data = request.get_json()
    task_id = data.get('task_id')
    
    task = ScanTask.query.get(task_id)
    if task:
        task.status = 'completed'
        task.completed_at = datetime.datetime.utcnow()
        db.session.commit()
        
        send_telegram_message(f"✅ Задача завершена: {task.name}")
    
    return jsonify({'status': 'ok'})

# Remove the @app.before_first_request decorator and create a new function
def create_tables():
    """Создание таблиц в базе данных"""
    with app.app_context():
        db.create_all()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print("\n[INFO] Shutting down Nuclei Scanner...")
    # Cleanup code here
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        create_tables()
        
        # Запуск фонового потока обновления статуса серверов
        status_thread = threading.Thread(target=update_server_status, daemon=True)
        status_thread.start()
        
        # Запуск Flask приложения
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=os.environ.get('DEBUG', 'False').lower() == 'true'
        )
    except Exception as e:
        print(f"[ERROR] Failed to start application: {e}")
        sys.exit(1)