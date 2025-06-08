from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import bcrypt
from config import settings

# Создание движка базы данных
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модели
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    ip_address = Column(String(45), unique=True, nullable=False)
    ssh_port = Column(Integer, default=22)
    username = Column(String(50), nullable=False)
    password = Column(String(255))  # Зашифрованный пароль
    status = Column(String(20), default="offline")  # online, offline, error
    last_ping = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    tasks = relationship("Task", back_populates="worker")

class Template(Base):
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Связи
    tasks = relationship("Task", back_populates="template")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    worker_id = Column(Integer, ForeignKey("workers.id"))
    template_id = Column(Integer, ForeignKey("templates.id"))
    targets_file = Column(String(500))
    targets_count = Column(Integer, default=0)
    progress = Column(Float, default=0.0)
    screen_session = Column(String(100))  # Имя screen сессии
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text)
    
    # Связи
    worker = relationship("Worker", back_populates="tasks")
    template = relationship("Template", back_populates="tasks")
    results = relationship("Result", back_populates="task", cascade="all, delete-orphan")

class Result(Base):
    __tablename__ = "results"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    template_name = Column(String(255))
    protocol = Column(String(20))  # http, https, tcp, etc
    severity = Column(String(20))  # info, low, medium, high, critical
    target = Column(String(500))
    matched_at = Column(String(500))
    matcher_name = Column(String(255))
    extracted_results = Column(Text)
    curl_command = Column(Text)
    raw_output = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    task = relationship("Task", back_populates="results")

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Инициализация базы данных
def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Создание администратора по умолчанию
    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(username=settings.admin_username).first()
        if not admin:
            admin = User(
                username=settings.admin_username,
                is_admin=True
            )
            admin.set_password(settings.admin_password)
            db.add(admin)
            db.commit()
            print(f"Создан администратор: {settings.admin_username}")
    finally:
        db.close()