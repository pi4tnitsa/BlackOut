# test_connectivity.py - Скрипт для тестирования подключений
#!/usr/bin/env python3
"""
Скрипт тестирования компонентов системы Nuclei Scanner
"""

import sys
import os
import psycopg2
import redis
import requests
import subprocess
from datetime import datetime

def test_database_connection():
    """Тестирование подключения к PostgreSQL"""
    print("🔍 Тестирование подключения к PostgreSQL...")
    
    try:
        # Параметры подключения из .env или по умолчанию
        conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'user': os.getenv('DB_ADMIN_USER', 'admin'),
            'password': os.getenv('DB_ADMIN_PASSWORD', 'admin_password'),
            'database': 'belarus'  # Тестируем одну из баз
        }
        
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Проверяем наличие таблиц
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('vulnerabilities', 'servers', 'scan_tasks')
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        if len(tables) == 3:
            print("✅ PostgreSQL: Подключение успешно, все таблицы присутствуют")
        else:
            print(f"⚠️  PostgreSQL: Найдены таблицы: {tables}, ожидались: vulnerabilities, servers, scan_tasks")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL: Ошибка подключения - {e}")
        return False

def test_redis_connection():
    """Тестирование подключения к Redis"""
    print("🔍 Тестирование подключения к Redis...")
    
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        
        # Тестовая запись и чтение
        test_key = f"nuclei_test_{datetime.now().timestamp()}"
        r.set(test_key, "test_value", ex=10)  # Истекает через 10 секунд
        
        value = r.get(test_key)
        if value == b"test_value":
            print("✅ Redis: Подключение успешно")
            r.delete(test_key)
            return True
        else:
            print("❌ Redis: Ошибка записи/чтения данных")
            return False
            
    except Exception as e:
        print(f"❌ Redis: Ошибка подключения - {e}")
        return False

def test_nuclei_installation():
    """Тестирование установки Nuclei"""
    print("🔍 Тестирование установки Nuclei...")
    
    try:
        result = subprocess.run(['nuclei', '-version'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Nuclei: Установлен, версия {version}")
            return True
        else:
            print(f"❌ Nuclei: Ошибка при проверке версии - {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ Nuclei: Команда не найдена, возможно не установлен")
        return False
    except Exception as e:
        print(f"❌ Nuclei: Ошибка - {e}")
        return False

def test_web_application():
    """Тестирование веб-приложения"""
    print("🔍 Тестирование веб-приложения...")
    
    try:
        response = requests.get('http://localhost:5000', timeout=10)
        
        if response.status_code == 200:
            print("✅ Web-приложение: Доступно")
            return True
        elif response.status_code == 302:
            print("✅ Web-приложение: Доступно (перенаправление на авторизацию)")
            return True
        else:
            print(f"⚠️  Web-приложение: Необычный статус код {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Web-приложение: Не удается подключиться на localhost:5000")
        return False
    except Exception as e:
        print(f"❌ Web-приложение: Ошибка - {e}")
        return False

def test_templates_directory():
    """Тестирование директорий шаблонов"""
    print("🔍 Тестирование директорий шаблонов...")
    
    templates_path = os.getenv('NUCLEI_TEMPLATES_PATH', '/opt/nuclei-templates')
    custom_path = os.getenv('CUSTOM_TEMPLATES_PATH', '/opt/custom-templates')
    
    success = True
    
    if os.path.exists(templates_path) and os.path.isdir(templates_path):
        template_count = len([f for f in os.listdir(templates_path) if f.endswith('.yaml')])
        print(f"✅ Nuclei Templates: Директория найдена, {template_count} шаблонов")
    else:
        print(f"❌ Nuclei Templates: Директория {templates_path} не найдена")
        success = False
    
    if os.path.exists(custom_path) and os.path.isdir(custom_path):
        custom_count = len([f for f in os.listdir(custom_path) if f.endswith('.yaml')])
        print(f"✅ Custom Templates: Директория найдена, {custom_count} кастомных шаблонов")
    else:
        print(f"⚠️  Custom Templates: Директория {custom_path} не найдена")
    
    return success

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования компонентов Nuclei Scanner")
    print("=" * 60)
    
    # Загружаем переменные окружения из .env если файл существует
    env_file = '.env'
    if os.path.exists(env_file):
        print(f"📁 Загрузка переменных из {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    tests = [
        ("База данных PostgreSQL", test_database_connection),
        ("Redis", test_redis_connection),
        ("Nuclei", test_nuclei_installation),
        ("Веб-приложение", test_web_application),
        ("Директории шаблонов", test_templates_directory)
    ]
    
    results = []
    
    print("\n🔍 Выполнение тестов:")
    print("-" * 40)
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name}: Неожиданная ошибка - {e}")
            results.append((name, False))
        print()
    
    # Сводка результатов
    print("📊 Сводка результатов:")
    print("-" * 40)
    
    passed = 0
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        print(f"{name:<25} {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все компоненты работают корректно!")
        return 0
    else:
        print("⚠️  Некоторые компоненты требуют внимания")
        return 1

if __name__ == "__main__":
    sys.exit(main())
