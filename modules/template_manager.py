import os
import shutil
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session

from database import Template, Worker
from modules.worker_manager import WorkerManager
from config import settings

class TemplateManager:
    def __init__(self):
        self.worker_manager = WorkerManager()
    
    async def upload_template(self, file: UploadFile, db: Session) -> Template:
        """Загрузка и сохранение шаблона"""
        # Проверка существующего шаблона
        existing = db.query(Template).filter(
            Template.name == file.filename
        ).first()
        
        if existing:
            raise Exception("Template with this name already exists")
        
        # Сохранение файла
        timestamp = datetime.now().timestamp()
        filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(settings.templates_dir, filename)
        
        # Сохранение на диск
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Получение размера файла
        file_size = os.path.getsize(file_path)
        
        # Создание записи в БД
        template = Template(
            name=file.filename,
            filename=filename,
            file_path=file_path,
            file_size=file_size
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return template
    
    async def deploy_to_worker(self, template: Template, worker: Worker):
        """Развертывание шаблона на воркере"""
        try:
            await self.worker_manager.deploy_template(
                worker,
                template.file_path,
                template.filename
            )
        except Exception as e:
            raise Exception(f"Failed to deploy template to {worker.name}: {str(e)}")
    
    async def deploy_to_all_workers(self, template_id: int, db: Session):
        """Развертывание шаблона на всех активных воркерах"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise Exception("Template not found")
        
        # Получение активных воркеров
        workers = db.query(Worker).filter(Worker.status == "online").all()
        
        errors = []
        for worker in workers:
            try:
                await self.deploy_to_worker(template, worker)
            except Exception as e:
                errors.append(f"{worker.name}: {str(e)}")
        
        if errors:
            raise Exception("Deployment errors: " + "; ".join(errors))
    
    def delete_template(self, template_id: int, db: Session):
        """Удаление шаблона"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise Exception("Template not found")
        
        # Удаление файла
        if os.path.exists(template.file_path):
            os.remove(template.file_path)
        
        # Удаление из БД
        db.delete(template)
        db.commit()
    
    def get_template_info(self, template_id: int, db: Session) -> dict:
        """Получение информации о шаблоне"""
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise Exception("Template not found")
        
        return {
            "id": template.id,
            "name": template.name,
            "filename": template.filename,
            "file_size": template.file_size,
            "uploaded_at": template.uploaded_at.isoformat() if template.uploaded_at else None,
            "is_active": template.is_active
        }
    
    def list_templates(self, db: Session) -> list:
        """Получение списка всех шаблонов"""
        templates = db.query(Template).all()
        return [self.get_template_info(t.id, db) for t in templates]
    
    def validate_template_archive(self, file_path: str) -> bool:
        """Валидация архива с шаблонами"""
        # Проверка расширения
        if not (file_path.endswith('.rar') or file_path.endswith('.zip')):
            return False
        
        # Проверка размера (максимум 100MB)
        if os.path.getsize(file_path) > 100 * 1024 * 1024:
            return False
        
        return True
    
    async def sync_templates_with_worker(self, worker: Worker, db: Session):
        """Синхронизация всех шаблонов с воркером"""
        templates = db.query(Template).filter(Template.is_active == True).all()
        
        for template in templates:
            try:
                await self.deploy_to_worker(template, worker)
            except Exception as e:
                print(f"Failed to sync template {template.name} with {worker.name}: {str(e)}")