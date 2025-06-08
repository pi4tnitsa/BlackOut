#!/bin/bash

# Nuclei Controller Installation Script
# Запускать с правами sudo: sudo bash install.sh

set -e

echo "========================================="
echo "   Nuclei Controller Installation"
echo "========================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Пожалуйста, запустите скрипт с правами sudo${NC}"
    exit 1
fi

# Определяем директорию скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Установка системных зависимостей
echo -e "${YELLOW}[1/8] Установка системных пакетов...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv unzip unrar screen git curl

# Создание директории проекта
PROJECT_DIR="/opt/nuclei-controller"
echo -e "${YELLOW}[2/8] Создание директории проекта...${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Копирование файлов проекта
echo -e "${YELLOW}[3/8] Копирование файлов проекта...${NC}"
cp -r $SCRIPT_DIR/* $PROJECT_DIR/ || true
rm -f $PROJECT_DIR/install.sh  # Удаляем сам скрипт установки

# Создание виртуального окружения
echo -e "${YELLOW}[4/8] Создание виртуального окружения Python...${NC}"
python3 -m venv venv
source venv/bin/activate

# Установка Python зависимостей
echo -e "${YELLOW}[5/8] Установка Python пакетов...${NC}"
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy alembic paramiko python-jose[cryptography] \
    python-multipart jinja2 aiofiles psutil bcrypt python-dotenv pydantic-settings \
    sqlalchemy-utils

# Создание структуры директорий
echo -e "${YELLOW}[6/8] Создание структуры проекта...${NC}"
mkdir -p modules static/css static/js templates uploads/templates uploads/targets worker_scripts

# Генерация случайного пароля для админа
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Создание .env файла
echo -e "${YELLOW}[7/8] Создание конфигурации...${NC}"
cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///./nuclei_controller.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
HOST=0.0.0.0
PORT=8000
EOF

# Инициализация базы данных
echo -e "${YELLOW}[8/8] Инициализация базы данных...${NC}"
cd $PROJECT_DIR
cat > init_db.py << EOF
from database import init_db
if __name__ == '__main__':
    init_db()
EOF
$PROJECT_DIR/venv/bin/python3 init_db.py
rm init_db.py

# Создание systemd сервиса
cat > /etc/systemd/system/nuclei-controller.service << EOF
[Unit]
Description=Nuclei Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Запуск сервиса
systemctl daemon-reload
systemctl enable nuclei-controller
systemctl start nuclei-controller

# Получение IP адреса
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Установка завершена!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "Доступ к веб-интерфейсу:"
echo -e "URL: ${YELLOW}http://$IP_ADDRESS:8000${NC}"
echo -e "Логин: ${YELLOW}admin${NC}"
echo -e "Пароль: ${YELLOW}$ADMIN_PASSWORD${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "Управление сервисом:"
echo -e "Статус: ${YELLOW}systemctl status nuclei-controller${NC}"
echo -e "Перезапуск: ${YELLOW}systemctl restart nuclei-controller${NC}"
echo -e "Логи: ${YELLOW}journalctl -u nuclei-controller -f${NC}"
echo -e "${GREEN}=========================================${NC}"