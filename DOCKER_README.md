# Docker Quick Start Guide

## 🚀 Быстрый запуск

### 1. Создайте .env файл
```bash
cp .env.example .env
```

Отредактируйте `.env` и заполните:
- `BOT_TOKEN` - токен бота от @BotFather
- `ADMIN_IDS` - ваш Telegram ID (получить: @userinfobot)
- `DB_PASSWORD` - пароль для PostgreSQL
- Опционально: `CRYPTOMUS_API_KEY`, `CRYPTOMUS_MERCHANT_ID`, `CRYPTOMUS_WEBHOOK_SECRET`

### 2. Запустите контейнеры
```bash
docker-compose up -d
```

### 3. Проверьте логи
```bash
docker-compose logs -f bot
```

## 📋 Доступные команды

### Запуск
```bash
# Запуск в фоне
docker-compose up -d

# Запуск с логами
docker-compose up
```

### Остановка
```bash
# Остановка без удаления контейнеров
docker-compose stop

# Остановка и удаление контейнеров
docker-compose down

# Остановка и удаление ВСЕГО (включая volumes)
docker-compose down -v
```

### Логи
```bash
# Все логи
docker-compose logs

# Логи бота
docker-compose logs bot

# Логи PostgreSQL
docker-compose logs postgres

# Следить за логами (live)
docker-compose logs -f bot
```

### Пересборка
```bash
# Пересобрать образ бота
docker-compose build bot

# Пересобрать БЕЗ кэша
docker-compose build --no-cache bot

# Пересобрать и запустить
docker-compose up -d --build
```

### Доступ к контейнерам
```bash
# Shell в контейнер бота
docker-compose exec bot bash

# Shell в PostgreSQL
docker-compose exec postgres psql -U bot_user -d payment_bot

# Python REPL в контейнере бота
docker-compose exec bot python
```

## 🔧 Переменные окружения

Основные переменные в `.env`:

```env
# Telegram Bot
BOT_TOKEN=123456:ABC-DEF...
ADMIN_IDS=123456789,987654321

# Database (PostgreSQL)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=payment_bot
DB_USER=bot_user
DB_PASSWORD=change_me_in_production

# Cryptomus (опционально - работает MOCK mode)
CRYPTOMUS_API_KEY=
CRYPTOMUS_MERCHANT_ID=
CRYPTOMUS_WEBHOOK_SECRET=

# Support
SUPPORT_USERNAME=YourSupportBot
```

## 📊 Структура volumes

### Постоянные данные
- `postgres_data` - данные PostgreSQL
- `./data/logs` - логи бота (доступны на хосте)

### Расположение на хосте
```
project/
├── data/
│   └── logs/
│       ├── bot.log
│       └── bot_errors.log
```

## 🐛 Troubleshooting

### Бот не стартует
```bash
# Проверьте логи
docker-compose logs bot

# Проверьте .env файл
cat .env

# Пересоберите образ
docker-compose build --no-cache bot
docker-compose up -d
```

### База данных недоступна
```bash
# Проверьте статус PostgreSQL
docker-compose ps postgres

# Проверьте healthcheck
docker inspect payment_bot_db | grep -A 10 Health

# Перезапустите PostgreSQL
docker-compose restart postgres
```

### Ошибки при миграции
```bash
# Войдите в контейнер
docker-compose exec bot bash

# Проверьте соединение с БД
python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
```

## 🔄 Обновление бота

```bash
# 1. Остановите контейнеры
docker-compose down

# 2. Обновите код (git pull или замените файлы)
git pull

# 3. Пересоберите образ
docker-compose build bot

# 4. Запустите
docker-compose up -d

# 5. Проверьте логи
docker-compose logs -f bot
```

## 🗑️ Полная очистка

```bash
# Удалить всё (контейнеры, volumes, образы)
docker-compose down -v --rmi all

# Удалить только volumes (БД будет стёрта!)
docker-compose down -v
```

## 💾 Backup базы данных

### Создание backup
```bash
docker-compose exec postgres pg_dump -U bot_user payment_bot > backup.sql
```

### Восстановление backup
```bash
cat backup.sql | docker-compose exec -T postgres psql -U bot_user -d payment_bot
```

## 📈 Production рекомендации

1. **Измените пароли** в `.env`
2. **Используйте Docker secrets** для чувствительных данных
3. **Настройте логи** (ротация через Docker logging driver)
4. **Мониторинг** через `docker-compose logs`
5. **Backup базы** регулярно
6. **Используйте reverse proxy** (nginx) для webhook endpoint

## 🌐 Ports

- `5432` - PostgreSQL (доступен для external connections)

Если нужно закрыть порт наружу, удалите `ports:` секцию в `docker-compose.yml` для postgres.
