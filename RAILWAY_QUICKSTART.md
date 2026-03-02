# 🚂 Railway.app - Быстрый старт

## 5 минут до запуска бота в облаке

### 1. GitHub (2 минуты)

```powershell
cd "c:\Users\secvency\Desktop\new tg payment bot crypto"
git init
git add .
git commit -m "Ready for Railway"
```

Создайте репозиторий на [github.com](https://github.com/new) → Private

```powershell
git remote add origin https://github.com/YOUR_USERNAME/telegram-payment-bot.git
git branch -M main
git push -u origin main
```

---

### 2. Railway (2 минуты)

1. [railway.app](https://railway.app) → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo**
3. Выберите `telegram-payment-bot`
4. Railway начнет деплой

---

### 3. Переменные (1 минута)

В Railway → **Variables** → **Raw Editor**:

```env
BOT_TOKEN=ваш_токен_от_BotFather
ADMIN_IDS=ваш_telegram_id
NOWPAYMENTS_API_KEY=ваш_nowpayments_api_key
NOWPAYMENTS_IPN_SECRET=ваш_ipn_secret
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db
LOG_LEVEL=INFO
```

**Update Variables** → Railway редеплоит

---

### 4. Проверка

Railway → **Logs** → должны увидеть:

```
✅ Bot started successfully!
Bot username: @YourBot
```

Telegram → Ваш бот → `/start` ✅

---

## Готово! 🎉

**Автодеплой:** Каждый `git push` обновляет бота

**Откат:** Railway → Deployments → Rollback

**Логи:** Railway → Logs (real-time)

**Стоимость:** $5 бесплатно/месяц

---

📖 **Подробная инструкция:** `RAILWAY_DEPLOYMENT_GUIDE.md`
