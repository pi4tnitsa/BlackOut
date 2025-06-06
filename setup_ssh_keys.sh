#!/bin/bash

echo "=== Настройка SSH ключей для управления воркерами ==="

# Проверка наличия центрального сервера
if [ -z "$1" ]; then
    echo "Использование: $0 <IP_воркера> [пользователь]"
    echo "Пример: $0 192.168.1.100 root"
    exit 1
fi

WORKER_IP="$1"
SSH_USER="${2:-root}"
CENTRAL_USER="nuclei-admin"

echo "Копирование SSH ключа на воркер $WORKER_IP..."

# Проверяем наличие SSH ключа
if [ ! -f "/home/$CENTRAL_USER/.ssh/id_rsa.pub" ]; then
    echo "SSH ключ не найден. Создание нового ключа..."
    sudo -u "$CENTRAL_USER" ssh-keygen -t rsa -b 4096 -f "/home/$CENTRAL_USER/.ssh/id_rsa" -N ""
fi

# Копируем ключ на воркер
echo "Копирование ключа на $WORKER_IP..."
sudo -u "$CENTRAL_USER" ssh-copy-id -i "/home/$CENTRAL_USER/.ssh/id_rsa.pub" "$SSH_USER@$WORKER_IP"

# Тестируем соединение
echo "Тестирование SSH соединения..."
sudo -u "$CENTRAL_USER" ssh -o ConnectTimeout=10 "$SSH_USER@$WORKER_IP" "echo 'SSH соединение успешно установлено'"

if [ $? -eq 0 ]; then
    echo "✅ SSH ключ успешно настроен для $WORKER_IP"
    echo ""
    echo "Теперь вы можете добавить этот сервер в веб-интерфейс:"
    echo "  IP: $WORKER_IP"
    echo "  SSH пользователь: $SSH_USER"
    echo "  SSH порт: 22"
else
    echo "❌ Ошибка настройки SSH ключа"
    exit 1
fi