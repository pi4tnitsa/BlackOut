from flask import Flask, render_template

def register_routes(app: Flask):
    """Регистрация всех маршрутов приложения"""
    try:
        # Импортируем маршруты
        from .auth import auth_bp
        from .dashboard import dashboard_bp
        from .servers import servers_bp
        from .tasks import tasks_bp
        from .vulnerabilities import vulnerabilities_bp
        
        # Регистрируем blueprints
        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(servers_bp, url_prefix='/servers')
        app.register_blueprint(tasks_bp, url_prefix='/tasks')
        app.register_blueprint(vulnerabilities_bp, url_prefix='/vulnerabilities')
        
        # Обработчики ошибок
        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('error.html', error_message="Страница не найдена"), 404
        
        @app.errorhandler(500)
        def internal_error(error):
            return render_template('error.html', error_message="Внутренняя ошибка сервера"), 500
        
        @app.errorhandler(403)
        def forbidden_error(error):
            return render_template('error.html', error_message="Доступ запрещен"), 403
        
        app.logger.info("Все маршруты успешно зарегистрированы")
        
    except ImportError as e:
        app.logger.error(f"Ошибка импорта маршрутов: {e}")
        # Создаем минимальные маршруты для работоспособности
        create_minimal_routes(app)

def create_minimal_routes(app: Flask):
    """Создание минимальных маршрутов для базовой работоспособности"""
    from flask import redirect, url_for, request, session, flash
    from flask_login import login_user, logout_user, login_required
    from models.server import User
    from config.settings import Config
    
    @app.route('/')
    def index():
        return redirect('/login')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
                user = User(username)
                login_user(user, remember=True)
                flash('Добро пожаловать!', 'success')
                return redirect('/dashboard')
            else:
                flash('Неверные учетные данные', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'info')
        return redirect('/login')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html', 
                             vuln_stats={}, 
                             server_summary={}, 
                             recent_tasks=[], 
                             recent_vulnerabilities=[],
                             total_servers=0)
    
    app.logger.warning("Используются минимальные маршруты")