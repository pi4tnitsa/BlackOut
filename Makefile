# Makefile - Удобные команды для разработки и развертывания
.PHONY: help install-admin install-worker start-admin start-worker stop backup clean

help:
	@echo "Доступные команды:"
	@echo "  install-admin    - Установка центрального сервера"
	@echo "  install-worker   - Установка воркера"
	@echo "  start-admin      - Запуск центрального сервера"
	@echo "  start-worker     - Запуск воркера"
	@echo "  stop            - Остановка всех сервисов"
	@echo "  backup          - Создание резервной копии"
	@echo "  clean           - Очистка временных файлов"
	@echo "  monitor         - Мониторинг системы"

install-admin:
	@echo "Установка центрального сервера..."
	chmod +x deploy.sh
	sudo ./deploy.sh

install-worker:
	@echo "Установка воркера..."
	chmod +x worker-deploy.sh
	sudo ./worker-deploy.sh

start-admin:
	@echo "Запуск центрального сервера..."
	sudo supervisorctl start nuclei-scanner-web nuclei-scanner-monitor

start-worker:
	@echo "Запуск воркера..."
	sudo supervisorctl start nuclei-worker

stop:
	@echo "Остановка всех сервисов..."
	sudo supervisorctl stop all

backup:
	@echo "Создание резервной копии..."
	chmod +x backup.sh
	sudo ./backup.sh

clean:
	@echo "Очистка временных файлов..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.log" -type f -delete 2>/dev/null || true

monitor:
	@echo "Мониторинг системы..."
	chmod +x monitoring.sh
	sudo ./monitoring.sh