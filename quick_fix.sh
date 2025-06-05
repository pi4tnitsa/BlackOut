#!/bin/bash

echo "=== Быстрое исправление проблем Nuclei Scanner ==="

# Проверяем права
if [[ $EUID -ne 0 ]]; then
   echo "Запустите с правами root: sudo $0"
   exit 1
fi

PROJECT_DIR="/opt/nuclei-scanner"
USER="nuclei-admin"

echo "1. Создание отсутствующих директорий..."
mkdir -p "$PROJECT_DIR/web/static/js"
mkdir -p "$PROJECT_DIR/web/static/css"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "/var/log/nuclei-scanner"

echo "2. Создание базового CSS файла..."
cat > "$PROJECT_DIR/web/static/css/style.css" << 'EOF'
/* Основные стили для Nuclei Scanner */
.sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: 100;
    padding: 48px 0 0;
    box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
}

.severity-critical { color: #dc3545; font-weight: bold; }
.severity-high { color: #fd7e14; font-weight: bold; }
.severity-medium { color: #ffc107; font-weight: bold; }
.severity-low { color: #20c997; }
.severity-info { color: #0dcaf0; }

.status-online { color: #198754; }
.status-offline { color: #dc3545; }
.status-unknown { color: #6c757d; }
EOF

echo "3. Создание базового JS файла..."
cat > "$PROJECT_DIR/web/static/js/main.js" << 'EOF'
// Основные JavaScript функции
function refreshStats() {
    location.reload();
}

function showNotification(message, type = 'info') {
    alert(message);
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('Nuclei Scanner загружен');
});
EOF

echo "4. Исправление прав доступа..."
chown -R "$USER:$USER" "$PROJECT_DIR"
chown -R "$USER:$USER" "/var/log/nuclei-scanner"

echo "5. Перезапуск сервисов..."
supervisorctl restart nuclei-scanner-web

echo "6. Проверка статуса..."
sleep 3
supervisorctl status nuclei-scanner-web

echo "✅ Быстрое исправление завершено!"
echo ""
echo "Проверьте доступность веб-интерфейса:"
echo "http://$(hostname -I | awk '{print $1}')"
