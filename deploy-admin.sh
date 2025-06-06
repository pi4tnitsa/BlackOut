#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт деплоя центрального сервера Nuclei Scanner
# Использование: ./deploy-admin.sh

set -e

echo "🚀 Развёртывание Nuclei Scanner - Центральный сервер"
echo "=================================================="

# Переменные конфигурации
APP_DIR="/opt/nuclei-admin"
APP_USER="nuclei"
DB_NAME="nuclei_scanner"
DB_USER="nuclei_user"
PYTHON_VERSION="3.9"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    print_error "Запустите скрипт с правами root"
    exit 1
fi

# Определение операционной системы
if [ -f /etc/debian_version ]; then
    OS="debian"
    print_status "Обнаружена Debian/Ubuntu система"
elif [ -f /etc/redhat-release ]; then
    OS="redhat"
    print_status "Обнаружена RedHat/CentOS система"
else
    print_warning "Неизвестная операционная система. Продолжаем с настройками по умолчанию..."
    OS="unknown"
fi

# Функция установки пакетов для Debian/Ubuntu
install_packages_debian() {
    print_status "Обновление списка пакетов..."
    apt-get update -qq

    print_status "Установка необходимых пакетов..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        postgresql \
        postgresql-contrib \
        nginx \
        supervisor \
        git \
        curl \
        wget \
        unzip \
        build-essential \
        libpq-dev \
        redis-server
}

# Функция установки пакетов для RedHat/CentOS
install_packages_redhat() {
    print_status "Обновление списка пакетов..."
    yum update -y

    print_status "Установка EPEL репозитория..."
    yum install -y epel-release

    print_status "Установка необходимых пакетов..."
    yum install -y \
        python3 \
        python3-pip \
        python3-devel \
        postgresql-server \
        postgresql-contrib \
        nginx \
        supervisor \
        git \
        curl \
        wget \
        unzip \
        gcc \
        gcc-c++ \
        make \
        postgresql-devel \
        redis
}

# Создание пользователя приложения
create_app_user() {
    print_status "Создание пользователя приложения..."
    
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash "$APP_USER"
        print_success "Пользователь $APP_USER создан"
    else
        print_warning "Пользователь $APP_USER уже существует"
    fi
}

# Настройка PostgreSQL
setup_postgresql() {
    print_status "Настройка PostgreSQL..."
    
    # Инициализация базы данных (для RedHat)
    if [ "$OS" = "redhat" ]; then
        postgresql-setup initdb || true
    fi
    
    # Запуск службы PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Создание базы данных и пользователя
    print_status "Создание базы данных и пользователя..."
    
    # Генерация случайного пароля
    DB_PASSWORD=$(openssl rand -base64 32)
    
    sudo -u postgres psql << EOF
CREATE DATABASE ${DB_NAME}_belarus;
CREATE DATABASE ${DB_NAME}_russia;
CREATE DATABASE ${DB_NAME}_kazakhstan;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME}_belarus TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME}_russia TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME}_kazakhstan TO $DB_USER;
\q
EOF

    # Сохранение данных доступа
    echo "DB_BELARUS=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/${DB_NAME}_belarus" > /etc/nuclei-admin.env
    echo "DB_RUSSIA=postgresql://$DB_USER:$DB_PASSWORD@localhost:5433/${DB_NAME}_russia" >> /etc/nuclei-admin.env
    echo "DB_KAZAKHSTAN=postgresql://$DB_USER:$DB_PASSWORD@localhost:5434/${DB_NAME}_kazakhstan" >> /etc/nuclei-admin.env
    
    print_success "PostgreSQL настроен"
}

# Создание директории приложения
setup_app_directory() {
    print_status "Создание директории приложения..."
    
    mkdir -p "$APP_DIR"
    mkdir -p "$APP_DIR/templates"
    mkdir -p "$APP_DIR/static"
    mkdir -p "$APP_DIR/logs"
    
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    
    print_success "Директория приложения создана: $APP_DIR"
}

# Функция для проверки и создания директорий, переноса файлов
setup_project_structure() {
    print_status "Проверка и создание структуры проекта..."
    
    # Создание основных директорий
    mkdir -p "$APP_DIR/templates"
    mkdir -p "$APP_DIR/static"
    mkdir -p "$APP_DIR/logs"
    mkdir -p "$APP_DIR/static/css"
    mkdir -p "$APP_DIR/static/js"
    mkdir -p "$APP_DIR/static/img"
    
    # Перенос файлов из корня проекта
    if [ -f "app.py" ]; then
        cp app.py "$APP_DIR/"
        chown "$APP_USER:$APP_USER" "$APP_DIR/app.py"
        print_success "Файл app.py перенесен в $APP_DIR"
    fi
    
    if [ -d "templates" ]; then
        cp -r templates/* "$APP_DIR/templates/"
        chown -R "$APP_USER:$APP_USER" "$APP_DIR/templates/"
        print_success "Шаблоны перенесены в $APP_DIR/templates"
    fi
    
    if [ -d "static" ]; then
        cp -r static/* "$APP_DIR/static/"
        chown -R "$APP_USER:$APP_USER" "$APP_DIR/static/"
        print_success "Статические файлы перенесены в $APP_DIR/static"
    fi
    
    # Проверка и создание необходимых файлов
    if [ ! -f "$APP_DIR/templates/base.html" ]; then
        print_warning "Файл base.html не найден в templates"
    fi
    
    if [ ! -f "$APP_DIR/templates/index.html" ]; then
        print_warning "Файл index.html не найден в templates"
    fi
    
    # Создание пустых файлов, если они отсутствуют
    touch "$APP_DIR/logs/gunicorn.log"
    touch "$APP_DIR/logs/celery.log"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR/logs"
    
    print_success "Структура проекта настроена"
}

# Установка Python-зависимостей
install_python_deps() {
    print_status "Установка Python зависимостей..."
    
    # Создание виртуального окружения
    sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
    
    # Создание requirements.txt
    cat > "$APP_DIR/requirements.txt" << 'EOF'
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Werkzeug==2.3.7
paramiko==3.3.1
requests==2.31.0
psycopg2-binary==2.9.7
gunicorn==21.2.0
redis==4.6.0
python-dotenv==1.0.0
celery==5.3.1
ipaddress==1.0.23
EOF

    # Установка зависимостей
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    
    print_success "Python зависимости установлены"
}

# Копирование файлов приложения
deploy_app_files() {
    print_status "Развёртывание файлов приложения..."
    
    # Копируем основной файл приложения (предполагается, что он находится в текущей директории)
    if [ -f "app.py" ]; then
        cp app.py "$APP_DIR/"
        chown "$APP_USER:$APP_USER" "$APP_DIR/app.py"
    else
        print_warning "Файл app.py не найден в текущей директории"
    fi
    
    # Копируем шаблоны
    if [ -d "templates" ]; then
        cp -r templates/* "$APP_DIR/templates/"
        chown -R "$APP_USER:$APP_USER" "$APP_DIR/templates/"
    else
        print_warning "Директория templates не найдена"
    fi
    
    print_success "Файлы приложения развёрнуты"
}

# Настройка конфигурации
setup_config() {
    print_status "Создание конфигурационного файла..."
    
    # Генерация секретного ключа
    SECRET_KEY=$(openssl rand -base64 64)
    
    # Создание .env файла
    cat > "$APP_DIR/.env" << EOF
# Конфигурация Nuclei Scanner
SECRET_KEY='$SECRET_KEY'

# Базы данных
DB_BELARUS=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/${DB_NAME}_belarus
DB_RUSSIA=postgresql://$DB_USER:$DB_PASSWORD@localhost:5433/${DB_NAME}_russia
DB_KAZAKHSTAN=postgresql://$DB_USER:$DB_PASSWORD@localhost:5434/${DB_NAME}_kazakhstan
CURRENT_DB=belarus

# Аутентификация
ADMIN_USER=admin
ADMIN_PASS=admin123

# SSH настройки для воркеров
SSH_USER=root
SSH_KEY_PATH=/home/$APP_USER/.ssh/id_rsa

# Telegram уведомления (заполните при необходимости)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Настройки приложения
DEBUG=False
PORT=5000
EOF

    chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    
    print_success "Конфигурация создана"
}

# Настройка SSH ключей
setup_ssh_keys() {
    print_status "Настройка SSH ключей..."
    
    SSH_DIR="/home/$APP_USER/.ssh"
    
    # Создание SSH директории
    sudo -u "$APP_USER" mkdir -p "$SSH_DIR"
    sudo -u "$APP_USER" chmod 700 "$SSH_DIR"
    
    # Генерация SSH ключа если не существует
    if [ ! -f "$SSH_DIR/id_rsa" ]; then
        sudo -u "$APP_USER" ssh-keygen -t rsa -b 4096 -f "$SSH_DIR/id_rsa" -N ""
        print_success "SSH ключ сгенерирован: $SSH_DIR/id_rsa.pub"
        print_warning "Не забудьте добавить публичный ключ на воркер-серверы!"
        echo "Публичный ключ:"
        cat "$SSH_DIR/id_rsa.pub"
    else
        print_warning "SSH ключ уже существует"
    fi
}

# Настройка Nginx
setup_nginx() {
    print_status "Настройка Nginx..."
    
    # Создание конфигурации Nginx
    cat > /etc/nginx/sites-available/nuclei-admin << 'EOF'
server {
    listen 80;
    server_name _;
    
    # Редирект на HTTPS (раскомментируйте при настройке SSL)
    # return 301 https://$server_name$request_uri;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30;
        proxy_send_timeout 30;
        proxy_read_timeout 30;
    }
    
    location /static {
        alias /opt/nuclei-admin/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Ограничение размера загружаемых файлов
    client_max_body_size 10M;
    
    # Логи
    access_log /var/log/nginx/nuclei-admin.access.log;
    error_log /var/log/nginx/nuclei-admin.error.log;
}

# Конфигурация для HTTPS (раскомментируйте при настройке SSL)
# server {
#     listen 443 ssl http2;
#     server_name _;
#     
#     ssl_certificate /path/to/certificate.crt;
#     ssl_certificate_key /path/to/private.key;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
#     ssl_prefer_server_ciphers off;
#     
#     location / {
#         proxy_pass http://127.0.0.1:5000;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto $scheme;
#     }
# }
EOF

    # Активация сайта
    if [ "$OS" = "debian" ]; then
        ln -sf /etc/nginx/sites-available/nuclei-admin /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
    fi
    
    # Проверка конфигурации
    nginx -t
    
    # Перезапуск Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    print_success "Nginx настроен"
}

# Настройка Supervisor
setup_supervisor() {
    print_status "Настройка Supervisor..."
    
    # Создание конфигурации Supervisor
    cat > /etc/supervisor/conf.d/nuclei-admin.conf << EOF
[program:nuclei-admin]
command=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --worker-class gevent app:app
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/gunicorn.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin"

[program:nuclei-admin-celery]
command=$APP_DIR/venv/bin/celery -A app.celery worker --loglevel=info
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$APP_DIR/logs/celery.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$APP_DIR/venv/bin"
EOF

    # Перезапуск Supervisor
    systemctl restart supervisor
    systemctl enable supervisor
    
    # Обновление конфигурации
    supervisorctl reread
    supervisorctl update
    
    print_success "Supervisor настроен"
}

# Настройка логротации
setup_logrotate() {
    print_status "Настройка ротации логов..."
    
    cat > /etc/logrotate.d/nuclei-admin << EOF
$APP_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $APP_USER $APP_USER
    postrotate
        supervisorctl restart nuclei-admin nuclei-admin-celery
    endscript
}
EOF

    print_success "Логротация настроена"
}

# Настройка firewall
setup_firewall() {
    print_status "Настройка firewall..."
    
    if command -v ufw >/dev/null 2>&1; then
        # Ubuntu/Debian UFW
        ufw allow ssh
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        print_success "UFW firewall настроен"
    elif command -v firewall-cmd >/dev/null 2>&1; then
        # CentOS/RHEL firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        print_success "Firewalld настроен"
    else
        print_warning "Firewall не обнаружен. Настройте вручную порты 22, 80, 443"
    fi
}

# Инициализация базы данных
init_database() {
    print_status "Инициализация базы данных..."
    
    # Запуск приложения для создания таблиц
    cd "$APP_DIR"
    sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c "
from app import app, db
with app.app_context():
    db.create_all()
print('База данных инициализирована')
"
    
    print_success "База данных инициализирована"
}

# Создание systemd сервиса (альтернатива Supervisor)
create_systemd_service() {
    print_status "Создание systemd сервиса..."
    
    cat > /etc/systemd/system/nuclei-admin.service << EOF
[Unit]
Description=Nuclei Scanner Admin Panel
After=network.target postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable nuclei-admin
    
    print_success "Systemd сервис создан"
}

# Проверка состояния сервисов
check_services() {
    print_status "Проверка состояния сервисов..."
    
    echo "PostgreSQL: $(systemctl is-active postgresql)"
    echo "Nginx: $(systemctl is-active nginx)"
    echo "Supervisor: $(systemctl is-active supervisor)"
    echo "Redis: $(systemctl is-active redis-server || systemctl is-active redis)"
    
    print_success "Проверка завершена"
}

# Вывод финальной информации
print_final_info() {
    echo ""
    print_success "Установка Nuclei Scanner завершена!"
    echo "=========================================="
    echo ""
    echo "📋 Информация о развёртывании:"
    echo "   • Директория приложения: $APP_DIR"
    echo "   • Пользователь: $APP_USER"
    echo "   • Конфигурация: $APP_DIR/.env"
    echo "   • Логи: $APP_DIR/logs/"
    echo ""
    echo "🌐 Веб-интерфейс:"
    echo "   • URL: http://$(hostname -I | awk '{print $1}')"
    echo "   • Логин: admin"
    echo "   • Пароль: admin123"
    echo ""
    echo "🔑 SSH ключ для воркеров:"
    echo "   • Публичный ключ: /home/$APP_USER/.ssh/id_rsa.pub"
    echo ""
    echo "🛠️ Управление сервисом:"
    echo "   • Статус: supervisorctl status"
    echo "   • Перезапуск: supervisorctl restart nuclei-admin"
    echo "   • Логи: tail -f $APP_DIR/logs/gunicorn.log"
    echo ""
    echo "🔧 Следующие шаги:"
    echo "   1. Настройте SSH ключи на воркер-серверах"
    echo "   2. Настройте SSL сертификат (опционально)"
    echo "   3. Настройте Telegram уведомления в .env файле"
    echo "   4. Добавьте воркер-серверы через веб-интерфейс"
    echo ""
    print_warning "Не забудьте изменить пароль администратора!"
}

# Основная функция
main() {
    print_status "Начало установки Nuclei Scanner..."
    
    # Установка пакетов в зависимости от ОС
    if [ "$OS" = "debian" ]; then
        install_packages_debian
    elif [ "$OS" = "redhat" ]; then
        install_packages_redhat
    else
        print_error "Неподдерживаемая операционная система"
        exit 1
    fi
    
    create_app_user
    setup_postgresql
    setup_app_directory
    setup_project_structure
    install_python_deps
    deploy_app_files
    setup_config
    setup_ssh_keys
    setup_nginx
    setup_supervisor
    setup_logrotate
    setup_firewall
    init_database
    check_services
    print_final_info
}

# Обработка ошибок
trap 'print_error "Установка прервана из-за ошибки на строке $LINENO"' ERR

# Запуск основной функции
main "$@"