# Nuclei Controller - Руководство по развертыванию

## Обзор системы

Nuclei Controller - это веб-система для удаленного управления сканированием уязвимостей с помощью Nuclei на нескольких серверах (воркерах).

### Основные возможности:
- ✅ Автоматическое развертывание через один скрипт
- ✅ Веб-интерфейс для управления
- ✅ Удаленное управление воркерами через SSH
- ✅ Загрузка и распределение шаблонов
- ✅ Мониторинг прогресса сканирования
- ✅ Сбор и анализ результатов
- ✅ Экспорт результатов в CSV/JSON

## Требования

### Главный сервер (Admin Server):
- Ubuntu 20.04+ или Debian 10+
- Python 3.8+
- Минимум 2GB RAM
- 10GB свободного места на диске
- Открытый порт 8000 (или другой для веб-интерфейса)

### Воркеры (Worker Servers):
- Ubuntu 20.04+ или Debian 10+
- SSH доступ с главного сервера
- Минимум 2GB RAM
- 5GB свободного места на диске

## Развертывание

### Шаг 1: Загрузка проекта

```bash
# Клонирование или загрузка проекта
git clone <repository-url> nuclei-controller
cd nuclei-controller

# Или загрузка архива
wget <archive-url> -O nuclei-controller.zip
unzip nuclei-controller.zip
cd nuclei-controller
```

### Шаг 2: Структура файлов

Убедитесь, что все файлы находятся в правильной структуре:

```
nuclei-controller/
├── install.sh
├── requirements.txt
├── config.py
├── database.py
├── main.py
├── modules/
│   ├── __init__.py
│   ├── auth.py
│   ├── worker_manager.py
│   ├── task_manager.py
│   ├── template_manager.py
│   └── result_parser.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── workers.html
│   ├── tasks.html
│   ├── results.html
│   └── templates.html
└── worker_scripts/
    └── setup_worker.sh
```

### Шаг 3: Запуск установки

```bash
# Сделать скрипт исполняемым
chmod +x install.sh

# Запустить установку с правами root
sudo ./install.sh
```

Скрипт автоматически:
- Установит все необходимые зависимости
- Создаст виртуальное окружение Python
- Настроит базу данных
- Создаст администратора с случайным паролем
- Запустит веб-сервер
- Покажет данные для входа

### Шаг 4: Доступ к системе

После успешной установки вы увидите:
```
=========================================
Установка завершена!
=========================================
Доступ к веб-интерфейсу:
URL: http://YOUR_IP:8000
Логин: admin
Пароль: GENERATED_PASSWORD
=========================================
```

Сохраните эти данные!

## Использование системы

### 1. Добавление воркеров

1. Войдите в веб-интерфейс
2. Перейдите в раздел "Workers"
3. Нажмите "Add Worker"
4. Введите:
   - Имя воркера
   - IP адрес
   - SSH порт (обычно 22)
   - Имя пользователя SSH
   - Пароль SSH

Система автоматически:
- Подключится к воркеру
- Установит Nuclei и зависимости
- Создаст рабочие директории

### 2. Загрузка шаблонов

1. Перейдите в раздел "Templates"
2. Нажмите "Upload Template"
3. Выберите RAR или ZIP архив с шаблонами Nuclei
4. Шаблоны автоматически развернутся на всех воркерах

### 3. Создание задачи сканирования

1. Перейдите в раздел "Tasks"
2. Нажмите "Create Task"
3. Заполните:
   - Название задачи
   - Выберите шаблон
   - Загрузите файл с целями (.txt, одна цель на строку)
4. Задача автоматически запустится

### 4. Мониторинг выполнения

- В разделе "Tasks" отображается прогресс
- Нажмите "Logs" для просмотра логов в реальном времени
- Статус обновляется автоматически

### 5. Просмотр результатов

1. Перейдите в раздел "Results"
2. Используйте фильтры для поиска:
   - По уровню серьезности
   - По протоколу
   - По цели
3. Экспортируйте результаты в CSV или JSON

## Управление системой

### Команды systemctl

```bash
# Статус сервиса
sudo systemctl status nuclei-controller

# Перезапуск
sudo systemctl restart nuclei-controller

# Остановка
sudo systemctl stop nuclei-controller

# Запуск
sudo systemctl start nuclei-controller

# Просмотр логов
sudo journalctl -u nuclei-controller -f
```

### Расположение файлов

- Проект: `/opt/nuclei-controller/`
- База данных: `/opt/nuclei-controller/nuclei_controller.db`
- Загруженные файлы: `/opt/nuclei-controller/uploads/`
- Логи: через journalctl

### Резервное копирование

```bash
# Создание резервной копии
sudo tar -czf nuclei-backup-$(date +%Y%m%d).tar.gz \
    /opt/nuclei-controller/nuclei_controller.db \
    /opt/nuclei-controller/uploads \
    /opt/nuclei-controller/.env

# Восстановление
sudo tar -xzf nuclei-backup-YYYYMMDD.tar.gz -C /
sudo systemctl restart nuclei-controller
```

## Безопасность

### Рекомендации:

1. **Смените пароль администратора** после первого входа
2. **Используйте HTTPS** - настройте reverse proxy (nginx/apache)
3. **Ограничьте доступ** - используйте firewall
4. **SSH ключи** - вместо паролей для воркеров
5. **Регулярные обновления** - обновляйте систему и Nuclei

### Настройка HTTPS с Nginx

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Устранение неполадок

### Проблема: Не могу подключиться к воркеру

1. Проверьте SSH доступ: `ssh user@worker-ip`
2. Проверьте firewall на воркере
3. Убедитесь, что учетные данные правильные

### Проблема: Шаблоны не загружаются

1. Проверьте размер файла (макс 100MB)
2. Убедитесь, что это RAR или ZIP архив
3. Проверьте права на директорию uploads

### Проблема: Задача зависла

1. Проверьте статус воркера
2. Посмотрите логи через веб-интерфейс
3. При необходимости остановите задачу

## Обновление системы

```bash
# Резервная копия
sudo tar -czf backup-before-update.tar.gz /opt/nuclei-controller

# Обновление кода
cd /opt/nuclei-controller
sudo git pull  # или загрузите новую версию

# Обновление зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Перезапуск
sudo systemctl restart nuclei-controller
```

## Поддержка

При возникновении проблем:
1. Проверьте логи: `sudo journalctl -u nuclei-controller -f`
2. Проверьте статус: `sudo systemctl status nuclei-controller`
3. Убедитесь, что все зависимости установлены

---

**Важно**: Этот проект предназначен для легального тестирования безопасности. Используйте только на системах, для которых у вас есть разрешение на проведение тестов.