#!/bin/bash

echo "🚀 Nuclei Scanner - Быстрый запуск"
echo "================================="

# Проверка ОС
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Этот скрипт работает только на Linux"
    exit 1
fi

# Проверка прав
if [[ $EUID -ne 0 ]]; then
   echo "❌ Запустите с правами root: sudo $0"
   exit 1
fi

# Проверка наличия скриптов
if [ ! -f "deploy.sh" ]; then
    echo "❌ Файл deploy.sh не найден"
    exit 1
fi

if [ ! -f "worker-deploy.sh" ]; then
    echo "❌ Файл worker-deploy.sh не найден"
    exit 1
fi

echo ""
echo "Выберите режим установки:"
echo "1) 🏢 Центральный сервер (только админка)"
echo "2) 👷 Воркер (подключается к существующему серверу)"
echo "3) 🔧 Всё в одном (тестовая установка)"
echo "4) 🧪 Только тестирование"
echo ""
read -p "Введите номер (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🏢 Установка центрального сервера..."
        echo "===================================="
        chmod +x deploy.sh
        ./deploy.sh
        
        echo ""
        echo "✅ Установка завершена!"
        echo ""
        echo "🌐 Доступ к системе:"
        echo "  URL: http://$(hostname -I | awk '{print $1}')"
        echo "  Логин: admin"
        echo "  Пароль: nuclei_admin_2024!"
        ;;
        
    2)
        echo ""
        echo "👷 Установка воркера..."
        echo "======================"
        read -p "IP центрального сервера: " central_ip
        
        if [ -z "$central_ip" ]; then
            echo "❌ IP центрального сервера обязателен"
            exit 1
        fi
        
        chmod +x worker-deploy.sh
        echo "$central_ip" | ./worker-deploy.sh
        
        echo ""
        echo "✅ Воркер установлен!"
        echo ""
        echo "📋 Следующие шаги:"
        echo "1. Убедитесь, что центральный сервер доступен"
        echo "2. Добавьте воркер через веб-интерфейс"
        echo "3. Проверьте логи: tail -f /var/log/nuclei-worker/worker.out.log"
        ;;
        
    3)
        echo ""
        echo "🔧 Тестовая установка (всё в одном)..."
        echo "====================================="
        
        # Сначала устанавливаем центральный сервер
        chmod +x deploy.sh
        ./deploy.sh
        
        echo ""
        echo "⏳ Ожидание запуска центрального сервера..."
        sleep 10
        
        # Затем устанавливаем локальный воркер
        echo ""
        echo "🔧 Установка локального воркера..."
        chmod +x worker-deploy.sh
        echo -e "127.0.0.1\n1\nlocalhost\nbelarus" | ./worker-deploy.sh
        
        echo ""
        echo "✅ Тестовая установка завершена!"
        echo ""
        echo "🌐 Доступ к системе:"
        echo "  URL: http://localhost"
        echo "  Логин: admin"
        echo "  Пароль: nuclei_admin_2024!"
        echo ""
        echo "📋 Для тестирования:"
        echo "1. Откройте веб-интерфейс"
        echo "2. Создайте задачу сканирования"
        echo "3. Добавьте тестовый IP (например, 127.0.0.1)"
        ;;
        
    4)
        echo ""
        echo "🧪 Запуск тестирования..."
        echo "========================"
        
        if [ -f "test_system.py" ]; then
            python3 test_system.py
        elif [ -f "test_connectivity.py" ]; then
            python3 test_connectivity.py
        else
            echo "❌ Файлы тестирования не найдены"
            exit 1
        fi
        ;;
        
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

echo ""
echo "🎉 Готово! Спасибо за использование Nuclei Scanner!"