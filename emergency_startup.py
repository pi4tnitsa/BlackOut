#!/usr/bin/env python3
"""
Аварийный скрипт запуска Nuclei Scanner
Запускает минимальную версию системы если основное приложение не работает
"""

import os
import sys
from flask import Flask, render_template_string, request, redirect, flash, session

# Добавляем путь к проекту
sys.path.insert(0, '/opt/nuclei-scanner')

app = Flask(__name__)
app.secret_key = 'emergency-key-change-me'

# Простые учетные данные
ADMIN_USER = 'admin'
ADMIN_PASS = 'nuclei_admin_2024!'

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            flash('Добро пожаловать в аварийный режим!', 'success')
            return redirect('/dashboard')
        else:
            flash('Неверные учетные данные', 'error')
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nuclei Scanner - Аварийный вход</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card mt-5">
                        <div class="card-header bg-warning">
                            <h4><i class="fa fa-exclamation-triangle"></i> Аварийный режим</h4>
                        </div>
                        <div class="card-body">
                            {% with messages = get_flashed_messages(with_categories=true) %}
                                {% if messages %}
                                    {% for category, message in messages %}
                                        <div class="alert alert-{{ 'danger' if category == 'error' else category }}">
                                            {{ message }}
                                        </div>
                                    {% endfor %}
                                {% endif %}
                            {% endwith %}
                            
                            <form method="POST">
                                <div class="mb-3">
                                    <label class="form-label">Логин</label>
                                    <input type="text" class="form-control" name="username" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Пароль</label>
                                    <input type="password" class="form-control" name="password" required>
                                </div>
                                <button type="submit" class="btn btn-warning">Войти</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect('/login')
    
    # Проверяем статус основных сервисов
    services_status = check_services()
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nuclei Scanner - Аварийная панель</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-warning">
            <div class="container">
                <span class="navbar-brand">🚨 Nuclei Scanner - Аварийный режим</span>
                <a href="/logout" class="btn btn-outline-dark">Выйти</a>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="alert alert-warning">
                <h4>⚠️ Система работает в аварийном режиме</h4>
                <p>Основное приложение недоступно. Используется упрощенная панель управления.</p>
            </div>
            
            <div class="row">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5>Статус сервисов</h5>
                        </div>
                        <div class="card-body">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Сервис</th>
                                        <th>Статус</th>
                                        <th>Действие</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for service, status in services.items() %}
                                    <tr>
                                        <td>{{ service }}</td>
                                        <td>
                                            <span class="badge bg-{{ 'success' if status else 'danger' }}">
                                                {{ 'Активен' if status else 'Остановлен' }}
                                            </span>
                                        </td>
                                        <td>
                                            <a href="/restart/{{ service }}" class="btn btn-sm btn-primary">Перезапустить</a>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Быстрые действия</h5>
                        </div>
                        <div class="card-body">
                            <a href="/logs" class="btn btn-info mb-2 d-block">Просмотр логов</a>
                            <a href="/restart-all" class="btn btn-warning mb-2 d-block">Перезапустить все</a>
                            <a href="/status" class="btn btn-secondary mb-2 d-block">Полный статус</a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Информация</h5>
                        </div>
                        <div class="card-body">
                            <p><strong>Время запуска:</strong> {{ current_time }}</p>
                            <p><strong>Режим:</strong> Аварийный</p>
                            <p><strong>Версия:</strong> Emergency v1.0</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''', services=services_status, current_time=get_current_time())

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/logs')
def logs():
    if 'logged_in' not in session:
        return redirect('/login')
    
    log_content = get_recent_logs()
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Логи системы</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-dark bg-warning">
            <div class="container">
                <span class="navbar-brand">📋 Логи системы</span>
                <a href="/dashboard" class="btn btn-outline-dark">Назад</a>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="card">
                <div class="card-header">
                    <h5>Последние записи в логах</h5>
                </div>
                <div class="card-body">
                    <pre style="background: #f8f9fa; padding: 15px; max-height: 500px; overflow-y: scroll;">{{ logs }}</pre>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''', logs=log_content)

@app.route('/restart/<service>')
def restart_service(service):
    if 'logged_in' not in session:
        return redirect('/login')
    
    result = restart_system_service(service)
    flash(f'Сервис {service}: {result}', 'info')
    return redirect('/dashboard')

@app.route('/restart-all')
def restart_all():
    if 'logged_in' not in session:
        return redirect('/login')
    
    services = ['supervisor', 'nginx', 'postgresql', 'redis']
    for service in services:
        restart_system_service(service)
    
    flash('Все сервисы перезапущены', 'success')
    return redirect('/dashboard')

def check_services():
    """Проверка статуса сервисов"""
    import subprocess
    
    services = {
        'PostgreSQL': False,
        'Redis': False,
        'Nginx': False,
        'Supervisor': False
    }
    
    service_names = {
        'PostgreSQL': 'postgresql',
        'Redis': 'redis-server',
        'Nginx': 'nginx',
        'Supervisor': 'supervisor'
    }
    
    for display_name, system_name in service_names.items():
        try:
            result = subprocess.run(['systemctl', 'is-active', system_name], 
                                   capture_output=True, text=True)
            services[display_name] = result.stdout.strip() == 'active'
        except:
            services[display_name] = False
    
    return services

def get_recent_logs():
    """Получение последних записей логов"""
    import subprocess
    
    log_files = [
        '/var/log/nuclei-scanner/web.out.log',
        '/var/log/nuclei-scanner/web.err.log',
        '/var/log/syslog'
    ]
    
    logs = []
    
    for log_file in log_files:
        try:
            if os.path.exists(log_file):
                result = subprocess.run(['tail', '-20', log_file], 
                                       capture_output=True, text=True)
                logs.append(f"=== {log_file} ===")
                logs.append(result.stdout)
                logs.append("")
        except:
            logs.append(f"=== Ошибка чтения {log_file} ===")
    
    return '\n'.join(logs) if logs else 'Логи недоступны'

def restart_system_service(service):
    """Перезапуск системного сервиса"""
    import subprocess
    
    service_map = {
        'PostgreSQL': 'postgresql',
        'Redis': 'redis-server', 
        'Nginx': 'nginx',
        'Supervisor': 'supervisor'
    }
    
    system_name = service_map.get(service, service)
    
    try:
        subprocess.run(['systemctl', 'restart', system_name], check=True)
        return 'перезапущен успешно'
    except subprocess.CalledProcessError:
        return 'ошибка перезапуска'
    except:
        return 'команда недоступна'

def get_current_time():
    """Получение текущего времени"""
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    print("🚨 Запуск Nuclei Scanner в аварийном режиме")
    print("📊 Доступ: http://localhost:5001")
    print("🔐 Логин: admin / Пароль: nuclei_admin_2024!")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
