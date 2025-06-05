# admin-server/Dockerfile - Dockerfile для центрального сервера
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    openssh-client \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов требований
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание директорий для логов и шаблонов
RUN mkdir -p /app/logs /opt/nuclei-templates /opt/custom-templates

# Создание пользователя для безопасности
RUN useradd -m -u 1000 nuclei && chown -R nuclei:nuclei /app /opt/nuclei-templates /opt/custom-templates
USER nuclei

# Открытие порта
EXPOSE 5000

# Команда запуска
CMD ["python", "app.py"]