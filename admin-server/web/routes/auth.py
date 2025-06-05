# web/routes/auth.py - Маршруты авторизации
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from config.settings import Config
from models.server import User
from utils.logger import get_logger

logger = get_logger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    """Главная страница - перенаправление на дашборд"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Проверка учетных данных
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            user = User(username)
            login_user(user, remember=True)
            
            logger.info(f"Успешный вход пользователя: {username}")
            flash('Добро пожаловать в систему управления сканером!', 'success')
            
            # Перенаправление на запрошенную страницу или дашборд
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            logger.warning(f"Неудачная попытка входа: {username}")
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    username = current_user.username if current_user.is_authenticated else 'Unknown'
    logout_user()
    
    logger.info(f"Пользователь вышел из системы: {username}")
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('auth.login'))
