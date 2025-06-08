import paramiko
import asyncio
from typing import Optional, List
import os
from datetime import datetime
from database import Worker
from config import settings

class WorkerManager:
    def __init__(self):
        self.ssh_clients = {}
    
    async def setup_worker(self, worker: Worker):
        """Установка и настройка воркера"""
        try:
            # SSH подключение
            ssh = self._connect_ssh(worker)
            
            # Установка необходимых пакетов
            commands = [
                # Обновление системы
                "sudo apt-get update",
                
                # Установка зависимостей
                "sudo apt-get install -y screen unzip unrar curl git",
                
                # Установка Nuclei
                "curl -sL https://github.com/projectdiscovery/nuclei/releases/latest/download/nuclei_linux_amd64.zip -o nuclei.zip",
                "unzip -o nuclei.zip",
                "sudo mv nuclei /usr/local/bin/",
                "rm nuclei.zip",
                "nuclei -version",
                
                # Создание рабочих директорий
                "mkdir -p ~/nuclei-worker/templates",
                "mkdir -p ~/nuclei-worker/targets",
                "mkdir -p ~/nuclei-worker/results",
                "mkdir -p ~/nuclei-worker/logs",
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.read()
                error = stderr.read().decode()
                if error and "already" not in error.lower():
                    print(f"Warning on {worker.name}: {error}")
            
            # Создание скрипта запуска
            run_script = """#!/bin/bash
TASK_ID=$1
TEMPLATE_PATH=$2
TARGETS_PATH=$3
OUTPUT_PATH=$4

# Запуск nuclei
nuclei -t "$TEMPLATE_PATH" -l "$TARGETS_PATH" -o "$OUTPUT_PATH" \\
    -rate-limit 150 -bulk-size 50 -concurrency 50 \\
    -json -stats -silent

echo "Scan completed for task $TASK_ID"
"""
            
            stdin, stdout, stderr = ssh.exec_command(
                f"echo '{run_script}' > ~/nuclei-worker/run_scan.sh && chmod +x ~/nuclei-worker/run_scan.sh"
            )
            stdout.read()
            
            ssh.close()
            return True
            
        except Exception as e:
            raise Exception(f"Failed to setup worker {worker.name}: {str(e)}")
    
    def _connect_ssh(self, worker: Worker) -> paramiko.SSHClient:
        """Создание SSH подключения"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=worker.ip_address,
                port=worker.ssh_port,
                username=worker.username,
                password=worker.password,
                timeout=settings.worker_timeout
            )
            return ssh
        except Exception as e:
            raise Exception(f"SSH connection failed: {str(e)}")
    
    async def check_worker_status(self, worker: Worker) -> bool:
        """Проверка статуса воркера"""
        try:
            ssh = self._connect_ssh(worker)
            stdin, stdout, stderr = ssh.exec_command("echo 'ping'")
            result = stdout.read().decode().strip()
            ssh.close()
            return result == "ping"
        except:
            return False
    
    async def ensure_remote_directory(self, ssh: paramiko.SSHClient, path: str):
        """Создает удаленную директорию, если она не существует"""
        stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {path}")
        # Дожидаемся завершения команды
        stdout.channel.recv_exit_status()


    async def deploy_template(self, worker: Worker, template_path: str, template_name: str):
        """Развертывание шаблона на воркере"""
        try:
            ssh = self._connect_ssh(worker)
            sftp = ssh.open_sftp()
            
            # Создаем директорию, если не существует
            remote_dir = "~/nuclei-worker/templates"
            await self.ensure_remote_directory(ssh, remote_dir)

            # Копирование архива
            remote_path = f"~/nuclei-worker/templates/{template_name}"
            sftp.put(template_path, remote_path)
            
            # Распаковка архива
            if template_name.endswith('.rar'):
                cmd = f"cd ~/nuclei-worker/templates && unrar x -o+ {template_name}"
            else:
                cmd = f"cd ~/nuclei-worker/templates && unzip -o {template_name}"
            
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
            
            sftp.close()
            ssh.close()
            
        except Exception as e:
            raise Exception(f"Failed to deploy template: {str(e)}")
    
    async def deploy_targets(self, worker: Worker, targets: List[str], task_id: int) -> str:
        """Развертывание списка целей на воркере"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Создание файла с целями
            targets_content = "\n".join(targets)
            targets_filename = f"targets_task_{task_id}.txt"
            remote_path = f"~/nuclei-worker/targets/{targets_filename}"
            
            stdin, stdout, stderr = ssh.exec_command(
                f"echo '{targets_content}' > {remote_path}"
            )
            stdout.read()
            
            ssh.close()
            return remote_path
            
        except Exception as e:
            raise Exception(f"Failed to deploy targets: {str(e)}")
    
    async def start_scan(self, worker: Worker, task_id: int, template_path: str, targets_path: str) -> str:
        """Запуск сканирования на воркере"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Формирование команды
            output_path = f"~/nuclei-worker/results/task_{task_id}_results.json"
            screen_name = f"nuclei_task_{task_id}"
            
            cmd = f"""screen -dmS {screen_name} bash -c '~/nuclei-worker/run_scan.sh {task_id} {template_path} {targets_path} {output_path}'"""
            
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
            
            ssh.close()
            return screen_name
            
        except Exception as e:
            raise Exception(f"Failed to start scan: {str(e)}")
    
    async def get_scan_status(self, worker: Worker, screen_name: str) -> dict:
        """Получение статуса сканирования"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Проверка существования screen сессии
            stdin, stdout, stderr = ssh.exec_command(f"screen -ls | grep {screen_name}")
            result = stdout.read().decode().strip()
            
            is_running = bool(result)
            
            # Получение последних строк лога
            log_cmd = f"tail -n 50 ~/nuclei-worker/logs/{screen_name}.log 2>/dev/null || echo ''"
            stdin, stdout, stderr = ssh.exec_command(log_cmd)
            log_tail = stdout.read().decode()
            
            ssh.close()
            
            return {
                "is_running": is_running,
                "log_tail": log_tail
            }
            
        except Exception as e:
            return {
                "is_running": False,
                "log_tail": f"Error: {str(e)}"
            }
    
    async def get_scan_results(self, worker: Worker, task_id: int) -> str:
        """Получение результатов сканирования"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Чтение файла результатов
            results_path = f"~/nuclei-worker/results/task_{task_id}_results.json"
            stdin, stdout, stderr = ssh.exec_command(f"cat {results_path} 2>/dev/null || echo '[]'")
            results = stdout.read().decode()
            
            ssh.close()
            return results
            
        except Exception as e:
            raise Exception(f"Failed to get results: {str(e)}")
    
    async def stop_scan(self, worker: Worker, screen_name: str):
        """Остановка сканирования"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Завершение screen сессии
            stdin, stdout, stderr = ssh.exec_command(f"screen -X -S {screen_name} quit")
            stdout.read()
            
            ssh.close()
            
        except Exception as e:
            raise Exception(f"Failed to stop scan: {str(e)}")
    
    async def cleanup_worker(self, worker: Worker, task_id: int):
        """Очистка файлов задачи на воркере"""
        try:
            ssh = self._connect_ssh(worker)
            
            # Удаление файлов задачи
            commands = [
                f"rm -f ~/nuclei-worker/targets/targets_task_{task_id}.txt",
                f"rm -f ~/nuclei-worker/results/task_{task_id}_results.json",
                f"rm -f ~/nuclei-worker/logs/nuclei_task_{task_id}.log"
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.read()
            
            ssh.close()
            
        except:
            pass  # Игнорируем ошибки очистки