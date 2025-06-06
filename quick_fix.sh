#!/bin/bash

set -e

echo "🔧 Быстрое исправление Nuclei Scanner"
echo "===================================="

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Запустите скрипт с правами root: sudo ./quick-fix.sh"
    exit 1
fi

# Переменные
APP_DIR="/opt/nuclei-admin"
APP_USER="nuclei"
DB_USER="nuclei_user"

# 1. Исправляем проблему с Go и Nuclei
fix_nuclei() {
    print_status "Исправление установки Nuclei..."
    
    # Определяем архитектуру
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) NUCLEI_ARCH="linux_amd64" ;;
        aarch64|arm64) NUCLEI_ARCH="linux_arm64" ;;
        *) print_error "Неподдерживаемая архитектура: $ARCH"; exit 1 ;;
    esac
    
    # Скачиваем и устанавливаем Nuclei напрямую
    NUCLEI_VERSION="v3.1.4"
    NUCLEI_URL="https://github.com/projectdiscovery/nuclei/releases/download/${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION#v}_${NUCLEI_ARCH}.zip"
    
    cd /tmp
    print_status "Скачивание Nuclei ${NUCLEI_VERSION}..."
    curl -L -o nuclei.zip "$NUCLEI_URL" || {
        print_error "Не удалось скачать Nuclei"
        exit 1
    }
    
    unzip -o nuclei.zip
    chmod +x nuclei
    mv nuclei /usr/local/bin/
    rm -f nuclei.zip README.md LICENSE.md
    
    if nuclei -version >/dev/null 2>&1; then
        print_success "Nuclei установлен: $(nuclei -version)"
    else
        print_error "Ошибка установки Nuclei"
        exit 1
    fi
}

# 2. Исправляем базу данных
fix_database() {
    print_status "Исправление базы данных..."
    
    # Проверяем PostgreSQL
    if ! systemctl is-active postgresql >/dev/null 2>&1; then
        print_status "Запуск PostgreSQL..."
        systemctl start postgresql
        systemctl enable postgresql
    fi
    
    # Генерируем новый пароль
    DB_PASSWORD=$(openssl rand -base64 32)
    
    # Создаём пользователя и базы данных
    print_status "Настройка пользователя базы данных..."
    sudo -u postgres psql << EOF
-- Удаляем старого пользователя если есть
DROP USER IF EXISTS $DB_USER;

-- Создаём нового пользователя
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER USER $DB_USER CREATEDB;

-- Удаляем старые базы если есть
DROP DATABASE IF EXISTS nuclei_scanner_belarus;
DROP DATABASE IF EXISTS nuclei_scanner_russia;
DROP DATABASE IF EXISTS nuclei_scanner_kazakhstan;

-- Создаём новые базы данных
CREATE DATABASE nuclei_scanner_belarus OWNER $DB_USER;
CREATE DATABASE nuclei_scanner_russia OWNER $DB_USER;
CREATE DATABASE nuclei_scanner_kazakhstan OWNER $DB_USER;

-- Даём права
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_belarus TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_russia TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE nuclei_scanner_kazakhstan TO $DB_USER;
\q
EOF

    if [ $? -eq 0 ]; then
        print_success "База данных настроена"
        
        # Сохраняем пароль
        echo "DB_PASSWORD=$DB_PASSWORD" > /etc/nuclei-admin.env
        chmod 600 /etc/nuclei-admin.env
        print_success "Пароль сохранён в /etc/nuclei-admin.env"
        
        return 0
    else
        print_error "Ошибка настройки базы данных"
        return 1
    fi
}

# 3. Исправляем .env файл
fix_env_file() {
    print_status "Исправление .env файла..."
    
    # Загружаем пароль
    if [ -f /etc/nuclei-admin.env ]; then
        source /etc/nuclei-admin.env
    else
        print_error "Файл с паролем не найден"
        return 1
    fi
    
    # Генерируем секретный ключ
    SECRET_KEY=$(openssl rand -base64 64)
    
    # Создаём правильный .env файл
    cat > "$APP_DIR/.env" << EOF
# Конфигурация Nuclei Scanner
SECRET_KEY='$SECRET_KEY'

# Базы данных
DB_BELARUS=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_belarus
DB_RUSSIA=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_russia
DB_KAZAKHSTAN=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/nuclei_scanner_kazakhstan
CURRENT_DB=belarus

# Аутентификация
ADMIN_USER=admin
ADMIN_PASS=admin123

# SSH настройки для воркеров
SSH_USER=root
SSH_KEY_PATH=/home/$APP_USER/.ssh/id_rsa

# Telegram уведомления (настройте при необходимости)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Настройки приложения
DEBUG=False
PORT=5000
EOF

    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    
    print_success ".env файл исправлен"
}

# 4. Устанавливаем python-dotenv если не установлен
fix_python_deps() {
    print_status "Проверка Python зависимостей..."
    
    if [ ! -f "$APP_DIR/venv/bin/pip" ]; then
        print_error "Виртуальное окружение не найдено в $APP_DIR/venv"
        return 1
    fi
    
    # Устанавливаем python-dotenv
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install python-dotenv || {
        print_error "Не удалось установить python-dotenv"
        return 1
    }
    
    print_success "Python зависимости проверены"
}

# 5. Тестируем подключение к базе данных
test_database() {
    print_status "Тестирование подключения к базе данных..."
    
    # Загружаем переменные окружения
    source /etc/nuclei-admin.env
    
    # Тестируем подключение
    sudo -u postgres psql -h localhost -U $DB_USER -d nuclei_scanner_belarus -c "SELECT 1;" << EOF
$DB_PASSWORD
EOF

    if [ $? -eq 0 ]; then
        print_success "Подключение к базе данных работает"
        return 0
    else
        print_error "Проблема с подключением к базе данных"
        return 1
    fi
}

# 6. Запускаем тест приложения
test_app() {
    print_status "Тестирование приложения..."
    
    cd "$APP_DIR"
    
    # Тестируем запуск приложения
    sudo -u "$APP_USER" timeout 10 "$APP_DIR/venv/bin/python" -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db

try:
    app = create_app()
    with app.app_context():
        db.create_all()
        print('SUCCESS: Приложение работает')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>/dev/null

    if [ $? -eq 0 ]; then
        print_success "Приложение протестировано успешно"
        return 0
    else
        print_error "Проблема с приложением"
        return 1
    fi
}

# 7. Перезапускаем сервисы
restart_services() {
    print_status "Перезапуск сервисов..."
    
    # Останавливаем supervisor
    supervisorctl stop nuclei-admin 2>/dev/null || true
    
    # Перезапускаем supervisor
    systemctl restart supervisor 2>/dev/null || true
    
    # Обновляем конфигурацию
    supervisorctl reread 2>/dev/null || true
    supervisorctl update 2>/dev/null || true
    
    # Запускаем приложение
    supervisorctl start nuclei-admin 2>/dev/null || true
    
    print_success "Сервисы перезапущены"
}

# Основная функция
main() {
    print_status "Начало исправления..."
    
    # Проверяем наличие директории приложения
    if [ ! -d "$APP_DIR" ]; then
        print_error "Директория $APP_DIR не найдена. Запустите сначала deploy-admin.sh"
        exit 1
    fi
    
    # Выполняем исправления по порядку
    echo
    print_status "1/6 Исправление Nuclei..."
    fix_nuclei
    
    echo
    print_status "2/6 Исправление базы данных..."
    fix_database || {
        print_error "Критическая ошибка с базой данных"
        exit 1
    }
    
    echo
    print_status "3/6 Исправление .env файла..."
    fix_env_file
    
    echo
    print_status "4/6 Проверка Python зависимостей..."
    fix_python_deps
    
    echo
    print_status "5/6 Тестирование базы данных..."
    test_database
    
    echo
    print_status "6/6 Тестирование приложения..."
    test_app
    
    echo
    print_status "Перезапуск сервисов..."
    restart_services
    
    # Финальная информация
    echo
    print_success "Исправление завершено!"
    echo "=================================="
    echo
    echo "🌐 Веб-интерфейс:"
    echo "   • URL: http://$(hostname -I | awk '{print $1}'):5000"
    echo "   • Логин: admin"
    echo "   • Пароль: admin123"
    echo
    echo "🔧 Управление:"
    echo "   • Статус: supervisorctl status nuclei-admin"
    echo "   • Логи: tail -f $APP_DIR/logs/gunicorn.log"
    echo "   • Перезапуск: supervisorctl restart nuclei-admin"
    echo
    echo "📊 База данных:"
    echo "   • Пользователь: $DB_USER"
    echo "   • Пароль: см. /etc/nuclei-admin.env"
    echo
    
    # Проверяем статус
    sleep 3
    if supervisorctl status nuclei-admin 2>/dev/null | grep -q "RUNNING"; then
        print_success "Приложение запущено и работает!"
    else
        print_warning "Приложение может ещё запускаться. Проверьте статус через 30 секунд:"
        echo "           supervisorctl status nuclei-admin"
    fi
}

# Запуск
main "$@"