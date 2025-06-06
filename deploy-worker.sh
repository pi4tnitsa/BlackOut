#!/bin/bash
# -*- coding: utf-8 -*-
# Скрипт деплоя воркера Nuclei Scanner
# Использование: ./deploy-worker.sh [ADMIN_SERVER_URL]

set -e

echo "🔧 Развёртывание Nuclei Scanner - Воркер"
echo "======================================="

# Переменные конфигурации
WORKER_DIR="/opt/nuclei-worker"
WORKER_USER="nuclei"
NUCLEI_VERSION="v3.4.4"
TEMPLATES_DIR="/opt/nuclei-templates"

# URL администраторского сервера (можно передать как аргумент)
ADMIN_SERVER_URL="${1:-http://192.168.1.100:5000}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода сообщений
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

# Определение операционной системы и архитектуры
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

# Определение архитектуры
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        NUCLEI_ARCH="linux_amd64"
        ;;
    aarch64|arm64)
        NUCLEI_ARCH="linux_arm64"
        ;;
    *)
        print_error "Неподдерживаемая архитектура: $ARCH"
        exit 1
        ;;
esac

print_status "Архитектура: $ARCH -> $NUCLEI_ARCH"

# Функция установки пакетов для Debian/Ubuntu
install_packages_debian() {
    print_status "Обновление списка пакетов..."
    apt-get update -qq

    print_status "Установка необходимых пакетов..."
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        wget \
        unzip \
        git \
        supervisor \
        openssh-server \
        cron \
        logrotate \
        htop \
        nmap \
        net-tools
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
        curl \
        wget \
        unzip \
        git \
        supervisor \
        openssh-server \
        cronie \
        logrotate \
        htop \
        nmap \
        net-tools
}

# Создание пользователя воркера
create_worker_user() {
    print_status "Создание пользователя воркера..."
    
    if ! id "$WORKER_USER" &>/dev/null; then
        useradd -r -m -s /bin/bash "$WORKER_USER"
        print_success "Пользователь $WORKER_USER создан"
    else
        print_warning "Пользователь $WORKER_USER уже существует"
    fi
}

# Создание рабочих директорий
setup_directories() {
    print_status "Создание рабочих директорий..."
    
    mkdir -p "$WORKER_DIR"
    mkdir -p "$WORKER_DIR/logs"
    mkdir -p "$WORKER_DIR/results"
    mkdir -p "$TEMPLATES_DIR"
    mkdir -p "/home/$WORKER_USER/.nuclei"
    
    chown -R "$WORKER_USER:$WORKER_USER" "$WORKER_DIR"
    chown -R "$WORKER_USER:$WORKER_USER" "$TEMPLATES_DIR"
    chown -R "$WORKER_USER:$WORKER_USER" "/home/$WORKER_USER/.nuclei"
    
    print_success "Рабочие директории созданы"
}

# Установка Nuclei
install_nuclei() {
    print_status "Установка Nuclei $NUCLEI_VERSION..."
    
    NUCLEI_URL="https://github.com/projectdiscovery/nuclei/releases/download/$NUCLEI_VERSION/nuclei_${NUCLEI_VERSION#v}_${NUCLEI_ARCH}.zip"
    TEMP_DIR=$(mktemp -d)
    
    # Скачивание Nuclei
    cd "$TEMP_DIR"
    curl -L -o nuclei.zip "$NUCLEI_URL"
    
    # Распаковка и установка
    unzip nuclei.zip
    chmod +x nuclei
    mv nuclei /usr/local/bin/
    
    # Проверка установки
    if nuclei -version >/dev/null 2>&1; then
        print_success "Nuclei успешно установлен: $(nuclei -version)"
    else
        print_error "Ошибка установки Nuclei"
        exit 1
    fi
    
    # Очистка временных файлов
    rm -rf "$TEMP_DIR"
}

# Установка шаблонов Nuclei
install_nuclei_templates() {
    print_status "Установка шаблонов Nuclei..."
    
    # Обновление шаблонов через Nuclei
    sudo -u "$WORKER_USER" nuclei -update-templates -silent
    
    # Альтернативный способ - клонирование репозитория
    if [ ! -d "$TEMPLATES_DIR/.git" ]; then
        print_status "Клонирование репозитория шаблонов..."
        sudo -u "$WORKER_USER" git clone https://github.com/projectdiscovery/nuclei-templates.git "$TEMPLATES_DIR"
    else
        print_status "Обновление репозитория шаблонов..."
        cd "$TEMPLATES_DIR"
        sudo -u "$WORKER_USER" git pull
    fi
    
    print_success "Шаблоны Nuclei установлены"
}

# Установка Python зависимостей
install_python_deps() {
    print_status "Установка Python зависимостей..."
    
    # Создание виртуального окружения
    sudo -u "$WORKER_USER" python3 -m venv "$WORKER_DIR/venv"
    
    # Создание requirements.txt
    cat > "$WORKER_DIR/requirements.txt" << 'EOF'
requests==2.31.0
paramiko==3.3.1
python-dotenv==1.0.0
psutil==5.9.5
schedule==1.2.0
ipaddress==1.0.23
EOF

    # Установка зависимостей
    sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install -r "$WORKER_DIR/requirements.txt"
    
    print_success "Python зависимости установлены"
}

# Копирование скрипта воркера
deploy_worker_script() {
    print_status "Развёртывание скрипта воркера..."
    
    # Копируем скрипт воркера (предполагается, что он находится в текущей директории)
    if [ -f "worker.py" ]; then
        cp worker.py "$WORKER_DIR/"
        chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/worker.py"
        chmod +x "$WORKER_DIR/worker.py"
    else
        print_warning "Файл worker.py не найден в текущей директории"
        print_status "Создаём базовый скрипт воркера..."
        
        # Создаём минимальный скрипт воркера
        cat > "$WORKER_DIR/worker.py" << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем основной класс воркера
# Здесь должен быть импорт из основного файла worker.py

if __name__ == '__main__':
    print("Базовый скрипт воркера. Замените на полную версию.")
EOF
    fi
    
    print_success "Скрипт воркера развёрнут"
}

# Создание конфигурации
setup_config() {
    print_status "Создание конфигурации воркера..."
    
    cat > "$WORKER_DIR/.env" << EOF
# Конфигурация Nuclei Worker
ADMIN_SERVER_URL=$ADMIN_SERVER_URL
WORKER_ID=1
NUCLEI_PATH=/usr/local/bin/nuclei
TEMPLATES_PATH=$TEMPLATES_DIR
RESULTS_PATH=$WORKER_DIR/results

# Логирование
LOG_LEVEL=INFO
LOG_FILE=$WORKER_DIR/logs/worker.log

# Производительность
MAX_CONCURRENT_SCANS=5
SCAN_TIMEOUT=3600
HEARTBEAT_INTERVAL=30

# Самодиагностика
SELF_CHECK_INTERVAL=300
AUTO_RESTART_ON_ERROR=true
EOF

    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/.env"
    chmod 600 "$WORKER_DIR/.env"
    
    print_success "Конфигурация создана"
}

# Настройка SSH
setup_ssh() {
    print_status "Настройка SSH доступа..."
    
    # Создание SSH директории
    SSH_DIR="/home/$WORKER_USER/.ssh"
    sudo -u "$WORKER_USER" mkdir -p "$SSH_DIR"
    sudo -u "$WORKER_USER" chmod 700 "$SSH_DIR"
    
    # Создание authorized_keys файла
    sudo -u "$WORKER_USER" touch "$SSH_DIR/authorized_keys"
    sudo -u "$WORKER_USER" chmod 600 "$SSH_DIR/authorized_keys"
    
    # Настройка SSH daemon
    if ! grep -q "^AllowUsers.*$WORKER_USER" /etc/ssh/sshd_config; then
        echo "AllowUsers root $WORKER_USER" >> /etc/ssh/sshd_config
        systemctl restart sshd
    fi
    
    print_success "SSH настроен"
    print_warning "Добавьте публичный ключ администратора в $SSH_DIR/authorized_keys"
}

# Настройка Supervisor
setup_supervisor() {
    print_status "Настройка Supervisor..."
    
    cat > /etc/supervisor/conf.d/nuclei-worker.conf << EOF
[program:nuclei-worker]
command=$WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --daemon --server-url $ADMIN_SERVER_URL
directory=$WORKER_DIR
user=$WORKER_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$WORKER_DIR/logs/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$WORKER_DIR/venv/bin"

[program:nuclei-worker-updater]
command=$WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --update-templates
directory=$WORKER_DIR
user=$WORKER_USER
autostart=false
autorestart=false
redirect_stderr=true
stdout_logfile=$WORKER_DIR/logs/updater.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
environment=PATH="$WORKER_DIR/venv/bin"
EOF

    # Перезапуск Supervisor
    systemctl restart supervisor
    systemctl enable supervisor
    
    # Обновление конфигурации
    supervisorctl reread
    supervisorctl update
    
    print_success "Supervisor настроен"
}

# Создание systemd сервиса
create_systemd_service() {
    print_status "Создание systemd сервиса..."
    
    cat > /etc/systemd/system/nuclei-worker.service << EOF
[Unit]
Description=Nuclei Scanner Worker
After=network.target

[Service]
Type=simple
User=$WORKER_USER
WorkingDirectory=$WORKER_DIR
Environment=PATH=$WORKER_DIR/venv/bin
ExecStart=$WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --daemon --server-url $ADMIN_SERVER_URL
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable nuclei-worker
    
    print_success "Systemd сервис создан"
}

# Настройка cron задач
setup_cron() {
    print_status "Настройка cron задач..."
    
    # Создание cron задач для пользователя воркера
    cat > /tmp/nuclei-worker-cron << EOF
# Обновление шаблонов каждый день в 3:00
0 3 * * * $WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --update-templates >/dev/null 2>&1

# Самодиагностика каждые 30 минут
*/30 * * * * $WORKER_DIR/venv/bin/python $WORKER_DIR/worker.py --diagnostics >/dev/null 2>&1

# Очистка старых результатов раз в неделю
0 2 * * 0 find $WORKER_DIR/results -name "*.json" -mtime +7 -delete >/dev/null 2>&1
EOF

    sudo -u "$WORKER_USER" crontab /tmp/nuclei-worker-cron
    rm /tmp/nuclei-worker-cron
    
    print_success "Cron задачи настроены"
}

# Настройка логротации
setup_logrotate() {
    print_status "Настройка ротации логов..."
    
    cat > /etc/logrotate.d/nuclei-worker << EOF
$WORKER_DIR/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $WORKER_USER $WORKER_USER
    postrotate
        supervisorctl restart nuclei-worker 2>/dev/null || systemctl restart nuclei-worker
    endscript
}
EOF

    print_success "Логротация настроена"
}

# Настройка мониторинга
setup_monitoring() {
    print_status "Настройка мониторинга..."
    
    # Создание скрипта мониторинга
    cat > "$WORKER_DIR/monitor.sh" << 'EOF'
#!/bin/bash
# Скрипт мониторинга воркера

WORKER_DIR="/opt/nuclei-worker"
LOG_FILE="$WORKER_DIR/logs/monitor.log"

check_nuclei() {
    if ! nuclei -version >/dev/null 2>&1; then
        echo "$(date): ERROR - Nuclei недоступен" >> "$LOG_FILE"
        return 1
    fi
    return 0
}

check_python() {
    if ! "$WORKER_DIR/venv/bin/python" --version >/dev/null 2>&1; then
        echo "$(date): ERROR - Python недоступен" >> "$LOG_FILE"
        return 1
    fi
    return 0
}

check_disk_space() {
    DISK_USAGE=$(df "$WORKER_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo "$(date): WARNING - Диск заполнен на $DISK_USAGE%" >> "$LOG_FILE"
        return 1
    fi
    return 0
}

check_connectivity() {
    if ! curl -s --connect-timeout 5 "$ADMIN_SERVER_URL" >/dev/null; then
        echo "$(date): ERROR - Нет связи с центральным сервером" >> "$LOG_FILE"
        return 1
    fi
    return 0
}

main() {
    echo "$(date): Запуск проверки мониторинга" >> "$LOG_FILE"
    
    ERRORS=0
    
    check_nuclei || ((ERRORS++))
    check_python || ((ERRORS++))
    check_disk_space || ((ERRORS++))
    check_connectivity || ((ERRORS++))
    
    if [ $ERRORS -eq 0 ]; then
        echo "$(date): Все проверки пройдены успешно" >> "$LOG_FILE"
    else
        echo "$(date): Обнаружено $ERRORS ошибок" >> "$LOG_FILE"
        
        # Попытка перезапуска при критических ошибках
        if [ $ERRORS -gt 2 ]; then
            echo "$(date): Критические ошибки - перезапуск сервиса" >> "$LOG_FILE"
            supervisorctl restart nuclei-worker 2>/dev/null || systemctl restart nuclei-worker
        fi
    fi
}

main "$@"
EOF

    chmod +x "$WORKER_DIR/monitor.sh"
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/monitor.sh"
    
    # Добавление в cron
    (sudo -u "$WORKER_USER" crontab -l 2>/dev/null; echo "*/10 * * * * $WORKER_DIR/monitor.sh") | sudo -u "$WORKER_USER" crontab -
    
    print_success "Мониторинг настроен"
}

# Настройка firewall
setup_firewall() {
    print_status "Настройка firewall..."
    
    if command -v ufw >/dev/null 2>&1; then
        # Ubuntu/Debian UFW
        ufw allow ssh
        ufw --force enable
        print_success "UFW firewall настроен"
    elif command -v firewall-cmd >/dev/null 2>&1; then
        # CentOS/RHEL firewalld
        firewall-cmd --permanent --add-service=ssh
        firewall-cmd --reload
        print_success "Firewalld настроен"
    else
        print_warning "Firewall не обнаружен. Настройте вручную порт 22"
    fi
}

# Создание скрипта обновления
create_update_script() {
    print_status "Создание скрипта обновления..."
    
    cat > "$WORKER_DIR/update.sh" << 'EOF'
#!/bin/bash
# Скрипт обновления воркера

WORKER_DIR="/opt/nuclei-worker"
WORKER_USER="nuclei"

echo "🔄 Обновление Nuclei Worker..."

# Остановка сервиса
echo "Остановка сервиса..."
supervisorctl stop nuclei-worker 2>/dev/null || systemctl stop nuclei-worker

# Обновление шаблонов
echo "Обновление шаблонов Nuclei..."
sudo -u "$WORKER_USER" nuclei -update-templates -silent

# Обновление зависимостей Python
echo "Обновление Python зависимостей..."
sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/pip" install --upgrade -r "$WORKER_DIR/requirements.txt"

# Обновление репозитория шаблонов
if [ -d "/opt/nuclei-templates/.git" ]; then
    echo "Обновление репозитория шаблонов..."
    cd /opt/nuclei-templates
    sudo -u "$WORKER_USER" git pull
fi

# Запуск сервиса
echo "Запуск сервиса..."
supervisorctl start nuclei-worker 2>/dev/null || systemctl start nuclei-worker

echo "✅ Обновление завершено"
EOF

    chmod +x "$WORKER_DIR/update.sh"
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/update.sh"
    
    print_success "Скрипт обновления создан"
}

# Создание скрипта диагностики
create_diagnostic_script() {
    print_status "Создание скрипта диагностики..."
    
    cat > "$WORKER_DIR/diagnostics.sh" << 'EOF'
#!/bin/bash
# Скрипт диагностики воркера

WORKER_DIR="/opt/nuclei-worker"

echo "🔍 Диагностика Nuclei Worker"
echo "============================"

# Проверка версии Nuclei
echo "Nuclei версия:"
nuclei -version 2>/dev/null || echo "❌ Nuclei недоступен"

# Проверка Python
echo -e "\nPython версия:"
"$WORKER_DIR/venv/bin/python" --version 2>/dev/null || echo "❌ Python недоступен"

# Проверка дискового пространства
echo -e "\nДисковое пространство:"
df -h "$WORKER_DIR" | tail -1

# Проверка памяти
echo -e "\nИспользование памяти:"
free -h

# Проверка процессов
echo -e "\nПроцессы воркера:"
ps aux | grep -E "(nuclei|worker)" | grep -v grep

# Проверка логов
echo -e "\nПоследние записи в логах:"
if [ -f "$WORKER_DIR/logs/worker.log" ]; then
    tail -5 "$WORKER_DIR/logs/worker.log"
else
    echo "Логи не найдены"
fi

# Проверка связи с админ сервером
echo -e "\nПроверка связи с центральным сервером:"
if [ -f "$WORKER_DIR/.env" ]; then
    ADMIN_URL=$(grep ADMIN_SERVER_URL "$WORKER_DIR/.env" | cut -d'=' -f2)
    if curl -s --connect-timeout 5 "$ADMIN_URL" >/dev/null; then
        echo "✅ Связь с $ADMIN_URL установлена"
    else
        echo "❌ Нет связи с $ADMIN_URL"
    fi
else
    echo "❌ Конфигурация не найдена"
fi

# Проверка шаблонов
echo -e "\nШаблоны Nuclei:"
TEMPLATE_COUNT=$(find /opt/nuclei-templates -name "*.yaml" -o -name "*.yml" 2>/dev/null | wc -l)
echo "Найдено шаблонов: $TEMPLATE_COUNT"

echo -e "\n✅ Диагностика завершена"
EOF

    chmod +x "$WORKER_DIR/diagnostics.sh"
    chown "$WORKER_USER:$WORKER_USER" "$WORKER_DIR/diagnostics.sh"
    
    print_success "Скрипт диагностики создан"
}

# Первоначальная проверка системы
initial_check() {
    print_status "Проверка системных требований..."
    
    # Проверка доступности интернета
    if ! curl -s --connect-timeout 5 google.com >/dev/null; then
        print_warning "Нет подключения к интернету"
    fi
    
    # Проверка свободного места
    DISK_SPACE=$(df / | tail -1 | awk '{print $4}')
    if [ "$DISK_SPACE" -lt 1000000 ]; then  # Менее 1GB
        print_warning "Мало свободного места на диске"
    fi
    
    # Проверка RAM
    TOTAL_RAM=$(free | grep Mem | awk '{print $2}')
    if [ "$TOTAL_RAM" -lt 1000000 ]; then  # Менее 1GB
        print_warning "Мало оперативной памяти"
    fi
    
    print_success "Системные требования проверены"
}

# Проверка сервисов
check_services() {
    print_status "Проверка состояния сервисов..."
    
    echo "SSH: $(systemctl is-active sshd || systemctl is-active ssh)"
    echo "Supervisor: $(systemctl is-active supervisor)"
    echo "Cron: $(systemctl is-active cron || systemctl is-active crond)"
    
    # Проверка воркера
    if supervisorctl status nuclei-worker >/dev/null 2>&1; then
        echo "Nuclei Worker: $(supervisorctl status nuclei-worker | awk '{print $2}')"
    elif systemctl is-active nuclei-worker >/dev/null 2>&1; then
        echo "Nuclei Worker: $(systemctl is-active nuclei-worker)"
    else
        echo "Nuclei Worker: не настроен"
    fi
    
    print_success "Проверка сервисов завершена"
}

# Тестирование воркера
test_worker() {
    print_status "Тестирование воркера..."
    
    # Запуск диагностики
    if [ -f "$WORKER_DIR/worker.py" ]; then
        sudo -u "$WORKER_USER" "$WORKER_DIR/venv/bin/python" "$WORKER_DIR/worker.py" --diagnostics || true
    fi
    
    # Проверка подключения к серверу
    if curl -s --connect-timeout 10 "$ADMIN_SERVER_URL" >/dev/null; then
        print_success "Связь с админ сервером установлена"
    else
        print_warning "Нет связи с админ сервером: $ADMIN_SERVER_URL"
    fi
    
    print_success "Тестирование завершено"
}

# Вывод финальной информации
print_final_info() {
    echo ""
    print_success "Установка Nuclei Worker завершена!"
    echo "====================================="
    echo ""
    echo "📋 Информация о развёртывании:"
    echo "   • Директория воркера: $WORKER_DIR"
    echo "   • Пользователь: $WORKER_USER"
    echo "   • Nuclei версия: $NUCLEI_VERSION"
    echo "   • Админ сервер: $ADMIN_SERVER_URL"
    echo ""
    echo "🔧 Управление сервисом:"
    echo "   • Статус: supervisorctl status nuclei-worker"
    echo "   • Запуск: supervisorctl start nuclei-worker"
    echo "   • Остановка: supervisorctl stop nuclei-worker"
    echo "   • Перезапуск: supervisorctl restart nuclei-worker"
    echo ""
    echo "📊 Мониторинг:"
    echo "   • Логи: tail -f $WORKER_DIR/logs/supervisor.log"
    echo "   • Диагностика: $WORKER_DIR/diagnostics.sh"
    echo "   • Мониторинг: $WORKER_DIR/monitor.sh"
    echo ""
    echo "🔄 Обслуживание:"
    echo "   • Обновление: $WORKER_DIR/update.sh"
    echo "   • Обновление шаблонов: nuclei -update-templates"
    echo ""
    echo "🔑 SSH настройка:"
    echo "   • Добавьте публичный ключ админа в:"
    echo "     /home/$WORKER_USER/.ssh/authorized_keys"
    echo ""
    echo "📈 Следующие шаги:"
    echo "   1. Добавьте SSH ключ администратора"
    echo "   2. Добавьте воркер в админ панели"
    echo "   3. Запустите тестовое сканирование"
    echo ""
    
    # Показать информацию о системе
    echo "💻 Информация о системе:"
    echo "   • Hostname: $(hostname)"
    echo "   • IP адрес: $(hostname -I | awk '{print $1}')"
    echo "   • Архитектура: $ARCH"
    echo "   • ОС: $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
    echo ""
}

# Основная функция
main() {
    print_status "Начало установки Nuclei Worker..."
    
    initial_check
    
    # Установка пакетов в зависимости от ОС
    if [ "$OS" = "debian" ]; then
        install_packages_debian
    elif [ "$OS" = "redhat" ]; then
        install_packages_redhat
    else
        print_error "Неподдерживаемая операционная система"
        exit 1
    fi
    
    create_worker_user
    setup_directories
    install_nuclei
    install_nuclei_templates
    install_python_deps
    deploy_worker_script
    setup_config
    setup_ssh
    setup_supervisor
    create_systemd_service
    setup_cron
    setup_logrotate
    setup_monitoring
    setup_firewall
    create_update_script
    create_diagnostic_script
    check_services
    test_worker
    print_final_info
}

# Обработка ошибок
trap 'print_error "Установка прервана из-за ошибки на строке $LINENO"' ERR

# Проверка аргументов
if [ $# -gt 1 ]; then
    print_error "Использование: $0 [ADMIN_SERVER_URL]"
    exit 1
fi

# Запуск основной функции
main "$@"