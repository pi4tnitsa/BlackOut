#!/bin/bash

echo "=== Nuclei Scanner - Быстрая установка ==="

# Проверка ОС
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Этот скрипт работает только на Linux"
    exit 1
fi

# Проверка прав
if [[ $EUID -ne 0 ]]; then
   echo "Запустите с правами root: sudo $0"
   exit 1
fi

echo "Какой компонент установить?"
echo "1) Центральный сервер"
echo "2) Воркер"
echo "3) Всё вместе (тестовая установка)"
read -p "Выберите опцию (1-3): " choice

case $choice in
    1)
        echo "Установка центрального сервера..."
        chmod +x deploy.sh
        ./deploy.sh
        ;;
    2)
        echo "Установка воркера..."
        read -p "IP центрального сервера: " central_ip
        read -p "ID воркера: " worker_id
        read -p "База данных (belarus/russia/kazakhstan): " database
        
        # Запуск установки воркера с параметрами
        chmod +x worker/worker-deploy.sh
        cd worker
        echo "$central_ip" | ./worker-deploy.sh
        ;;
    3)
        echo "Тестовая установка всё в одном..."
        chmod +x deploy.sh
        ./deploy.sh
        
        echo "Установка локального воркера..."
        sleep 5
        chmod +x worker/worker-deploy.sh
        cd worker
        echo "127.0.0.1" | ./worker-deploy.sh
        ;;
    *)
        echo "Неверный выбор"
        exit 1
        ;;
esac

echo "Установка завершена!"