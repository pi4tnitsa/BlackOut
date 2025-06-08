from fastapi import FastAPI, Request, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn
from typing import Optional, List
from datetime import datetime
import os
import json

from config import settings
from database import get_db, init_db, User, Worker, Task, Template, Result
from modules.auth import get_current_user, create_access_token, verify_user
from modules.worker_manager import WorkerManager
from modules.task_manager import TaskManager
from modules.template_manager import TemplateManager
from modules.result_parser import ResultParser

# Инициализация приложения
app = FastAPI(title=settings.app_name, version=settings.version)

# Статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Инициализация менеджеров
worker_manager = WorkerManager()
task_manager = TaskManager()
template_manager = TemplateManager()
result_parser = ResultParser()

# Маршруты
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    # Проверка аутентификации
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        return RedirectResponse(url="/dashboard", status_code=302)
    except:
        return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = verify_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Неверный логин или пароль"}
        )
    
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        
        # Статистика
        workers_count = db.query(Worker).count()
        tasks_count = db.query(Task).count()
        results_count = db.query(Result).count()
        templates_count = db.query(Template).count()
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "workers_count": workers_count,
            "tasks_count": tasks_count,
            "results_count": results_count,
            "templates_count": templates_count
        })
    except:
        return RedirectResponse(url="/login", status_code=302)

# API для воркеров
@app.get("/workers", response_class=HTMLResponse)
async def workers_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        workers = db.query(Worker).all()
        return templates.TemplateResponse("workers.html", {
            "request": request,
            "user": user,
            "workers": workers
        })
    except:
        return RedirectResponse(url="/login", status_code=302)

@app.post("/api/workers")
async def add_worker(
    request: Request,
    name: str = Form(...),
    ip_address: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    ssh_port: int = Form(22),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_current_user(token, db)
    
    # Проверка существующего воркера
    existing = db.query(Worker).filter(
        (Worker.name == name) | (Worker.ip_address == ip_address)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Worker already exists")
    
    # Создание воркера
    worker = Worker(
        name=name,
        ip_address=ip_address,
        username=username,
        password=password,  # В реальном проекте нужно шифровать
        ssh_port=ssh_port
    )
    db.add(worker)
    db.commit()
    
    # Установка воркера
    try:
        await worker_manager.setup_worker(worker)
        worker.status = "online"
        worker.last_ping = datetime.utcnow()
    except Exception as e:
        worker.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
    
    db.commit()
    return {"status": "success", "worker_id": worker.id}

@app.delete("/api/workers/{worker_id}")
async def delete_worker(
    worker_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_current_user(token, db)
    
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    db.delete(worker)
    db.commit()
    
    return {"status": "success"}

# API для шаблонов
@app.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        templates_list = db.query(Template).all()
        return templates.TemplateResponse("templates.html", {
            "request": request,
            "user": user,
            "templates": templates_list
        })
    except:
        return RedirectResponse(url="/login", status_code=302)

@app.post("/api/templates")
async def upload_template(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_current_user(token, db)
    
    # Проверка расширения файла
    if not file.filename.endswith(('.rar', '.zip')):
        raise HTTPException(status_code=400, detail="Only RAR and ZIP files allowed")
    
    # Сохранение и обработка шаблона
    try:
        template = await template_manager.upload_template(file, db)
        
        # Распространение на воркеры
        workers = db.query(Worker).filter(Worker.status == "online").all()
        for worker in workers:
            await template_manager.deploy_to_worker(template, worker)
        
        return {"status": "success", "template_id": template.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API для задач
@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        tasks = db.query(Task).order_by(Task.created_at.desc()).all()
        return templates.TemplateResponse("tasks.html", {
            "request": request,
            "user": user,
            "tasks": tasks
        })
    except:
        return RedirectResponse(url="/login", status_code=302)

@app.post("/api/tasks")
async def create_task(
    request: Request,
    name: str = Form(...),
    template_id: int = Form(...),
    targets_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_current_user(token, db)
    
    # Создание задачи
    try:
        task = await task_manager.create_task(
            name=name,
            template_id=template_id,
            targets_file=targets_file,
            db=db
        )
        
        # Запуск задачи
        await task_manager.start_task(task.id, db)
        
        return {"status": "success", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/status")
async def get_task_status(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message
    }

# API для результатов
@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        user = await get_current_user(token, db)
        results = db.query(Result).order_by(Result.created_at.desc()).limit(100).all()
        return templates.TemplateResponse("results.html", {
            "request": request,
            "user": user,
            "results": results
        })
    except:
        return RedirectResponse(url="/login", status_code=302)

@app.get("/api/results/export")
async def export_results(
    request: Request,
    format: str = "csv",
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = await get_current_user(token, db)
    
    results = db.query(Result).all()
    
    if format == "csv":
        # Экспорт в CSV
        import csv
        from io import StringIO
        from fastapi.responses import StreamingResponse
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Task", "Template", "Protocol", "Severity", "Target", "Matched At", "Created At"])
        
        for result in results:
            writer.writerow([
                result.id,
                result.task_id,
                result.template_name,
                result.protocol,
                result.severity,
                result.target,
                result.matched_at,
                result.created_at
            ])
        
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=results.csv"}
        )
    
    elif format == "json":
        # Экспорт в JSON
        data = [{
            "id": r.id,
            "task_id": r.task_id,
            "template_name": r.template_name,
            "protocol": r.protocol,
            "severity": r.severity,
            "target": r.target,
            "matched_at": r.matched_at,
            "matcher_name": r.matcher_name,
            "extracted_results": r.extracted_results,
            "created_at": r.created_at.isoformat() if r.created_at else None
        } for r in results]
        
        return JSONResponse(content=data)
    
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

# Запуск при импорте
if __name__ == "__main__":
    # Инициализация базы данных при первом запуске
    init_db()
    
    # Запуск сервера
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )