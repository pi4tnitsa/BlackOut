# Nuclei Scanner - Распределённая система сканирования уязвимостей

Система автоматического сканирования уязвимостей с централизованным управлением и горизонтальным масштабированием на основе инструмента Nuclei.

## 🚀 Возможности

- **Центральное управление** через веб-интерфейс
- **Горизонтальное масштабирование** воркер-узлов
- **Многобазовая архитектура** (Беларусь, Россия, Казахстан)
- **Асинхронная обработка** задач с очередями
- **Telegram уведомления** о критичных уязвимостях
- **Автоматическое распределение нагрузки**
- **Мониторинг в реальном времени**

## 🏗️ Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Центральный    │    │    Воркер 1     │    │    Воркер 2     │
│    сервер       │◄──►│                 │    │                 │
│  (Flask + DB)   │    │ Nuclei Scanner  │    │ Nuclei Scanner  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Компоненты системы:

1. **Центральный сервер** - Flask приложение с веб-интерфейсом
2. **Воркер-узлы** - Автономные сканеры на базе Nuclei
3. **Базы данных** - PostgreSQL с географическим разделением
4. **Веб-интерфейс** - Bootstrap 5 + современный дизайн

## 📋 Требования

### Центральный сервер:
- Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- Python 3.9+
- PostgreSQL 12+
- Nginx
- 2+ GB RAM
- 20+ GB дискового пространства

### Воркер-узлы:
- Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- Python 3.9+
- 1+ GB RAM
- 10+ GB дискового пространства
- Nuclei v2.9.15+

## 🚀 Быстрый старт

### 1. Развёртывание центрального сервера

```bash
# Клонирование репозитория
git clone <repository-url>
cd nuclei-scanner

# Запуск скрипта установки
chmod +x deploy-admin.sh
sudo ./deploy-admin.sh
```

### 2. Развёртывание воркера

```bash
# На каждом воркер-сервере
chmod +x deploy-worker.sh
sudo ./deploy-worker.sh http://ADMIN_SERVER_IP:5000
```

### 3. Настройка SSH ключей

```bash
# На центральном сервере
sudo cat /home/nuclei/.ssh/id_rsa.pub

# На каждом воркере
sudo nano /home/nuclei/.ssh/authorized_keys
# Вставить публичный ключ администратора
```

### 4. Первый запуск

1. Откройте веб-интерфейс: `http://SERVER_IP`
2. Войдите с логином `admin` / паролем `admin123`
3. Добавьте воркер-серверы в разделе "Серверы"
4. Создайте первую задачу сканирования

## 🔧 Конфигурация

### Переменные окружения (.env)

```bash
# Базы данных
DB_BELARUS=postgresql://user:pass@localhost:5432/nuclei_belarus
DB_RUSSIA=postgresql://user:pass@localhost:5433/nuclei_russia  
DB_KAZAKHSTAN=postgresql://user:pass@localhost:5434/nuclei_kazakhstan

# Аутентификация
ADMIN_USER=admin
ADMIN_PASS=ваш_безопасный_пароль

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SSH настройки
SSH_USER=nuclei
SSH_KEY_PATH=/home/nuclei/.ssh/id_rsa
```

### Настройка Telegram уведомлений

1. Создайте бота через @BotFather
2. Получите токен бота
3. Получите ID чата (можно через @userinfobot)
4. Добавьте в `.env` файл
5. Перезапустите сервис

## 📊 Использование

### Создание задачи сканирования

1. Перейдите в раздел "Задачи сканирования"
2. Нажмите "Создать задачу"
3. Укажите:
   - Название задачи
   - Целевые IP адреса (поддерживаются форматы: IP, CIDR, диапазоны)
   - Шаблоны сканирования
   - Серверы для выполнения
   - Приоритет задачи

### Форматы целевых адресов

```bash
# Одиночные IP
192.168.1.1
10.0.0.1

# CIDR блоки  
192.168.1.0/24
10.0.0.0/16

# Диапазоны
192.168.1.1-192.168.1.100
10.0.0.1-10.0.0.254
```

### Мониторинг результатов

- **Панель управления** - общая статистика и метрики
- **Уязвимости** - детальный просмотр найденных уязвимостей
- **Серверы** - состояние и мониторинг воркер-узлов
- **Задачи** - прогресс выполнения сканирований

## 🛠️ Управление сервисами

### Центральный сервер

```bash
# Статус сервиса
sudo supervisorctl status nuclei-admin

# Перезапуск
sudo supervisorctl restart nuclei-admin

# Логи
sudo tail -f /opt/nuclei-admin/logs/gunicorn.log

# Обновление
cd /opt/nuclei-admin
sudo -u nuclei git pull
sudo supervisorctl restart nuclei-admin
```

### Воркер-узлы

```bash
# Статус
sudo supervisorctl status nuclei-worker

# Диагностика
sudo /opt/nuclei-worker/diagnostics.sh

# Обновление шаблонов
sudo /opt/nuclei-worker/update.sh

# Логи
sudo tail -f /opt/nuclei-worker/logs/supervisor.log
```

## 🔐 Безопасность

### Рекомендации по безопасности:

1. **Измените пароль администратора** после первого входа
2. **Настройте SSL сертификат** для HTTPS
3. **Ограничьте доступ** к веб-интерфейсу по IP
4. **Используйте VPN** для подключения к воркерам
5. **Регулярно обновляйте** систему и зависимости

### Настройка SSL (опционально)

```bash
# Получение сертификата Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com

# Автообновление сертификата
sudo crontab -e
0 12 * * * /usr/bin/certbot renew --quiet
```

## 📈 Мониторинг и логирование

### Структура логов

```
/opt/nuclei-admin/logs/
├── gunicorn.log          # Основные логи приложения
├── celery.log           # Логи фоновых задач
└── nginx.access.log     # Логи веб-сервера

/opt/nuclei-worker/logs/
├── supervisor.log       # Логи воркера
├── worker.log          # Детальные логи сканирования
└── monitor.log         # Логи мониторинга
```

### Метрики системы

- Количество уязвимостей по критичности
- Статус воркер-узлов (онлайн/оффлайн)
- Прогресс выполнения задач
- Производительность сканирования

## 🔄 Обновление

### Обновление центрального сервера

```bash
cd /opt/nuclei-admin
sudo supervisorctl stop nuclei-admin
sudo -u nuclei git pull
sudo -u nuclei /opt/nuclei-admin/venv/bin/pip install -r requirements.txt
sudo supervisorctl start nuclei-admin
```

### Обновление воркеров

```bash
# Автоматическое обновление
sudo /opt/nuclei-worker/update.sh

# Или вручную
sudo supervisorctl stop nuclei-worker
sudo nuclei -update-templates
sudo supervisorctl start nuclei-worker
```

## 🐛 Устранение проблем

### Частые проблемы:

**1. Воркер не подключается к серверу**
```bash
# Проверьте сетевую связность
curl -v http://ADMIN_SERVER:5000

# Проверьте SSH ключи
sudo -u nuclei ssh ADMIN_USER@ADMIN_SERVER
```

**2. Nuclei не найден**
```bash
# Переустановка Nuclei
sudo /opt/nuclei-worker/update.sh
```

**3. База данных недоступна**
```bash
# Проверка статуса PostgreSQL
sudo systemctl status postgresql

# Проверка подключения
sudo -u postgres psql -l
```

**4. Высокая нагрузка на воркер**
```bash
# Мониторинг ресурсов
htop
iotop

# Ограничение параллельных сканирований
nano /opt/nuclei-worker/.env
# MAX_CONCURRENT_SCANS=2
```

## 📚 API документация

### Эндпоинты для воркеров:

```bash
# Отправка heartbeat
POST /api/worker/heartbeat
{
  "server_id": 1,
  "timestamp": "2025-06-06T10:30:00Z",
  "status": "online"
}

# Отправка уязвимости
POST /api/worker/submit_vulnerability
{
  "ip_address": "192.168.1.15",
  "template_id": "CVE-2023-1234",
  "severity_level": "critical",
  "url": "https://192.168.1.15:8080/admin",
  "task_id": 123
}

# Уведомление о завершении задачи
POST /api/worker/task_complete
{
  "task_id": 123,
  "server_id": 1
}
```

## 🤝 Поддержка

### Логи для диагностики:

```bash
# Сбор всех логов
sudo tar czf nuclei-logs-$(date +%Y%m%d).tar.gz \
  /opt/nuclei-admin/logs/ \
  /opt/nuclei-worker/logs/ \
  /var/log/nginx/ \
  /var/log/postgresql/
```

### Контакты:

- 📧 Email: support@example.com
- 💬 Telegram: @nuclei_support
- 🐛 Issues: GitHub Issues

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для деталей.

---

**⚠️ Важно**: Используйте систему только для законного тестирования безопасности собственной инфраструктуры или с явного разрешения владельцев тестируемых систем.