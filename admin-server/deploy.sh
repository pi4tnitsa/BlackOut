#!/bin/bash
# deploy.sh - Скрипт развертывания центрального сервера - ИСПРАВЛЕННАЯ версия

set -e

echo "=== Развертывание Nuclei Scanner - Центральный сервер ==="

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен запускаться с правами root"
   exit 1
fi

# Переменные
PROJECT_DIR="/opt/nuclei-scanner"
USER="nuclei-admin"
VENV_DIR="$PROJECT_DIR/venv"
DB_NAME_BELARUS="belarus"
DB_NAME_RUSSIA="russia"
DB_NAME_KAZAKHSTAN="kazakhstan"

echo "Обновление системы..."
apt-get update -y
apt-get upgrade -y

echo "Установка системных зависимостей..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    git \
    curl \
    wget \
    unzip \
    supervisor

echo "Создание пользователя $USER..."
if ! id "$USER" &>/dev/null; then
    useradd -m -s /bin/bash "$USER"
    usermod -aG sudo "$USER"
fi

echo "Создание директорий проекта..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "/var/log/nuclei-scanner"

echo "Настройка PostgreSQL..."
# Запуск PostgreSQL
systemctl start postgresql
systemctl enable postgresql

# Создание баз данных и пользователей
sudo -u postgres psql << EOF
-- Создание баз данных если не существуют
SELECT 'CREATE DATABASE $DB_NAME_BELARUS' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME_BELARUS')\gexec
SELECT 'CREATE DATABASE $DB_NAME_RUSSIA' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME_RUSSIA')\gexec
SELECT 'CREATE DATABASE $DB_NAME_KAZAKHSTAN' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME_KAZAKHSTAN')\gexec

-- Создание администратора если не существует
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'admin') THEN
        CREATE USER admin WITH PASSWORD 'admin_password_change_me';
    END IF;
END
\$\$;

-- Предоставление прав администратору
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_BELARUS TO admin;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_RUSSIA TO admin;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_KAZAKHSTAN TO admin;

-- Создание пользователей для воркеров (если не существуют)
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_belarus_1') THEN
        CREATE USER worker_belarus_1 WITH PASSWORD 'worker_password_change_me';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_russia_1') THEN
        CREATE USER worker_russia_1 WITH PASSWORD 'worker_password_change_me';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_kazakhstan_1') THEN
        CREATE USER worker_kazakhstan_1 WITH PASSWORD 'worker_password_change_me';
    END IF;
END
\$\$;

-- Предоставление прав воркерам
GRANT CONNECT ON DATABASE $DB_NAME_BELARUS TO worker_belarus_1;
GRANT CONNECT ON DATABASE $DB_NAME_RUSSIA TO worker_russia_1;
GRANT CONNECT ON DATABASE $DB_NAME_KAZAKHSTAN TO worker_kazakhstan_1;
EOF

# Предоставляем права на таблицы (после их создания)
sudo -u postgres psql -d $DB_NAME_BELARUS << EOF
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO worker_belarus_1;
GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO worker_belarus_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, SELECT, UPDATE ON TABLES TO worker_belarus_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO worker_belarus_1;
EOF

sudo -u postgres psql -d $DB_NAME_RUSSIA << EOF
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO worker_russia_1;
GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO worker_russia_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, SELECT, UPDATE ON TABLES TO worker_russia_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO worker_russia_1;
EOF

sudo -u postgres psql -d $DB_NAME_KAZAKHSTAN << EOF
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO worker_kazakhstan_1;
GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO worker_kazakhstan_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, SELECT, UPDATE ON TABLES TO worker_kazakhstan_1;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO worker_kazakhstan_1;
EOF

echo "Настройка Redis..."
systemctl start redis-server
systemctl enable redis-server

echo "Копирование файлов проекта..."
# Копируем только содержимое admin-server, если мы в корне проекта
if [ -d "admin-server" ]; then
    cp -r admin-server/* "$PROJECT_DIR/"
else
    # Если запускаем из директории admin-server
    cp -r ./* "$PROJECT_DIR/"
fi
chown -R "$USER:$USER" "$PROJECT_DIR"

echo "Создание виртуального окружения Python..."
sudo -u "$USER" python3 -m venv "$VENV_DIR"
sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip

echo "Установка Python зависимостей..."
sudo -u "$USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "Создание конфигурационного файла .env..."
cat > "$PROJECT_DIR/.env" << EOF
# База данных
DB_HOST=localhost
DB_PORT=5432
DB_RUSSIA=russia
DB_BELARUS=belarus
DB_KAZAKHSTAN=kazakhstan
DB_ADMIN_USER=admin
DB_ADMIN_PASSWORD=admin_password_change_me

# Flask приложение
FLASK_SECRET_KEY=$(openssl rand -hex 32)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin_password_change_me

# Telegram (настройте свои значения)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Redis
REDIS_URL=redis://localhost:6379/0

# SSH для управления воркерами (настройте свои значения)
SSH_USERNAME=root
SSH_KEY_PATH=/home/$USER/.ssh/id_rsa
SSH_PASSWORD=

# Nuclei пути
NUCLEI_TEMPLATES_PATH=/opt/nuclei-templates
CUSTOM_TEMPLATES_PATH=/opt/custom-templates
EOF

chown "$USER:$USER" "$PROJECT_DIR/.env"
chmod 600 "$PROJECT_DIR/.env"

echo "Создание SSH ключей для управления воркерами..."
sudo -u "$USER" mkdir -p "/home/$USER/.ssh"
if [ ! -f "/home/$USER/.ssh/id_rsa" ]; then
    sudo -u "$USER" ssh-keygen -t rsa -b 4096 -f "/home/$USER/.ssh/id_rsa" -N ""
fi

echo "Инициализация базы данных..."
cd "$PROJECT_DIR"
sudo -u "$USER" "$VENV_DIR/bin/python" -c "
from app import create_app
app = create_app()
with app.app_context():
    print('База данных инициализирована')
"

echo "Настройка Supervisor для управления процессами..."
cat > /etc/supervisor/conf.d/nuclei-scanner.conf << EOF
[program:nuclei-scanner-web]
command=$VENV_DIR/bin/python app.py
directory=$PROJECT_DIR
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/nuclei-scanner/web.err.log
stdout_logfile=/var/log/nuclei-scanner/web.out.log
environment=PATH="$VENV_DIR/bin"

[program:nuclei-scanner-monitor]
command=$VENV_DIR/bin/python -c "
import time
import os
os.environ.setdefault('FLASK_ENV', 'production')
try:
    from services.server_monitor import ServerMonitor
    from services.ssh_service import SSHService
    monitor = ServerMonitor()
    ssh_service = SSHService(
        ssh_username=os.getenv('SSH_USERNAME', 'root'),
        ssh_key_path=os.getenv('SSH_KEY_PATH'),
        ssh_password=os.getenv('SSH_PASSWORD')
    )
    monitor.set_ssh_service(ssh_service)
    monitor.start_monitoring()
    while True:
        time.sleep(60)
except Exception as e:
    print(f'Ошибка мониторинга: {e}')
    time.sleep(60)
"
directory=$PROJECT_DIR
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/nuclei-scanner/monitor.err.log
stdout_logfile=/var/log/nuclei-scanner/monitor.out.log
environment=PATH="$VENV_DIR/bin"
EOF

echo "Настройка Nginx..."
cat > /etc/nginx/sites-available/nuclei-scanner << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias $PROJECT_DIR/web/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf /etc/nginx/sites-available/nuclei-scanner /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

echo "Создание директорий для шаблонов..."
mkdir -p /opt/nuclei-templates
mkdir -p /opt/custom-templates
chown -R "$USER:$USER" /opt/nuclei-templates /opt/custom-templates

echo "Установка Nuclei (для тестирования шаблонов)..."
if ! command -v go &> /dev/null; then
    cd /tmp
    wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
    echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
    source /etc/profile
fi

export PATH=$PATH:/usr/local/go/bin
if ! command -v nuclei &> /dev/null; then
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
    ln -sf /root/go/bin/nuclei /usr/local/bin/nuclei
fi

# Обновление шаблонов Nuclei
nuclei -update-templates

echo "Настройка файрвола (UFW)..."
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 5432/tcp  # PostgreSQL для воркеров

echo "Запуск сервисов..."
systemctl restart supervisor
systemctl enable supervisor
systemctl restart nginx
systemctl enable nginx

supervisorctl reread
supervisorctl update
supervisorctl start all

echo "Настройка логротации..."
cat > /etc/logrotate.d/nuclei-scanner << EOF
/var/log/nuclei-scanner/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        supervisorctl restart nuclei-scanner-web nuclei-scanner-monitor
    endscript
}
EOF

echo "=== Установка завершена ==="
echo ""
echo "Центральный сервер Nuclei Scanner установлен и запущен!"
echo ""
echo "Доступ к веб-интерфейсу: http://$(hostname -I | awk '{print $1}')"
echo "Логин: admin"
echo "Пароль: admin_password_change_me"
echo ""
echo "ВАЖНО! Обязательно измените пароли в файле $PROJECT_DIR/.env"
echo ""
echo "Файлы логов:"
echo "  - Веб-приложение: /var/log/nuclei-scanner/web.out.log"
echo "  - Мониторинг: /var/log/nuclei-scanner/monitor.out.log"
echo ""
echo "Команды управления:"
echo "  - Просмотр статуса: supervisorctl status"
echo "  - Перезапуск веб: supervisorctl restart nuclei-scanner-web"
echo "  - Просмотр логов: tail -f /var/log/nuclei-scanner/web.out.log"
echo ""
echo "Для настройки воркеров используйте скрипт worker-deploy.sh из директории worker/"