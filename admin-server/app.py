from flask import Flask
from flask_login import LoginManager
from config.settings import Config
from config.database import init_db
from utils.logger import setup_logger
import os

def create_app():
    """Создание и настройка Flask приложения"""
    app = Flask(__name__, 
                template_folder='web/templates',
                static_folder='web/static')
    app.config.from_object(Config)
    
    # Создаем директории если не существуют
    os.makedirs('logs', exist_ok=True)
    os.makedirs('web/static', exist_ok=True)
    os.makedirs('web/templates', exist_ok=True)
    
    # Настройка логирования
    setup_logger(app)
    
    # Инициализация базы данных
    try:
        init_db(app)
    except Exception as e:
        app.logger.error(f"Ошибка инициализации БД: {e}")
        # Продолжаем работу даже если БД недоступна
    
    # Настройка системы авторизации
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Необходимо войти в систему'
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.server import User
        return User.get(user_id)
    
    # Регистрация маршрутов с обработкой ошибок
    try:
        from web.routes import register_routes
        register_routes(app)
    except Exception as e:
        app.logger.error(f"Ошибка регистрации маршрутов: {e}")
        # Создаем минимальные маршруты
        create_emergency_routes(app)
    
    return app

def create_emergency_routes(app):
    """Создание экстренных маршрутов для минимальной работоспособности"""
    from flask import render_template_string, redirect, request, flash
    from flask_login import login_user, logout_user, login_required
    from models.server import User
    
    @app.route('/')
    def index():
        return redirect('/login')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            
            if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
                user = User(username)
                login_user(user)
                return redirect('/dashboard')
            flash('Неверные данные', 'error')
        
        # Простая форма входа
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head><title>Nuclei Scanner - Вход</title></head>
        <body>
            <h2>Вход в систему</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Логин" required><br><br>
                <input type="password" name="password" placeholder="Пароль" required><br><br>
                <button type="submit">Войти</button>
            </form>
        </body>
        </html>
        ''')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template_string('''
        <h1>Nuclei Scanner Dashboard</h1>
        <p>Система запущена в аварийном режиме.</p>
        <a href="/logout">Выйти</a>
        ''')
    
    @app.route('/logout')
    def logout():
        logout_user()
        return redirect('/login')

if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=5000)
