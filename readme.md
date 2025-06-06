# Nuclei Scanner - Распределенная система сканирования уязвимостей

## 📋 Описание проекта

Nuclei Scanner - это распределенная система для автоматизированного сканирования уязвимостей с использованием инструмента Nuclei. Система состоит из центрального сервера управления и воркеров, которые выполняют сканирование.

### Основные возможности:
- Распределенное сканирование уязвимостей
- Централизованное управление задачами
- Поддержка множества воркеров
- Веб-интерфейс для управления
- Уведомления в Telegram
- Многобазовая архитектура (поддержка разных регионов)

## 🚀 Требования к системе

### Центральный сервер:
- Ubuntu 24.04 LTS
- 4+ CPU ядер
- 8+ GB RAM
- 50+ GB свободного места
- Доступ к интернету
- Открытые порты: 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Воркер-серверы:
- Ubuntu 24.04 LTS
- 2+ CPU ядер
- 4+ GB RAM
- 20+ GB свободного места
- Доступ к интернету
- Открытый порт 22 (SSH)

## 📦 Установка центрального сервера

1. Подготовка системы:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
sudo apt install -y git curl wget
```

2. Клонирование репозитория:
```bash
git clone https://github.com/your-repo/nuclei-scanner.git
cd nuclei-scanner
```

3. Создание и настройка .env файла:
```bash
# Создаем директорию для приложения
sudo mkdir -p /opt/nuclei-admin
sudo chown -R $USER:$USER /opt/nuclei-admin

# Создаем .env файл
cat > /opt/nuclei-admin/.env << 'EOF'
# Конфигурация Nuclei Scanner
SECRET_KEY='your-secret-key'

# Базы данных
DB_BELARUS=postgresql://nuclei_user:password@localhost:5432/nuclei_belarus
DB_RUSSIA=postgresql://nuclei_user:password@localhost:5433/nuclei_russia
DB_KAZAKHSTAN=postgresql://nuclei_user:password@localhost:5434/nuclei_kazakhstan
CURRENT_DB=belarus

# Аутентификация
ADMIN_USER=admin
ADMIN_PASS=your-secure-password

# SSH настройки для воркеров
SSH_USER=root
SSH_KEY_PATH=/home/nuclei/.ssh/id_rsa

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Настройки приложения
DEBUG=False
PORT=5000
EOF

# Устанавливаем правильные права
sudo chown nuclei:nuclei /opt/nuclei-admin/.env
sudo chmod 600 /opt/nuclei-admin/.env
```

4. Запуск скрипта установки:
```bash
chmod +x deploy-admin.sh
sudo ./deploy-admin.sh
```

5. Проверка установки:
```bash
# Проверка статуса сервисов
sudo systemctl status nuclei-admin
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis-server

# Проверка логов
tail -f /opt/nuclei-admin/logs/gunicorn.log
```

## 🔧 Установка воркеров

1. На каждом воркер-сервере:
```bash
# Установка Nuclei
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest

# Установка зависимостей
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Создание рабочей директории
sudo mkdir -p /opt/nuclei-worker
sudo chown -R $USER:$USER /opt/nuclei-worker
```

2. Копирование файлов воркера:
```bash
# С центрального сервера
scp worker.py nuclei@worker-ip:/opt/nuclei-worker/
```

3. Настройка SSH-ключей:
```bash
# На центральном сервере
sudo cat /home/nuclei/.ssh/id_rsa.pub

# На воркер-сервере
mkdir -p ~/.ssh
echo "public-key-from-central-server" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

4. Запуск воркера:
```bash
cd /opt/nuclei-worker
python3 worker.py --server-url http://central-server-ip --daemon
```

## 🌐 Настройка веб-интерфейса

1. Доступ к веб-интерфейсу:
- URL: http://your-server-ip
- Логин: admin
- Пароль: (установленный в .env)

2. Добавление воркеров:
- Перейдите в раздел "Серверы"
- Нажмите "Добавить сервер"
- Введите IP-адрес и SSH-порт воркера
- Сохраните настройки

3. Создание задачи сканирования:
- Перейдите в раздел "Задачи"
- Нажмите "Создать задачу"
- Укажите цели сканирования
- Выберите шаблоны
- Выберите воркеры
- Установите приоритет
- Сохраните задачу

## 🔍 Мониторинг и обслуживание

### Проверка логов:
```bash
# Логи приложения
tail -f /opt/nuclei-admin/logs/gunicorn.log
tail -f /opt/nuclei-admin/logs/celery.log

# Логи Nginx
tail -f /var/log/nginx/nuclei-admin.access.log
tail -f /var/log/nginx/nuclei-admin.error.log

# Логи воркеров
tail -f /var/log/nuclei-worker.log
```

### Управление сервисами:
```bash
# Перезапуск приложения
sudo supervisorctl restart nuclei-admin

# Перезапуск Nginx
sudo systemctl restart nginx

# Перезапуск базы данных
sudo systemctl restart postgresql
```

### Резервное копирование:
```bash
# Создание бэкапа базы данных
pg_dump -U nuclei_user nuclei_belarus > backup_belarus.sql
pg_dump -U nuclei_user nuclei_russia > backup_russia.sql
pg_dump -U nuclei_user nuclei_kazakhstan > backup_kazakhstan.sql
```

## 🔐 Безопасность

1. Настройка SSL:
```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com
```

2. Настройка файрвола:
```bash
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

3. Регулярное обновление:
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Обновление Nuclei
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
```

## 🐛 Устранение неполадок

### Проблемы с подключением воркеров:
1. Проверьте SSH-ключи
2. Проверьте доступность портов
3. Проверьте логи воркера

### Проблемы с базой данных:
1. Проверьте статус PostgreSQL
2. Проверьте права доступа
3. Проверьте логи PostgreSQL

### Проблемы с веб-интерфейсом:
1. Проверьте статус Nginx
2. Проверьте статус приложения
3. Проверьте логи Nginx и Gunicorn

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи
2. Проверьте документацию
3. Создайте issue в репозитории

## 📝 Лицензия

MIT License. См. файл LICENSE для подробностей.