# install.sh - Скрипт установки воркера
#!/bin/bash

# Скрипт установки Nuclei воркера

set -e

echo "=== Установка Nuclei воркера ==="

# Проверяем root права
if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт должен запускаться с правами root"
   exit 1
fi

# Обновляем систему
echo "Обновление системы..."
apt-get update -y
apt-get upgrade -y

# Устанавливаем зависимости
echo "Установка зависимостей..."
apt-get install -y python3 python3-pip python3-venv git curl wget unzip

# Устанавливаем Go
echo "Установка Go..."
if ! command -v go &> /dev/null; then
    cd /tmp
    wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz
    tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
    echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
    source /etc/profile
fi

# Устанавливаем Nuclei
echo "Установка Nuclei..."
export PATH=$PATH:/usr/local/go/bin
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
ln -sf /root/go/bin/nuclei /usr/local/bin/nuclei

# Обновляем шаблоны Nuclei
echo "Обновление шаблонов Nuclei..."
nuclei -update-templates

# Создаем пользователя для воркера
echo "Создание пользователя nuclei-worker..."
if ! id "nuclei-worker" &>/dev/null; then
    useradd -m -s /bin/bash nuclei-worker
fi

# Создаем директории
echo "Создание директорий..."
mkdir -p /opt/nuclei-worker
mkdir -p /opt/custom-templates
mkdir -p /var/log/nuclei-worker

# Устанавливаем Python зависимости
echo "Установка Python зависимостей..."
cd /opt/nuclei-worker
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install psycopg2-binary PyYAML requests python-dotenv

# Копируем файлы воркера
echo "Копирование файлов воркера..."
# Здесь должно быть копирование файлов проекта

# Устанавливаем права доступа
echo "Настройка прав доступа..."
chown -R nuclei-worker:nuclei-worker /opt/nuclei-worker
chown -R nuclei-worker:nuclei-worker /opt/custom-templates
chown -R nuclei-worker:nuclei-worker /var/log/nuclei-worker

# Создаем systemd сервис
echo "Создание systemd сервиса..."
cat > /etc/systemd/system/nuclei-worker.service << EOF
[Unit]
Description=Nuclei Worker Service
After=network.target

[Service]
Type=simple
User=nuclei-worker
Group=nuclei-worker
WorkingDirectory=/opt/nuclei-worker
Environment=PATH=/opt/nuclei-worker/venv/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/nuclei-worker/venv/bin/python worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd и запускаем сервис
echo "Настройка автозапуска..."
systemctl daemon-reload
systemctl enable nuclei-worker.service

echo "=== Установка завершена ==="
echo "Для запуска воркера выполните:"
echo "  systemctl start nuclei-worker"
echo ""
echo "Для просмотра логов выполните:"
echo "  journalctl -u nuclei-worker -f"
echo ""
echo "Не забудьте настроить config.yaml с параметрами вашей базы данных!"