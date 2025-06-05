# app.py - Точка входа приложения - ИСПРАВЛЕННАЯ версия
from flask import Flask
from flask_login import LoginManager
from config.settings import Config
from config.database import init_db
from web.routes import register_routes
from utils.logger import setup_logger

def create_app():
    """Создание и настройка Flask приложения"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
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
    app.run(debug=True, host='0.0.0.0', port=5000)