# admin-server/web/routes/servers.py - ДОПОЛНЕННАЯ версия
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from services.database_service import DatabaseService
from services.ssh_service import SSHService
from services.server_monitor import ServerMonitor
from models.server import Server
from utils.validators import validate_ip_address, validate_hostname, validate_port
from utils.logger import get_logger
import os

logger = get_logger(__name__)
servers_bp = Blueprint('servers', __name__)

# Инициализация сервисов
db_service = DatabaseService()
ssh_service = SSHService(
    ssh_username=os.getenv('SSH_USERNAME', 'root'),
    ssh_key_path=os.getenv('SSH_KEY_PATH'),
    ssh_password=os.getenv('SSH_PASSWORD')
)
server_monitor = ServerMonitor()
server_monitor.set_ssh_service(ssh_service)

@servers_bp.route('/')
@login_required
def index():
    """Список серверов"""
    try:
        servers = db_service.get_servers()
        server_statuses = server_monitor.check_all_servers()
        
        # Обогащаем данные серверов статусной информацией
        enhanced_servers = []
        for server in servers:
            server_dict = server.to_dict()
            status_info = server_statuses.get(server.id, {})
            server_dict['status_info'] = status_info.get('info', {})
            server_dict['current_status'] = status_info.get('status', 'unknown')
            enhanced_servers.append(server_dict)
        
        return render_template('servers.html', servers=enhanced_servers)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки списка серверов: {e}")
        flash('Ошибка загрузки списка серверов', 'error')
        return render_template('servers.html', servers=[])

@servers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_server():
    """Добавление нового сервера"""
    if request.method == 'POST':
        try:
            hostname = request.form.get('hostname', '').strip()
            ip_address = request.form.get('ip_address', '').strip()
            ssh_port = int(request.form.get('ssh_port', 22))
            
            # Валидация данных
            errors = []
            
            if not hostname:
                errors.append('Имя хоста обязательно')
            elif not validate_hostname(hostname):
                errors.append('Некорректное имя хоста')
            
            if not ip_address:
                errors.append('IP-адрес обязателен')
            elif not validate_ip_address(ip_address):
                errors.append('Некорректный IP-адрес')
            
            if not validate_port(ssh_port):
                errors.append('Некорректный SSH порт')
            
            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('servers.index'))
            
            # Создание сервера
            server = Server(
                hostname=hostname,
                ip_address=ip_address,
                ssh_port=ssh_port,
                status='offline'
            )
            
            server_id = db_service.save_server(server)
            
            if server_id:
                logger.info(f"Сервер добавлен: {hostname} ({ip_address})")
                flash(f'Сервер {hostname} успешно добавлен', 'success')
            else:
                flash('Ошибка добавления сервера', 'error')
            
        except ValueError as e:
            flash(f'Ошибка валидации: {e}', 'error')
        except Exception as e:
            logger.error(f"Ошибка добавления сервера: {e}")
            flash('Ошибка добавления сервера', 'error')
    
    return redirect(url_for('servers.index'))

@servers_bp.route('/api/<int:server_id>/status')
@login_required
def api_server_status(server_id):
    """API для получения статуса сервера"""
    try:
        metrics = server_monitor.get_server_metrics(server_id)
        return jsonify({
            'success': True,
            'metrics': metrics
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса сервера {server_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@servers_bp.route('/api/<int:server_id>/install-nuclei', methods=['POST'])
@login_required
def api_install_nuclei(server_id):
    """API для установки Nuclei на сервер"""
    try:
        servers = db_service.get_servers()
        server = next((s for s in servers if s.id == server_id), None)
        
        if not server:
            return jsonify({
                'success': False,
                'error': 'Сервер не найден'
            }), 404
        
        result = ssh_service.install_nuclei(server)
        
        if result['success']:
            logger.info(f"Nuclei установлен на сервере {server.hostname}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка установки Nuclei на сервер {server_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@servers_bp.route('/api/<int:server_id>/update-templates', methods=['POST'])
@login_required
def api_update_templates(server_id):
    """API для обновления шаблонов Nuclei"""
    try:
        servers = db_service.get_servers()
        server = next((s for s in servers if s.id == server_id), None)
        
        if not server:
            return jsonify({
                'success': False,
                'error': 'Сервер не найден'
            }), 404
        
        result = ssh_service.update_nuclei_templates(server)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка обновления шаблонов на сервере {server_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@servers_bp.route('/api/<int:server_id>/execute-command', methods=['POST'])
@login_required
def api_execute_command(server_id):
    """API для выполнения команды на сервере"""
    try:
        servers = db_service.get_servers()
        server = next((s for s in servers if s.id == server_id), None)
        
        if not server:
            return jsonify({
                'success': False,
                'error': 'Сервер не найден'
            }), 404
        
        command = request.json.get('command', '').strip()
        if not command:
            return jsonify({
                'success': False,
                'error': 'Команда не указана'
            }), 400
        
        result = ssh_service.execute_command(server, command)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка выполнения команды на сервере {server_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500