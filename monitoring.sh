# monitoring.sh - Скрипт мониторинга системы (отсутствовал)
#!/bin/bash

echo "=== Мониторинг Nuclei Scanner ==="

echo "📊 Статус сервисов:"
echo "===================="
systemctl is-active --quiet postgresql && echo "✅ PostgreSQL: Активен" || echo "❌ PostgreSQL: Не активен"
systemctl is-active --quiet redis && echo "✅ Redis: Активен" || echo "❌ Redis: Не активен"
systemctl is-active --quiet nginx && echo "✅ Nginx: Активен" || echo "❌ Nginx: Не активен"
systemctl is-active --quiet supervisor && echo "✅ Supervisor: Активен" || echo "❌ Supervisor: Не активен"

echo ""
echo "🔧 Процессы Nuclei Scanner:"
echo "==========================="
supervisorctl status

echo ""
echo "💾 Использование диска:"
echo "======================"
df -h | grep -E "(Filesystem|/dev/)"

echo ""
echo "🧠 Использование памяти:"
echo "========================"
free -h

echo ""
echo "⚡ Загрузка CPU:"
echo "==============="
uptime

echo ""
echo "🌐 Сетевые подключения:"
echo "======================="
ss -tuln | grep -E "(5000|5432|6379|80)"

echo ""
echo "📝 Последние строки логов:"
echo "=========================="
echo "Web-приложение:"
tail -5 /var/log/nuclei-scanner/web.out.log 2>/dev/null || echo "Лог не найден"

echo ""
echo "Мониторинг:"
tail -5 /var/log/nuclei-scanner/monitor.out.log 2>/dev/null || echo "Лог не найден"

echo ""
echo "🔍 Статистика базы данных:"
echo "=========================="
sudo -u postgres psql -c "
SELECT 
    datname as database,
    numbackends as connections,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_stat_database 
WHERE datname IN ('belarus', 'russia', 'kazakhstan');
" 2>/dev/null || echo "Ошибка подключения к PostgreSQL"
