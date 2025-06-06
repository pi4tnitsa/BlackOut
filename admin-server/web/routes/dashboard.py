# web/routes/dashboard.py - Исправленная главная панель управления
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from utils.logger import get_logger
from datetime import datetime, timedelta
import os

logger = get_logger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

# Инициализация сервисов с обработкой ошибок
try:
    from services.database_service import DatabaseService
    from services.server_monitor import ServerMonitor
    db_service = DatabaseService()
    server_monitor = ServerMonitor()
except Exception as e:
    logger.error(f"Ошибка инициализации сервисов: {e}")
    db_service = None
    server_monitor = None

@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Главная страница дашборда"""
    try:
        # Получаем статистику уязвимостей
        vuln_stats = {}
        servers = []
        server_summary = {'total_servers': 0, 'online_servers': 0, 'offline_servers': 0}
        recent_tasks = []
        recent_vulnerabilities = []
        
        if db_service:
            try:
                vuln_stats = db_service.get_vulnerability_stats()
                servers = db_service.get_servers()
            except Exception as e:
                logger.error(f"Ошибка получения данных из БД: {e}")
        
        if server_monitor:
            try:
                server_summary = server_monitor.get_monitoring_summary()
            except Exception as e:
                logger.error(f"Ошибка получения статуса серверов: {e}")
        
        if db_service:
            try:
                recent_tasks = db_service.get_tasks()[:10] if db_service else []
                recent_vulnerabilities = db_service.get_vulnerabilities(limit=10) if db_service else []
            except Exception as e:
                logger.error(f"Ошибка получения последних данных: {e}")
        
        context = {
            'vuln_stats': vuln_stats or {},
            'server_summary': server_summary,
            'recent_tasks': recent_tasks,
            'recent_vulnerabilities': recent_vulnerabilities,
            'total_servers': len(servers) if servers else 0,
            'current_time': datetime.utcnow()
        }
        
        return render_template('dashboard.html', **context)
        
    except Exception as e:
        logger.error(f"Ошибка загрузки дашборда: {e}")
        return render_template('dashboard.html', 
                             error="Ошибка загрузки данных",
                             vuln_stats={},
                             server_summary={},
                             recent_tasks=[],
                             recent_vulnerabilities=[],
                             total_servers=0)

@dashboard_bp.route('/api/stats')
@login_required
def api_stats():
    """API для получения статистики в реальном времени"""
    try:
        # Статистика уязвимостей
        vuln_stats = {}
        server_summary = {}
        db_stats = {}
        
        if db_service:
            try:
                vuln_stats = db_service.get_vulnerability_stats()
            except Exception as e:
                logger.error(f"Ошибка получения статистики уязвимостей: {e}")
        
        if server_monitor:
            try:
                server_summary = server_monitor.get_monitoring_summary()
            except Exception as e:
                logger.error(f"Ошибка получения статистики серверов: {e}")
        
        # Статистика по базам данных
        for db_name in ['belarus', 'russia', 'kazakhstan']:
            try:
                from services.database_service import DatabaseService
                db_srv = DatabaseService(db_name)
                db_stats[db_name] = db_srv.get_vulnerability_stats()
            except Exception as e:
                logger.error(f"Ошибка получения статистики БД {db_name}: {e}")
                db_stats[db_name] = {}
        
        return jsonify({
            'success': True,
            'timestamp': datetime.utcnow().isoformat(),
            'vulnerability_stats': vuln_stats,
            'server_stats': server_summary,
            'database_stats': db_stats
        })
        
    except Exception as e:
        logger.error(f"Ошибка API статистики: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dashboard_bp.route('/api/charts/vulnerabilities')
@login_required
def api_vulnerability_charts():
    """API для данных графиков уязвимостей"""
    try:
        if not db_service:
            return jsonify({
                'success': False,
                'error': 'Сервис БД недоступен'
            })
        
        # График по типам уязвимостей за последние 30 дней
        query = """
        SELECT 
            DATE(timestamp) as date,
            severity_level,
            COUNT(*) as count
        FROM vulnerabilities 
        WHERE timestamp >= %s
        GROUP BY DATE(timestamp), severity_level
        ORDER BY date DESC
        """
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        results = db_service.db_manager.execute_query(
            db_service.database_name, 
            query, 
            [thirty_days_ago]
        )
        
        # Преобразуем данные для графика
        chart_data = {}
        for row in results:
            date_str = row['date'].strftime('%Y-%m-%d')
            if date_str not in chart_data:
                chart_data[date_str] = {}
            chart_data[date_str][row['severity_level']] = row['count']
        
        return jsonify({
            'success': True,
            'chart_data': chart_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка API графиков: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
