from flask import render_template, jsonify, request
from utils.logger import get_logger

logger = get_logger(__name__)

def register_error_handlers(app):
    """Регистрация обработчиков ошибок"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 ошибка: {request.url}")
        if request.is_json:
            return jsonify({'error': 'Ресурс не найден'}), 404
        return render_template('error.html', 
                             error_message="Страница не найдена"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 ошибка: {error}")
        if request.is_json:
            return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        return render_template('error.html', 
                             error_message="Внутренняя ошибка сервера"), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        logger.warning(f"403 ошибка: {request.url}")
        if request.is_json:
            return jsonify({'error': 'Доступ запрещен'}), 403
        return render_template('error.html', 
                             error_message="Доступ запрещен"), 403
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.error(f"Необработанная ошибка: {error}", exc_info=True)
        if request.is_json:
            return jsonify({'error': 'Произошла неожиданная ошибка'}), 500
        return render_template('error.html', 
                             error_message="Произошла неожиданная ошибка"), 500
