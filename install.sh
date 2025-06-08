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

# Установка системных зависимостей
echo -e "${YELLOW}[1/7] Установка системных пакетов...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv unzip unrar screen git curl

# Создание директории проекта
PROJECT_DIR="/opt/nuclei-controller"
echo -e "${YELLOW}[2/7] Создание директории проекта...${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Создание виртуального окружения
echo -e "${YELLOW}[3/7] Создание виртуального окружения Python...${NC}"
python3 -m venv venv
source venv/bin/activate

# Установка Python зависимостей
echo -e "${YELLOW}[4/7] Установка Python пакетов...${NC}"
pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy alembic paramiko python-jose[cryptography] \
    python-multipart jinja2 aiofiles psutil bcrypt python-dotenv

# Создание структуры директорий
echo -e "${YELLOW}[5/7] Создание структуры проекта...${NC}"
mkdir -p modules static/css static/js templates uploads/templates uploads/targets worker_scripts

# Генерация случайного пароля для админа
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Создание .env файла
echo -e "${YELLOW}[6/7] Создание конфигурации...${NC}"
cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///./nuclei_controller.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
HOST=0.0.0.0
PORT=8000
EOF

# Инициализация базы данных и запуск
echo -e "${YELLOW}[7/7] Инициализация базы данных...${NC}"
python3 -c "
import sys
sys.path.append('.')
from database import init_db
init_db()
"

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