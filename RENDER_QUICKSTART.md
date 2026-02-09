# 🚀 Быстрый старт деплоя на Render

## Краткая инструкция (5 минут)

### 1️⃣ Загрузка кода на GitHub

```powershell
# В папке проекта
cd "c:\Users\secvency\Desktop\new tg payment bot crypto"

# Инициализация Git
git init
git add .
git commit -m "Ready for Render deployment"

# Подключение GitHub (замените YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/telegram-payment-bot.git
git branch -M main
git push -u origin main
```

### 2️⃣ Деплой на Render

1. Зайти на [render.com](https://render.com) → Sign up with GitHub
2. **New +** → **Web Service**
3. Подключить ваш репозиторий
4. Настройки:
   - Name: `telegram-payment-bot`
   - Runtime: **Docker**
   - Instance Type: **Free**

### 3️⃣ Переменные окружения

Добавить в Render (скопировать из вашего `.env`):

```
BOT_TOKEN=ваш_токен
CRYPTOMUS_MERCHANT_ID=ваш_merchant_id
CRYPTOMUS_API_KEY=ваш_api_key
ADMIN_IDS=ваш_telegram_id
```

### 4️⃣ Deploy!

Нажать **Create Web Service** → Ждать ~5 минут → Готово! ✅

---

## ⚠️ Важно после деплоя

### Предотвращение засыпания

Render free tier засыпает через 15 минут. Решение:

**UptimeRobot** (бесплатно):
1. [uptimerobot.com](https://uptimerobot.com) → Sign up
2. Add New Monitor → HTTP(s)
3. URL: `https://ваш-бот.onrender.com`
4. Interval: **5 minutes**

### Webhook для Cryptomus

В Cryptomus Dashboard:
```
Webhook URL: https://ваш-бот.onrender.com/webhook/cryptomus
```

---

## 📝 Обновление кода

```powershell
git add .
git commit -m "описание изменений"
git push origin main
# Render автоматически передеплоит!
```

---

**Подробная инструкция:** См. `RENDER_DEPLOYMENT_GUIDE.md`

**Проблемы?** Проверьте логи в Render → вкладка Logs
