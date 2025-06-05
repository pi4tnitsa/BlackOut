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
        
        # Обработчик ошибок
        @app.errorhandler(404)
        def not_found_error(error):
            from flask import render_template
            return render_template('error.html', error_message="Страница не найдена"), 404
        
        @app.errorhandler(500)
        def internal_error(error):
            from flask import render_template
            return render_template('error.html', error_message="Внутренняя ошибка сервера"), 500
        
    except ImportError as e:
        app.logger.error(f"Ошибка импорта маршрутов: {e}")
        raise
