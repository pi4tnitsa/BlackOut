#!/usr/bin/env python3
"""
Полный тест системы Nuclei Scanner
"""

import sys
import os
import time
import requests
import subprocess
import psycopg2
import redis
from datetime import datetime

def test_database():
    """Тест подключения к PostgreSQL"""
    print("🔍 Тестирование PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            database='belarus',
            user='admin',
            password='nuclei_admin_pass_2024!'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        table_count = cursor.fetchone()[0]
        print(f"✅ PostgreSQL: {table_count} таблиц найдено")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL: {e}")
        return False

def test_redis():
    """Тест подключения к Redis"""
    print("🔍 Тестирование Redis...")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis: подключение успешно")
        return True
    except Exception as e:
        print(f"❌ Redis: {e}")
        return False

def test_web_app():
    """Тест веб-приложения"""
    print("🔍 Тестирование веб-приложения...")
    try:
        response = requests.get('http://localhost:5000', timeout=10)
        if response.status_code in [200, 302]:
            print("✅ Веб-приложение: доступно")
            return True
        else:
            print(f"⚠️ Веб-приложение: статус {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Веб-приложение: {e}")
        return False

def test_nuclei():
    """Тест Nuclei"""
    print("🔍 Тестирование Nuclei...")
    try:
        result = subprocess.run(['nuclei', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Nuclei: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Nuclei: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Nuclei: {e}")
        return False

def test_services():
    """Тест системных сервисов"""
    print("🔍 Тестирование сервисов...")
    services = ['postgresql', 'redis-server', 'nginx', 'supervisor']
    all_ok = True
    
    for service in services:
        try:
            result = subprocess.run(['systemctl', 'is-active', service], 
                                  capture_output=True, text=True)
            if result.stdout.strip() == 'active':
                print(f"✅ {service}: активен")
            else:
                print(f"❌ {service}: не активен")
                all_ok = False
        except Exception as e:
            print(f"❌ {service}: ошибка проверки")
            all_ok = False
    
    return all_ok

def main():
    print("🚀 Тестирование системы Nuclei Scanner")
    print("=" * 50)
    
    tests = [
        ("База данных", test_database),
        ("Redis", test_redis),
        ("Веб-приложение", test_web_app),
        ("Nuclei", test_nuclei),
        ("Системные сервисы", test_services)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ {name}: неожиданная ошибка - {e}")
            print()
    
    print("📊 Результаты:")
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 Все тесты пройдены!")
        print("\n🌐 Доступ к системе:")
        print("URL: http://localhost")
        print("Логин: admin")
        print("Пароль: nuclei_admin_2024!")
        return 0
    else:
        print("⚠️ Некоторые тесты провалены")
        return 1

if __name__ == "__main__":
    sys.exit(main())
