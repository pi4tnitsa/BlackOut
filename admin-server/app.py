from flask import Flask
from flask_login import LoginManager
from config.settings import Config
from config.database import init_db
from web.routes import register_routes
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
    init_db(app)
    
    # Настройка системы авторизации
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Необходимо войти в систему'
    
    @login_manager.user_loader
    def load_user(user_id):
        from models.server import User
        return User.get(user_id)
    
    # Регистрация маршрутов
    register_routes(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=5000)
