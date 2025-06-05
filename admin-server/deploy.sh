#!/bin/bash

set -e

echo "=== Развертывание Nuclei Scanner - Центральный сервер ==="

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен запускаться с правами root"
   echo "Используйте: sudo ./deploy.sh"
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
    supervisor \
    openssh-server

echo "Создание пользователя $USER..."
if ! id "$USER" &>/dev/null; then
    useradd -m -s /bin/bash "$USER"
    usermod -aG sudo "$USER"
fi

echo "Создание директорий проекта..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/web/static"
mkdir -p "$PROJECT_DIR/web/templates"
mkdir -p "/var/log/nuclei-scanner"

echo "Настройка PostgreSQL..."
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
        CREATE USER admin WITH PASSWORD 'nuclei_admin_pass_2024!';
    END IF;
END
\$\$;

-- Предоставление прав администратору
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_BELARUS TO admin;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_RUSSIA TO admin;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_KAZAKHSTAN TO admin;

-- Создание пользователей для воркеров
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_belarus_1') THEN
        CREATE USER worker_belarus_1 WITH PASSWORD 'worker_belarus_pass_2024!';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_russia_1') THEN
        CREATE USER worker_russia_1 WITH PASSWORD 'worker_russia_pass_2024!';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'worker_kazakhstan_1') THEN
        CREATE USER worker_kazakhstan_1 WITH PASSWORD 'worker_kazakhstan_pass_2024!';
    END IF;
END
\$\$;

-- Предоставление прав воркерам
GRANT CONNECT ON DATABASE $DB_NAME_BELARUS TO worker_belarus_1;
GRANT CONNECT ON DATABASE $DB_NAME_RUSSIA TO worker_russia_1;
GRANT CONNECT ON DATABASE $DB_NAME_KAZAKHSTAN TO worker_kazakhstan_1;
EOF

echo "Настройка Redis..."
systemctl start redis-server
systemctl enable redis-server

echo "Копирование файлов проекта..."
# Копируем только содержимое admin-server
if [ -d "admin-server" ]; then
    cp -r admin-server/* "$PROJECT_DIR/"
else
    echo "Директория admin-server не найдена. Копируем текущую директорию."
    cp -r ./* "$PROJECT_DIR/" 2>/dev/null || true
fi
chown -R "$USER:$USER" "$PROJECT_DIR"

echo "Создание виртуального окружения Python..."
sudo -u "$USER" python3 -m venv "$VENV_DIR"
sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip

echo "Установка Python зависимостей..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    sudo -u "$USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
else
    echo "Файл requirements.txt не найден. Устанавливаем базовые зависимости..."
    sudo -u "$USER" "$VENV_DIR/bin/pip" install Flask==2.3.3 Flask-Login==0.6.3 psycopg2-binary==2.9.7 paramiko==3.3.1 requests==2.31.0 python-dotenv==1.0.0 redis==4.6.0 PyYAML==6.0.1
fi

echo "Создание конфигурационного файла .env..."
cat > "$PROJECT_DIR/.env" << EOF
# База данных
DB_HOST=localhost
DB_PORT=5432
DB_RUSSIA=russia
DB_BELARUS=belarus
DB_KAZAKHSTAN=kazakhstan
DB_ADMIN_USER=admin
DB_ADMIN_PASSWORD=nuclei_admin_pass_2024!

# Flask приложение
FLASK_SECRET_KEY=$(openssl rand -hex 32)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=nuclei_admin_2024!

# Telegram (настройте свои значения)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Redis
REDIS_URL=redis://localhost:6379/0

# SSH для управления воркерами
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

echo "Создание базового CSS файла..."
mkdir -p "$PROJECT_DIR/web/static"
cat > "$PROJECT_DIR/web/static/style.css" << 'EOF'
/* Основные стили для Nuclei Scanner */
.sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: 100;
    padding: 48px 0 0;
    box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
}

.sidebar-sticky {
    position: relative;
    top: 0;
    height: calc(100vh - 48px);
    padding-top: .5rem;
    overflow-x: hidden;
    overflow-y: auto;
}

.severity-critical { color: #dc3545; font-weight: bold; }
.severity-high { color: #fd7e14; font-weight: bold; }
.severity-medium { color: #ffc107; font-weight: bold; }
.severity-low { color: #20c997; }
.severity-info { color: #0dcaf0; }

.status-online { color: #198754; }
.status-offline { color: #dc3545; }
.status-unknown { color: #6c757d; }
EOF

echo "Инициализация базы данных..."
cd "$PROJECT_DIR"
sudo -u "$USER" "$VENV_DIR/bin/python" -c "
import sys
sys.path.append('.')
try:
    from app import create_app
    app = create_app()
    with app.app_context():
        print('База данных инициализирована успешно')
except Exception as e:
    print(f'Ошибка инициализации БД: {e}')
"

echo "Предоставление прав воркерам на таблицы..."
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

echo "Установка Go и Nuclei..."
if ! command -v go &> /dev/null; then
    cd /tmp
    wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
    echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
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
ufw allow 5432/tcp

echo "Запуск сервисов..."
systemctl restart supervisor
systemctl enable supervisor
systemctl restart nginx
systemctl enable nginx

supervisorctl reread
supervisorctl update
supervisorctl start nuclei-scanner-web

echo "Создание скрипта мониторинга..."
cat > /opt/nuclei-scanner/monitoring.sh << 'EOF'
#!/bin/bash
echo "=== Статус сервисов Nuclei Scanner ==="
echo "PostgreSQL: $(systemctl is-active postgresql)"
echo "Redis: $(systemctl is-active redis)"
echo "Nginx: $(systemctl is-active nginx)"
echo "Supervisor: $(systemctl is-active supervisor)"
echo ""
echo "=== Процессы Supervisor ==="
supervisorctl status
echo ""
echo "=== Последние логи ==="
tail -5 /var/log/nuclei-scanner/web.out.log 2>/dev/null || echo "Логи недоступны"
EOF

chmod +x /opt/nuclei-scanner/monitoring.sh

echo "=== Установка завершена ==="
echo ""
echo "🎉 Nuclei Scanner центральный сервер установлен!"
echo ""
echo "📊 Доступ к системе:"
echo "  URL: http://$(hostname -I | awk '{print $1}')"
echo "  Логин: admin"
echo "  Пароль: nuclei_admin_2024!"
echo ""
echo "🔧 Управление:"
echo "  Статус: supervisorctl status"
echo "  Мониторинг: /opt/nuclei-scanner/monitoring.sh"
echo "  Логи: tail -f /var/log/nuclei-scanner/web.out.log"
echo ""
echo "⚠️ ВАЖНО:"
echo "  1. Измените пароли в файле /opt/nuclei-scanner/.env"
echo "  2. Настройте Telegram бота (если нужно)"
echo "  3. Для установки воркеров используйте worker-deploy.sh"
echo ""
echo "🔐 Пароли по умолчанию:"
echo "  Admin БД: nuclei_admin_pass_2024!"
echo "  Worker Belarus: worker_belarus_pass_2024!"
echo "  Worker Russia: worker_russia_pass_2024!"
echo "  Worker Kazakhstan: worker_kazakhstan_pass_2024!"
echo ""
