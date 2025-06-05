# admin-server/web/routes/vulnerabilities.py - ПОЛНАЯ РЕАЛИЗАЦИЯ
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required
from services.database_service import DatabaseService
from utils.helpers import export_vulnerabilities_to_json, format_datetime
from utils.logger import get_logger
import io
import csv
from datetime import datetime

logger = get_logger(__name__)
vulnerabilities_bp = Blueprint('vulnerabilities', __name__)

@vulnerabilities_bp.route('/')
@login_required
def index():
    """Список уязвимостей"""
    try:
        # Получаем параметры фильтрации
        database = request.args.get('database', 'belarus')
        ip_filter = request.args.get('ip', '')
        severity_filter = request.args.get('severity', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Инициализируем сервис с нужной базой данных
        db_service = DatabaseService(database)
        
        # Получаем уязвимости с фильтрацией
        offset = (page - 1) * per_page
        vulnerabilities = db_service.get_vulnerabilities(
            ip_filter=ip_filter if ip_filter else None,
            severity_filter=severity_filter if severity_filter else None,
            limit=per_page,
            offset=offset
        )
        
        # Получаем статистику
        stats = db_service.get_vulnerability_stats()
        
        # Список доступных баз данных
        available_databases = ['belarus', 'russia', 'kazakhstan']
        
        context = {
            'vulnerabilities': vulnerabilities,
            'stats': stats,
            'current_database': database,
            'available_databases': available_databases,
            'filters': {
                'ip': ip_filter,
                'severity': severity_filter,
                'page': page,
                'per_page': per_page
            },
            'severity_levels': ['info', 'low', 'medium', 'high', 'critical']
        }
        
        return render_template('vulnerabilities.html', **context)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки уязвимостей: {e}")
        return render_template('vulnerabilities.html', 
                             vulnerabilities=[], 
                             stats={}, 
                             error="Ошибка загрузки данных")

@vulnerabilities_bp.route('/api/search')
@login_required
def api_search():
    """API для поиска уязвимостей"""
    try:
        database = request.args.get('database', 'belarus')
        query = request.args.get('q', '').strip()
        severity = request.args.get('severity', '')
        limit = int(request.args.get('limit', 100))
        
        db_service = DatabaseService(database)
        
        vulnerabilities = db_service.get_vulnerabilities(
            ip_filter=query if query else None,
            severity_filter=severity if severity else None,
            limit=limit
        )
        
        # Преобразуем в формат для JSON
        results = []
        for vuln in vulnerabilities:
            vuln_dict = vuln.to_dict()
            vuln_dict['timestamp'] = format_datetime(vuln_dict['timestamp'])
            results.append(vuln_dict)
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results)
        })
        
    except Exception as e:
        logger.error(f"Ошибка поиска уязвимостей: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vulnerabilities_bp.route('/export/<format>')
@login_required
def export_vulnerabilities(format):
    """Экспорт уязвимостей в различных форматах"""
    try:
        database = request.args.get('database', 'belarus')
        ip_filter = request.args.get('ip', '')
        severity_filter = request.args.get('severity', '')
        
        db_service = DatabaseService(database)
        
        vulnerabilities = db_service.get_vulnerabilities(
            ip_filter=ip_filter if ip_filter else None,
            severity_filter=severity_filter if severity_filter else None,
            limit=10000  # Максимум для экспорта
        )
        
        if format.lower() == 'json':
            # Экспорт в JSON
            vuln_dicts = []
            for vuln in vulnerabilities:
                vuln_dict = vuln.to_dict()
                vuln_dict['timestamp'] = format_datetime(vuln_dict['timestamp'])
                vuln_dicts.append(vuln_dict)
            
            json_data = export_vulnerabilities_to_json(vuln_dicts)
            
            return send_file(
                io.BytesIO(json_data.encode('utf-8')),
                mimetype='application/json',
                as_attachment=True,
                download_name=f'vulnerabilities_{database}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
            )
            
        elif format.lower() == 'csv':
            # Экспорт в CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Заголовки
            headers = [
                'ID', 'IP Address', 'Template Method', 'Connection Method',
                'Severity Level', 'URL', 'Additional Info', 'Source Host ID', 'Timestamp'
            ]
            writer.writerow(headers)
            
            # Данные
            for vuln in vulnerabilities:
                writer.writerow([
                    vuln.id,
                    vuln.ip_address,
                    vuln.template_method,
                    vuln.connection_method,
                    vuln.severity_level,
                    vuln.url,
                    vuln.additional_info,
                    vuln.source_host_id,
                    format_datetime(vuln.timestamp)
                ])
            
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'vulnerabilities_{database}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            )
        
        else:
            return jsonify({
                'success': False,
                'error': 'Неподдерживаемый формат экспорта'
            }), 400
            
    except Exception as e:
        logger.error(f"Ошибка экспорта уязвимостей: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vulnerabilities_bp.route('/api/stats/<database>')
@login_required
def api_database_stats(database):
    """API для получения статистики по конкретной базе данных"""
    try:
        if database not in ['belarus', 'russia', 'kazakhstan']:
            return jsonify({
                'success': False,
                'error': 'Неподдерживаемая база данных'
            }), 400
        
        db_service = DatabaseService(database)
        stats = db_service.get_vulnerability_stats()
        
        return jsonify({
            'success': True,
            'database': database,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики БД {database}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# admin-server/utils/helpers.py - ИСПРАВЛЕННАЯ версия с добавлением отсутствующей функции
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Форматирование даты и времени"""
    if dt is None:
        return "Неизвестно"
    return dt.strftime(format_str)

def format_uptime(seconds: int) -> str:
    """Форматирование времени работы"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин {seconds % 60} сек"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days} дн {hours} ч"

def format_bytes(bytes_value: int) -> str:
    """Форматирование размера в байтах"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def generate_task_id() -> str:
    """Генерация уникального ID задачи"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    hash_suffix = hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:8]
    return f"scan_{timestamp}_{hash_suffix}"

def parse_nuclei_template_info(template_path: str) -> Dict[str, Any]:
    """Парсинг информации из шаблона Nuclei"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем метаданные из YAML заголовка
        if content.startswith('id:'):
            lines = content.split('\n')
            info = {}
            
            for line in lines:
                if line.startswith('id:'):
                    info['id'] = line.split(':', 1)[1].strip()
                elif line.startswith('  name:'):
                    info['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('  severity:'):
                    info['severity'] = line.split(':', 1)[1].strip()
                elif line.startswith('  description:'):
                    info['description'] = line.split(':', 1)[1].strip()
            
            return info
    except Exception:
        pass
    
    return {'id': 'unknown', 'name': 'Unknown Template', 'severity': 'info'}

def calculate_scan_eta(total_ips: int, rate_limit: int, num_servers: int) -> timedelta:
    """Расчет предполагаемого времени сканирования"""
    ips_per_server = total_ips / max(num_servers, 1)
    seconds_per_server = ips_per_server / rate_limit
    
    # Добавляем накладные расходы (инициализация, завершение)
    overhead_seconds = 60  # 1 минута накладных расходов
    
    total_seconds = seconds_per_server + overhead_seconds
    return timedelta(seconds=int(total_seconds))

def export_vulnerabilities_to_json(vulnerabilities: List[Dict[str, Any]]) -> str:
    """Экспорт уязвимостей в JSON"""
    export_data = {
        'export_date': datetime.utcnow().isoformat(),
        'total_count': len(vulnerabilities),
        'vulnerabilities': vulnerabilities
    }
    
    return json.dumps(export_data, indent=2, ensure_ascii=False, default=str)

def import_ip_list_from_file(file_content: str) -> List[str]:
    """Импорт списка IP из файла"""
    from utils.validators import validate_ip_address
    ips = []
    
    for line in file_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            # Пытаемся извлечь IP из строки
            if validate_ip_address(line):
                ips.append(line)
            else:
                # Пытаемся найти IP в строке с помощью регулярного выражения
                import re
                ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                matches = re.findall(ip_pattern, line)
                for match in matches:
                    if validate_ip_address(match):
                        ips.append(match)
    
    return list(set(ips))  # Удаляем дубликаты