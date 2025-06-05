# web/routes/__init__.py - Регистрация маршрутов - ИСПРАВЛЕННАЯ версия
from flask import Flask

def register_routes(app: Flask):
    """Регистрация всех маршрутов приложения"""
    try:
        from .auth import auth_bp
        from .dashboard import dashboard_bp
        from .servers import servers_bp
        from .tasks import tasks_bp
        from .vulnerabilities import vulnerabilities_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(servers_bp, url_prefix='/servers')
        app.register_blueprint(tasks_bp, url_prefix='/tasks')
        app.register_blueprint(vulnerabilities_bp, url_prefix='/vulnerabilities')
        
    except ImportError as e:
        app.logger.error(f"Ошибка импорта маршрутов: {e}")
        raise