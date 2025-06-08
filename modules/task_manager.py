import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
import os
import json

from database import Task, Worker, Template, Result
from modules.worker_manager import WorkerManager
from modules.result_parser import ResultParser
from config import settings

class TaskManager:
    def __init__(self):
        self.worker_manager = WorkerManager()
        self.result_parser = ResultParser()
        self.running_tasks = {}
    
    async def create_task(
        self,
        name: str,
        template_id: int,
        targets_file: UploadFile,
        db: Session
    ) -> Task:
        """Создание новой задачи"""
        # Проверка шаблона
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise Exception("Template not found")
        
        # Сохранение файла с целями
        targets_filename = f"targets_{datetime.now().timestamp()}.txt"
        targets_path = os.path.join(settings.targets_dir, targets_filename)
        
        content = await targets_file.read()
        with open(targets_path, "wb") as f:
            f.write(content)
        
        # Подсчет целей
        with open(targets_path, "r") as f:
            targets = [line.strip() for line in f if line.strip()]
        targets_count = len(targets)
        
        # Выбор свободного воркера
        worker = db.query(Worker).filter(
            Worker.status == "online"
        ).first()
        
        if not worker:
            raise Exception("No available workers")
        
        # Создание задачи
        task = Task(
            name=name,
            template_id=template_id,
            worker_id=worker.id,
            targets_file=targets_path,
            targets_count=targets_count,
            status="pending"
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return task
    
    async def start_task(self, task_id: int, db: Session):
        """Запуск задачи"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise Exception("Task not found")
        
        if task.status != "pending":
            raise Exception("Task already started")
        
        # Запуск в фоне
        asyncio.create_task(self._run_task(task_id))
    
    async def _run_task(self, task_id: int):
        """Выполнение задачи"""
        db = Session(bind=db.engine)
        
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            worker = task.worker
            template = task.template
            
            # Обновление статуса
            task.status = "running"
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Чтение целей
            with open(task.targets_file, "r") as f:
                targets = [line.strip() for line in f if line.strip()]
            
            # Развертывание целей на воркере
            targets_remote_path = await self.worker_manager.deploy_targets(
                worker, targets, task_id
            )
            
            # Путь к шаблону на воркере
            template_remote_path = f"~/nuclei-worker/templates/{os.path.basename(template.file_path)}"
            
            # Запуск сканирования
            screen_name = await self.worker_manager.start_scan(
                worker, task_id, template_remote_path, targets_remote_path
            )
            
            task.screen_session = screen_name
            db.commit()
            
            # Мониторинг прогресса
            self.running_tasks[task_id] = True
            
            while self.running_tasks.get(task_id, False):
                # Проверка статуса
                status = await self.worker_manager.get_scan_status(worker, screen_name)
                
                if not status["is_running"]:
                    break
                
                # Обновление прогресса (примерная оценка)
                # В реальном проекте нужно парсить вывод nuclei для точного прогресса
                await asyncio.sleep(10)
            
            # Получение результатов
            results_json = await self.worker_manager.get_scan_results(worker, task_id)
            
            # Парсинг и сохранение результатов
            results = json.loads(results_json) if results_json else []
            for result_data in results:
                result = self.result_parser.parse_result(result_data, task_id)
                if result:
                    db.add(result)
            
            # Обновление статуса задачи
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.progress = 100.0
            db.commit()
            
            # Очистка
            await self.worker_manager.cleanup_worker(worker, task_id)
            
        except Exception as e:
            # Обработка ошибок
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.commit()
        
        finally:
            # Удаление из активных задач
            self.running_tasks.pop(task_id, None)
            db.close()
    
    async def stop_task(self, task_id: int, db: Session):
        """Остановка задачи"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise Exception("Task not found")
        
        if task.status != "running":
            raise Exception("Task is not running")
        
        # Сигнал остановки
        self.running_tasks[task_id] = False
        
        # Остановка на воркере
        if task.screen_session:
            await self.worker_manager.stop_scan(task.worker, task.screen_session)
        
        # Обновление статуса
        task.status = "failed"
        task.error_message = "Task stopped by user"
        task.completed_at = datetime.utcnow()
        db.commit()
    
    async def get_task_progress(self, task_id: int, db: Session) -> dict:
        """Получение прогресса задачи"""
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise Exception("Task not found")
        
        # Если задача выполняется, получаем актуальный статус
        if task.status == "running" and task.screen_session:
            status = await self.worker_manager.get_scan_status(
                task.worker, task.screen_session
            )
            
            return {
                "status": task.status,
                "progress": task.progress,
                "is_running": status["is_running"],
                "log_tail": status["log_tail"]
            }
        
        return {
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message
        }
    
    def distribute_targets(self, targets: List[str], workers_count: int) -> List[List[str]]:
        """Распределение целей между воркерами"""
        if workers_count == 0:
            return []
        
        # Равномерное распределение
        chunk_size = len(targets) // workers_count
        remainder = len(targets) % workers_count
        
        chunks = []
        start = 0
        
        for i in range(workers_count):
            end = start + chunk_size + (1 if i < remainder else 0)
            chunks.append(targets[start:end])
            start = end
        