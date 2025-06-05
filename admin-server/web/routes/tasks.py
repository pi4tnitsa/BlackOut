# admin-server/web/routes/tasks.py - ПОЛНАЯ РЕАЛИЗАЦИЯ
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from services.database_service import DatabaseService
from services.task_distributor import TaskDistributor
from services.ssh_service import SSHService
from utils.validators import validate_ip_range
from utils.helpers import generate_task_id, calculate_scan_eta
from utils.logger import get_logger
import threading
import os

logger = get_logger(__name__)
tasks_bp = Blueprint('tasks', __name__)

# Инициализация сервисов
db_service = DatabaseService()
task_distributor = TaskDistributor()
ssh_service = SSHService(
    ssh_username=os.getenv('SSH_USERNAME', 'root'),
    ssh_key_path=os.getenv('SSH_KEY_PATH'),
    ssh_password=os.getenv('SSH_PASSWORD')
)
task_distributor.set_ssh_service(ssh_service)

@tasks_bp.route('/')
@login_required
def index():
    """Список задач сканирования"""
    try:
        tasks = db_service.get_tasks()
        servers = db_service.get_servers()
        
        return render_template('tasks.html', tasks=tasks, servers=servers)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки списка задач: {e}")
        flash('Ошибка загрузки списка задач', 'error')
        return render_template('tasks.html', tasks=[], servers=[])

@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """Создание новой задачи сканирования"""
    if request.method == 'POST':
        try:
            task_name = request.form.get('task_name', '').strip()
            ip_ranges_text = request.form.get('ip_ranges', '').strip()
            selected_servers = request.form.getlist('server_ids')
            database_name = request.form.get('database', 'belarus')
            
            # Валидация данных
            errors = []
            
            if not task_name:
                errors.append('Название задачи обязательно')
            
            if not ip_ranges_text:
                errors.append('IP-диапазоны обязательны')
            
            if not selected_servers:
                errors.append('Необходимо выбрать хотя бы один сервер')
            
            # Парсинг и валидация IP-диапазонов
            ip_ranges = []
            if ip_ranges_text:
                for line in ip_ranges_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        is_valid, error_msg = validate_ip_range(line)
                        if is_valid:
                            ip_ranges.append(line)
                        else:
                            errors.append(f'Некорректный IP-диапазон "{line}": {error_msg}')
            
            if not ip_ranges:
                errors.append('Не найдено валидных IP-диапазонов')
            
            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('tasks.index'))
            
            # Создание задачи
            server_ids = [int(sid) for sid in selected_servers]
            
            # Инициализируем распределитель с выбранной базой данных
            distributor = TaskDistributor(database_name)
            distributor.set_ssh_service(ssh_service)
            
            task_id = distributor.create_scan_task(
                name=task_name,
                ip_ranges=ip_ranges,
                server_ids=server_ids
            )
            
            if task_id:
                logger.info(f"Создана задача сканирования: {task_name} (ID: {task_id})")
                flash(f'Задача "{task_name}" успешно создана', 'success')
            else:
                flash('Ошибка создания задачи', 'error')
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи: {e}")
            flash(f'Ошибка создания задачи: {str(e)}', 'error')
    
    return redirect(url_for('tasks.index'))

@tasks_bp.route('/api/<int:task_id>/start', methods=['POST'])
@login_required
def api_start_task(task_id):
    """API для запуска задачи сканирования"""
    try:
        database_name = request.json.get('database', 'belarus')
        
        # Инициализируем распределитель с нужной базой данных
        distributor = TaskDistributor(database_name)
        distributor.set_ssh_service(ssh_service)
        
        # Запускаем задачу в отдельном потоке
        def run_task():
            try:
                success = distributor.execute_scan_task(task_id)
                logger.info(f"Задача {task_id} завершена. Успех: {success}")
            except Exception as e:
                logger.error(f"Ошибка выполнения задачи {task_id}: {e}")
        
        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Задача запущена'
        })
        
    except Exception as e:
        logger.error(f"Ошибка запуска задачи {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tasks_bp.route('/api/<int:task_id>/status')
@login_required
def api_task_status(task_id):
    """API для получения статуса задачи"""
    try:
        tasks = db_service.get_tasks()
        task = next((t for t in tasks if t.id == task_id), None)
        
        if not task:
            return jsonify({
                'success': False,
                'error': 'Задача не найдена'
            }), 404
        
        return jsonify({
            'success': True,
            'task': task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса задачи {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tasks_bp.route('/api/estimate', methods=['POST'])
@login_required
def api_estimate_scan():
    """API для расчета времени сканирования"""
    try:
        ip_ranges_text = request.json.get('ip_ranges', '')
        server_count = int(request.json.get('server_count', 1))
        rate_limit = int(request.json.get('rate_limit', 100))
        
        # Подсчитываем общее количество IP
        total_ips = 0
        for line in ip_ranges_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                is_valid, _ = validate_ip_range(line)
                if is_valid:
                    # Приблизительный подсчет (для точности нужно парсить)
                    if '/' in line:
                        import ipaddress
                        network = ipaddress.ip_network(line, strict=False)
                        total_ips += network.num_addresses
                    elif '-' in line:
                        parts = line.split('-')
                        if len(parts) == 2:
                            try:
                                start = ipaddress.ip_address(parts[0].strip())
                                end = ipaddress.ip_address(parts[1].strip())
                                total_ips += int(end) - int(start) + 1
                            except:
                                total_ips += 1
                    else:
                        total_ips += 1
        
        eta = calculate_scan_eta(total_ips, rate_limit, server_count)
        
        return jsonify({
            'success': True,
            'total_ips': total_ips,
            'estimated_time': str(eta),
            'estimated_seconds': eta.total_seconds()
        })
        
    except Exception as e:
        logger.error(f"Ошибка расчета времени сканирования: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500