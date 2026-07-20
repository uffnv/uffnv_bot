#!/usr/bin/env python3
"""
Скрипт первоначальной настройки БД для бота.
Запускать один раз после установки PostgreSQL.
"""
import subprocess
import sys

PG_BIN = r"C:\Program Files\PostgreSQL\17\bin"
DB_NAME = "lifemanager"
DB_USER = "botuser"
DB_PASS = "botpassword"

def run(cmd, **kwargs):
    print(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

print("=== Настройка БД для Life-Manager Bot ===\n")

# Создаём пользователя и БД от имени postgres
run(f'"{PG_BIN}\\psql" -U postgres -c "CREATE USER {DB_USER} WITH PASSWORD \'{DB_PASS}\';" 2>&1 || true')
run(f'"{PG_BIN}\\psql" -U postgres -c "CREATE DATABASE {DB_NAME} OWNER {DB_USER};" 2>&1 || true')
run(f'"{PG_BIN}\\psql" -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE {DB_NAME} TO {DB_USER};" 2>&1 || true')

print("\n✅ База данных настроена!")
print(f"   БД: {DB_NAME}")
print(f"   Пользователь: {DB_USER}")
print(f"   Пароль: {DB_PASS}")
print(f"\nDATABASE_URL=postgresql+asyncpg://{DB_USER}:{DB_PASS}@localhost:5432/{DB_NAME}")
