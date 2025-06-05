# 🛡️ Nuclei Scanner - Распределённая система сканирования уязвимостей

Комплексная система для автоматического сканирования IP-адресов с использованием кастомных шаблонов Nuclei. Поддерживает масштабирование за счёт подключаемых воркеров с централизованной административной панелью.

## 📋 Оглавление

- [Особенности](#-особенности)
- [Архитектура](#-архитектура)
- [Требования](#-требования)
- [Установка](#-установка)
- [Конфигурация](#-конфигурация)
- [Использование](#-использование)
- [API](#-api)
- [Мониторинг](#-мониторинг)
- [Безопасность](#-безопасность)
- [FAQ](#-faq)

## 🚀 Особенности

### Центральный сервер
- **Веб-панель управления** с современным интерфейсом
- **Распределение задач** по множеству серверов
- **Мониторинг в реальном времени** состояния воркеров
- **SSH управление** удалёнными серверами
- **Telegram уведомления** о критичных уязвимостях
- **Множественные базы данных** (Беларусь, Россия, Казахстан)
- **Экспорт результатов** в JSON/CSV
- **Графики и статистика** в реальном времени

### Воркер-серверы
- **Автономная работа** с очередью задач
- **Автоматическая установка** и обновление Nuclei
- **Масштабируемость** - добавление новых серверов на лету
- **Отказоустойчивость** - автоматический перезапуск при сбоях
- **Гибкая конфигурация** сканирования

### Безопасность
- **Изолированные пользователи БД** для каждого воркера
- **SSH-ключи** для безопасного управления
- **Авторизация** в веб-интерфейсе
- **Полное логирование** всех операций

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    ЦЕНТРАЛЬНЫЙ СЕРВЕР                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Web Panel   │  │ Task        │  │ Server Monitor      │  │
│  │ (Flask)     │  │ Distributor │  │ (SSH Management)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ PostgreSQL  │  │ Redis       │  │ Telegram Bot        │  │
│  │ (3 DBs)     │  │ (Tasks)     │  │ (Notifications)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                               │
                               │ SSH Management
                               │ Task Distribution
                               │
    ┌──────────────────────────┼──────────────────────────┐
    │                          │                          │
    ▼                          ▼                          ▼
┌─────────┐              ┌─────────┐              ┌─────────┐
│ ВОРКЕР 1│              │ ВОРКЕР 2│              │ ВОРКЕР N│
├─────────┤              ├─────────┤              ├─────────┤
│ Nuclei  │              │ Nuclei  │              │ Nuclei  │
│ Runner  │              │ Runner  │              │ Runner  │
│         │              │         │              │         │
│ Result  │              │ Result  │              │ Result  │
│ Upload  │              │ Upload  │              │ Upload  │
└─────────┘              └─────────┘              └─────────┘
```

## 💻 Требования

### Центральный сервер
- **ОС**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM**: минимум 4 ГБ, рекомендуется 8 ГБ
- **Диск**: минимум 50 ГБ SSD
- **CPU**: минимум 2 ядра, рекомендуется 4 ядра
- **Сеть**: статический IP, доступ к воркерам по SSH

### Воркер-серверы
- **ОС**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- **RAM**: минимум 2 ГБ, рекомендуется 4 ГБ
- **Диск**: минимум 20 ГБ
- **CPU**: минимум 1 ядро, рекомендуется 2 ядра
- **Сеть**: доступ к центральному серверу, интернет для сканирования

### Программное обеспечение
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Nginx
- Supervisor
- Go 1.19+ (для Nuclei)

## 🔧 Установка

### Быстрая установка центрального сервера

```bash
# 1. Клонирование репозитория
git clone https://github.com/your-repo/nuclei-scanner.git
cd nuclei-scanner

# 2. Запуск автоматической установки
chmod +x deploy.sh
sudo ./deploy.sh

# 3. Настройка конфигурации
sudo nano /opt/nuclei-scanner/.env
```

### Установка воркера

```bash
# 1. Копирование файлов воркера на целевой сервер
scp -r worker/ root@WORKER_IP:/tmp/

# 2. Подключение к воркеру и установка
ssh root@WORKER_IP
cd /tmp
chmod +x worker-deploy.sh
./worker-deploy.sh

# 3. Настройка SSH ключей (с центрального сервера)
./setup-ssh-keys.sh WORKER_IP root
```

### Ручная установка

<details>
<summary>Развернуть инструкции по ручной установке</summary>

#### Центральный сервер

```bash
# Установка зависимостей
sudo apt update
sudo apt install -y python3 python3-pip postgresql redis-server nginx supervisor

# Создание пользователя
sudo useradd -m nuclei-admin

# Настройка PostgreSQL
sudo -u postgres createdb belarus
sudo -u postgres createdb russia  
sudo -u postgres createdb kazakhstan

# Установка Python зависимостей
cd admin-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Конфигурация
cp .env.example .env
nano .env

# Запуск
python app.py
```

#### Воркер

```bash
# Установка Nuclei
wget https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_2.9.4_linux_amd64.zip
unzip nuclei_2.9.4_linux_amd64.zip
sudo mv nuclei /usr/local/bin/

# Установка Python зависимостей
cd worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Конфигурация
cp config.yaml.example config.yaml
nano config.yaml

# Запуск
python worker.py
```

</details>

## ⚙️ Конфигурация

### Центральный сервер (.env)

```bash
# База данных
DB_HOST=localhost
DB_PORT=5432
DB_ADMIN_USER=admin
DB_ADMIN_PASSWORD=secure_password

# Веб-интерфейс
FLASK_SECRET_KEY=your_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_admin_password

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SSH управление
SSH_USERNAME=root
SSH_KEY_PATH=/home/nuclei-admin/.ssh/id_rsa
```

### Воркер (config.yaml)

```yaml
database:
  host: "192.168.1.100"  # IP центрального сервера
  port: 5432
  name: "belarus"        # belarus/russia/kazakhstan
  user: "worker_belarus_1"
  password: "worker_password"

worker:
  server_id: 1           # Уникальный ID воркера
  hostname: "worker-01"
  check_interval: 30     # Интервал проверки задач (сек)
  max_concurrent_scans: 3

nuclei:
  binary_path: "/usr/local/bin/nuclei"
  templates_path: "/opt/custom-templates"
  rate_limit: 100       # Запросов в секунду
  timeout: 30          # Таймаут соединения
  retries: 2           # Количество повторов
  threads: 50          # Количество потоков

logging:
  level: "INFO"
  file: "/var/log/nuclei-worker/worker.log"
  max_size_mb: 100
  backup_count: 5
```

## 🎯 Использование

### Веб-интерфейс

1. **Доступ к панели**: http://your-server-ip
2. **Авторизация**: admin / your_password
3. **Добавление серверов**: Серверы → Добавить сервер
4. **Создание задач**: Задачи → Создать задачу
5. **Мониторинг**: Дашборд для просмотра статистики

### Создание задачи сканирования

```python
# Пример через веб-интерфейс:
1. Перейти в раздел "Задачи"
2. Нажать "Создать задачу"
3. Ввести название задачи
4. Выбрать базу данных (belarus/russia/kazakhstan)
5. Указать IP-диапазоны:
   - 192.168.1.0/24
   - 10.0.0.1-10.0.0.100
   - 172.16.1.1
6. Выбрать серверы для сканирования
7. Нажать "Создать задачу"
```

### Управление серверами

```bash
# Добавление SSH ключа на новый воркер
./setup-ssh-keys.sh 192.168.1.101 root

# Установка Nuclei на воркер через веб-интерфейс
# Серверы → Выбрать сервер → Кнопка установки

# Обновление шаблонов
# Серверы → Выбрать сервер → Кнопка обновления
```

### Кастомные шаблоны Nuclei

```yaml
# Пример кастомного шаблона (/opt/custom-templates/custom-check.yaml)
id: custom-web-service-check

info:
  name: Custom Web Service Check
  author: your-team
  severity: medium
  description: Проверка кастомного веб-сервиса
  tags: web,custom

requests:
  - method: GET
    path:
      - "{{BaseURL}}/admin"
      - "{{BaseURL}}/api/status"
    
    matchers:
      - type: word
        words:
          - "admin panel"
          - "unauthorized access"
        condition: or
```

## 📡 API

### REST API Endpoints

```bash
# Получение статистики
GET /api/stats
{
  "success": true,
  "vulnerability_stats": {...},
  "server_stats": {...}
}

# Запуск задачи
POST /tasks/api/{task_id}/start
{
  "database": "belarus"
}

# Статус сервера
GET /servers/api/{server_id}/status
{
  "success": true,
  "metrics": {...}
}

# Поиск уязвимостей
GET /vulnerabilities/api/search?q=192.168.1&severity=high
{
  "success": true,
  "results": [...],
  "total": 25
}
```

### Webhook уведомления

```python
# Настройка webhook для получения уведомлений о уязвимостях
# В файле services/telegram_service.py можно добавить:

def send_webhook_notification(self, vulnerability, webhook_url):
    """Отправка webhook уведомления"""
    payload = {
        'type': 'vulnerability_found',
        'severity': vulnerability.severity_level,
        'ip': vulnerability.ip_address,
        'template': vulnerability.template_method,
        'timestamp': vulnerability.timestamp.isoformat()
    }
    
    requests.post(webhook_url, json=payload)
```

## 📊 Мониторинг

### Системный мониторинг

```bash
# Скрипт проверки состояния системы
./monitoring.sh

# Просмотр логов в реальном времени
tail -f /var/log/nuclei-scanner/web.out.log
tail -f /var/log/nuclei-worker/worker.out.log

# Статус всех сервисов
supervisorctl status

# Мониторинг PostgreSQL
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"
```

### Метрики воркеров

```bash
# CPU и память воркера
htop

# Статистика Nuclei
nuclei -stats

# Сетевые соединения
ss -tuln | grep 5432
```

### Алерты и уведомления

Система автоматически отправляет уведомления в Telegram при:
- Обнаружении критичных уязвимостей (critical/high)
- Изменении статуса серверов (online/offline)
- Завершении задач сканирования
- Ошибках в работе системы

## 🔒 Безопасность

### Рекомендации по безопасности

1. **Смена паролей по умолчанию**
```bash
# Изменить пароли в .env файле
nano /opt/nuclei-scanner/.env
```

2. **Настройка файрвола**
```bash
# UFW правила
ufw allow from TRUSTED_IP to any port 22
ufw allow from WORKER_NETWORK to any port 5432
ufw allow 80/tcp
ufw allow 443/tcp
```

3. **SSL/TLS шифрование**
```bash
# Установка Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

4. **Изоляция сетей**
```bash
# Создание отдельной сети для воркеров
# Настройка VPN между центральным сервером и воркерами
```

### Аудит безопасности

```bash
# Проверка открытых портов
nmap -sT localhost

# Анализ логов безопасности
grep "Failed" /var/log/auth.log

# Проверка прав доступа к файлам
find /opt/nuclei-scanner -type f -perm -o+w

# Мониторинг подозрительной активности
tail -f /var/log/nuclei-scanner/web.out.log | grep -i "error\|fail\|attack"
```

## 🔧 Обслуживание

### Резервное копирование

```bash
# Автоматическое резервное копирование
./backup.sh

# Восстановление из резервной копии
sudo -u postgres psql belarus < belarus_backup.sql

# Настройка автоматического бэкапа (crontab)
0 2 * * * /opt/nuclei-scanner/backup.sh
```

### Обновление системы

```bash
# Обновление центрального сервера
cd /opt/nuclei-scanner
git pull origin main
supervisorctl restart nuclei-scanner-web

# Обновление воркеров
# Выполнить на каждом воркере:
supervisorctl restart nuclei-worker
```

### Масштабирование

```bash
# Добавление нового воркера
1. Развернуть воркер с помощью worker-deploy.sh
2. Настроить SSH ключи с центрального сервера
3. Добавить сервер через веб-интерфейс
4. Протестировать подключение

# Балансировка нагрузки
# Система автоматически распределяет задачи между доступными воркерами
```

## 🐛 Решение проблем

### Частые проблемы

<details>
<summary>Воркер не подключается к базе данных</summary>

```bash
# Проверка сетевого подключения
telnet CENTRAL_SERVER_IP 5432

# Проверка прав пользователя в PostgreSQL
sudo -u postgres psql -c "SELECT * FROM pg_user WHERE usename='worker_belarus_1';"

# Проверка файрвола
sudo ufw status
```
</details>

<details>
<summary>Nuclei не находит шаблоны</summary>

```bash
# Проверка пути к шаблонам
ls -la /opt/custom-templates/

# Обновление шаблонов
nuclei -update-templates

# Проверка прав доступа
sudo chown -R nuclei-worker:nuclei-worker /opt/custom-templates/
```
</details>

<details>
<summary>Высокая нагрузка на сервер</summary>

```bash
# Уменьшение rate-limit в config.yaml
rate_limit: 50  # вместо 100

# Ограничение количества потоков
threads: 25     # вместо 50

# Мониторинг ресурсов
htop
iotop
```
</details>

### Логи для диагностики

```bash
# Веб-приложение
/var/log/nuclei-scanner/web.out.log
/var/log/nuclei-scanner/web.err.log

# Воркеры
/var/log/nuclei-worker/worker.out.log
/var/log/nuclei-worker/worker.err.log

# Системные логи
/var/log/supervisor/
/var/log/nginx/
/var/log/postgresql/
```

## 📚 FAQ

**Q: Можно ли использовать систему для сканирования внешних IP?**
A: Да, но убедитесь, что у вас есть разрешение на сканирование целевых ресурсов.

**Q: Как добавить новые шаблоны Nuclei?**
A: Поместите YAML файлы в директорию `/opt/custom-templates/` на воркерах.

**Q: Поддерживается ли сканирование IPv6?**
A: Да, система поддерживает как IPv4, так и IPv6 адреса.

**Q: Можно ли ограничить сканирование по времени?**
A: Да, настройте параметры `timeout` и `rate_limit` в конфигурации воркера.

**Q: Как настроить уведомления в Slack вместо Telegram?**
A: Модифицируйте класс `TelegramService` для отправки в Slack webhook.

## 🤝 Поддержка

### Контакты
- 📧 Email: support@your-domain.com
- 💬 Telegram: @your_support_bot
- 🐛 Issues: https://github.com/your-repo/nuclei-scanner/issues

### Документация
- 📖 Wiki: https://github.com/your-repo/nuclei-scanner/wiki
- 🎥 Видео-инструкции: https://youtube.com/your-channel

### Сообщество
- 💻 Discord: https://discord.gg/your-server
- 🔗 LinkedIn: https://linkedin.com/company/your-company

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).

## 🙏 Благодарности

- [ProjectDiscovery](https://github.com/projectdiscovery) за Nuclei
- [Flask](https://flask.palletsprojects.com/) за веб-фреймворк
- Сообществу информационной безопасности за поддержку

---

**⚠️ Предупреждение**: Используйте эту систему только для сканирования собственных ресурсов или с явного разрешения владельцев. Несанкционированное сканирование может быть незаконным.
