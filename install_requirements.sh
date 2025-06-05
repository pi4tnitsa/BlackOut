# install_requirements.sh - Установка всех зависимостей
#!/bin/bash

echo "=== Установка зависимостей для Nuclei Scanner ==="

# Проверка ОС
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "Обнаружена система на базе Debian/Ubuntu"
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv postgresql redis-server nginx supervisor
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        echo "Обнаружена система на базе CentOS/RHEL"
        sudo yum update -y
        sudo yum install -y python3 python3-pip postgresql-server redis nginx supervisor
    else
        echo "Неподдерживаемый пакетный менеджер Linux"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "Обнаружена macOS"
    if command -v brew &> /dev/null; then
        brew install python postgresql redis nginx
        brew services start postgresql
        brew services start redis
    else
        echo "Установите Homebrew для macOS: https://brew.sh/"
        exit 1
    fi
else
    echo "Неподдерживаемая операционная система: $OSTYPE"
    exit 1
fi

echo "Создание виртуального окружения Python..."
python3 -m venv venv
source venv/bin/activate

echo "Установка Python зависимостей для центрального сервера..."
pip install --upgrade pip
pip install -r admin-server/requirements.txt

echo "Установка дополнительных инструментов..."
pip install python-dotenv

echo "Создание тестового .env файла..."
if [ ! -f admin-server/.env ]; then
    cp admin-server/.env admin-server/.env.example
    echo "Создан пример .env файла. Настройте его перед запуском!"
fi

echo ""
echo "✅ Установка зависимостей завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Настройте файл admin-server/.env"
echo "2. Запустите тест подключений: python test_connectivity.py"
echo "3. Для полной установки используйте: make install-admin"