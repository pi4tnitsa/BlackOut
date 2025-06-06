#!/bin/bash

set -e

echo "=== Развертывание Nuclei Scanner - Воркер ==="

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен запускаться с правами root"
   exit 1
fi

# Интерактивный ввод параметров
if [ -z "$1" ]; then
    read -p "Введите IP-адрес центрального сервера: " CENTRAL_SERVER_IP
else
    CENTRAL_SERVER_IP="$1"
fi

read -p "Введите ID воркера (уникальный номер): " WORKER_ID
read -p "Введите hostname воркера: " WORKER_HOSTNAME
read -p "Выберите базу данных (belarus/russia/kazakhstan): " DATABASE_NAME

# Переменные
PROJECT_DIR="/opt/nuclei-worker"
USER="nuclei-worker"
VENV_DIR="$PROJECT_DIR/venv"

echo "Обновление системы..."
apt-get update -y
apt-get upgrade -y

echo "Установка системных зависимостей..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    unzip \
    supervisor

echo "Создание пользователя $USER..."
if ! id "$USER" &>/dev/null; then
    useradd -m -s /bin/bash "$USER"
fi

echo "Создание директорий проекта..."
mkdir -p "$PROJECT_DIR"
mkdir -p "/var/log/nuclei-worker"

echo "Установка Go..."
if ! command -v go &> /dev/null; then
    cd /tmp
    wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
    echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
    source /etc/profile
fi

echo "Установка Nuclei..."
export PATH=$PATH:/usr/local/go/bin
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
ln -sf /root/go/bin/nuclei /usr/local/bin/nuclei

# Обновление шаблонов
nuclei -update-templates

echo "Копирование файлов воркера..."
# Копируем файлы из worker директории
if [ -d "worker" ]; then
    cp -r worker/* "$PROJECT_DIR/"
else
    echo "Директория worker не найдена!"
    exit 1
fi
chown -R "$USER:$USER" "$PROJECT_DIR"

echo "Создание виртуального окружения Python..."
sudo -u "$USER" python3 -m venv "$VENV_DIR"
sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip

echo "Установка Python зависимостей..."
sudo -u "$USER" "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "Создание конфигурационного файла..."
cat > "$PROJECT_DIR/config.yaml" << EOF
database:
  host: "$CENTRAL_SERVER_IP"
  port: 5432
  name: "$DATABASE_NAME"
  user: "worker_${DATABASE_NAME}_${WORKER_ID}"
  password: "worker_${DATABASE_NAME}_pass_2024!"

worker:
  server_id: $WORKER_ID
  hostname: "$WORKER_HOSTNAME"
  check_interval: 30
  max_concurrent_scans: 3

nuclei:
  binary_path: "/usr/local/bin/nuclei"
  templates_path: "/opt/custom-templates"
  rate_limit: 100
  timeout: 30
  retries: 2
  threads: 50

logging:
  level: "INFO"
  file: "/var/log/nuclei-worker/worker.log"
  max_size_mb: 100
  backup_count: 5
EOF

chown "$USER:$USER" "$PROJECT_DIR/config.yaml"

echo "Создание директории для кастомных шаблонов..."
mkdir -p /opt/custom-templates
chown -R "$USER:$USER" /opt/custom-templates

echo "Настройка Supervisor..."
cat > /etc/supervisor/conf.d/nuclei-worker.conf << EOF
[program:nuclei-worker]
command=$VENV_DIR/bin/python worker.py
directory=$PROJECT_DIR
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/nuclei-worker/worker.err.log
stdout_logfile=/var/log/nuclei-worker/worker.out.log
environment=PATH="$VENV_DIR/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"
EOF

echo "Настройка логротации..."
cat > /etc/logrotate.d/nuclei-worker << EOF
/var/log/nuclei-worker/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        supervisorctl restart nuclei-worker
    endscript
}
EOF

echo "Запуск сервисов..."
systemctl restart supervisor
systemctl enable supervisor

supervisorctl reread
supervisorctl update
supervisorctl start nuclei-worker

echo "=== Установка воркера завершена ==="
echo ""
echo "🎉 Воркер Nuclei Scanner установлен и запущен!"
echo ""
echo "📊 Конфигурация:"
echo "  Центральный сервер: $CENTRAL_SERVER_IP"
echo "  ID воркера: $WORKER_ID"
echo "  Hostname: $WORKER_HOSTNAME"
echo "  База данных: $DATABASE_NAME"
echo ""
echo "🔧 Команды управления:"
echo "  Статус: supervisorctl status nuclei-worker"
echo "  Перезапуск: supervisorctl restart nuclei-worker"
echo "  Логи: tail -f /var/log/nuclei-worker/worker.out.log"
echo ""
echo "⚠️ ВАЖНО!"
echo "1. Убедитесь, что пароль БД совпадает с настройками центрального сервера"
echo "2. Добавьте этот сервер через веб-интерфейс центрального сервера"
echo "3. Проверьте подключение: tail -f /var/log/nuclei-worker/worker.out.log"