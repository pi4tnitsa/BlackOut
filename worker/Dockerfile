# worker/Dockerfile - Dockerfile для воркера
FROM python:3.11-slim

# Установка системных зависимостей включая Go для Nuclei
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    wget \
    git \
    && wget -q https://golang.org/dl/go1.21.0.linux-amd64.tar.gz \
    && tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz \
    && rm go1.21.0.linux-amd64.tar.gz \
    && rm -rf /var/lib/apt/lists/*

# Настройка PATH для Go
ENV PATH="/usr/local/go/bin:${PATH}"

# Установка Nuclei
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
    && ln -sf /root/go/bin/nuclei /usr/local/bin/nuclei \
    && nuclei -update-templates

# Создание рабочей директории
WORKDIR /app

# Копирование файлов требований
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода воркера
COPY . .

# Создание директорий
RUN mkdir -p /app/logs /opt/custom-templates

# Создание пользователя
RUN useradd -m -u 1000 nuclei && chown -R nuclei:nuclei /app /opt/custom-templates
USER nuclei

# Команда запуска
CMD ["python", "worker.py"]
