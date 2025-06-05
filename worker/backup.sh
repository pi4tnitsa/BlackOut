# backup.sh - Скрипт резервного копирования (отсутствовал)
#!/bin/bash

echo "=== Резервное копирование Nuclei Scanner ==="

# Переменные
BACKUP_DIR="/opt/nuclei-scanner-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="nuclei_scanner_backup_$DATE.tar.gz"

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

echo "Создание резервной копии базы данных..."
sudo -u postgres pg_dump belarus > "$BACKUP_DIR/belarus_$DATE.sql"
sudo -u postgres pg_dump russia > "$BACKUP_DIR/russia_$DATE.sql"
sudo -u postgres pg_dump kazakhstan > "$BACKUP_DIR/kazakhstan_$DATE.sql"

echo "Создание резервной копии конфигурации..."
tar -czf "$BACKUP_DIR/$BACKUP_FILE" \
    --exclude="*/venv/*" \
    --exclude="*/logs/*" \
    --exclude="*/__pycache__/*" \
    /opt/nuclei-scanner \
    /opt/custom-templates \
    /etc/supervisor/conf.d/nuclei-scanner.conf \
    /etc/nginx/sites-available/nuclei-scanner

echo "Резервная копия создана: $BACKUP_DIR/$BACKUP_FILE"

# Удаление старых бэкапов (старше 30 дней)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete

echo "Старые резервные копии очищены"