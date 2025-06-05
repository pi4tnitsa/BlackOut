#!/bin/bash

echo "=== Установка недостающих зависимостей ==="

PROJECT_DIR="/opt/nuclei-scanner"
USER="nuclei-admin"

if [ -d "$PROJECT_DIR" ]; then
    echo "Обновление Python зависимостей..."
    sudo -u "$USER" "$PROJECT_DIR/venv/bin/pip" install --upgrade \
        Flask==2.3.3 \
        Flask-Login==0.6.3 \
        psycopg2-binary==2.9.7 \
        paramiko==3.3.1 \
        requests==2.31.0 \
        python-dotenv==1.0.0 \
        redis==4.6.0 \
        PyYAML==6.0.1 \
        Werkzeug==2.3.7 \
        itsdangerous==2.1.2 \
        click==8.1.7 \
        Jinja2==3.1.2 \
        MarkupSafe==2.1.3
    
    echo "✅ Зависимости обновлены"
    
    echo "Перезапуск приложения..."
    supervisorctl restart nuclei-scanner-web
    
    echo "✅ Приложение перезапущено"
else
    echo "❌ Проект не найден в $PROJECT_DIR"
    echo "Сначала запустите основную установку"