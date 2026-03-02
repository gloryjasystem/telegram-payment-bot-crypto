# 🤖 Получение токена бота от @BotFather

## Проблема
При запуске `python bot.py` видите ошибку:
```
TokenValidationError: Token is invalid!
```

Это означает, что в файле `.env` указан неправильный или placeholder токен.

## Решение: Получите новый токен от @BotFather

### Шаг 1: Откройте @BotFather в Telegram
1. Откройте Telegram
2. Найдите бота **@BotFather**
3. Нажмите `/start`

### Шаг 2: Создайте нового бота
1. Отправьте команду `/newbot`
2. @BotFather спросит имя бота:
   ```
   Alright, a new bot. How are we going to call it?
   Please choose a name for your bot.
   ```
   Введите: `MarketFilter Payment Bot` (или любое другое имя)

3. @BotFather попросит username:
   ```
   Good. Now let's choose a username for your bot.
   It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
   ```
   Введите: `marketfilter_payment_bot` (или другой уникальный username)
   
   **Важно**: Username ДОЛЖЕН заканчиваться на `bot`

### Шаг 3: Получите токен
@BotFather ответит примерно так:
```
Done! Congratulations on your new bot. You will find it at t.me/marketfilter_payment_bot.

Use this token to access the HTTP API:
8475634513:AAE_ZOjKR7pqoZ39H8kzcyOcGtMdEOj2V2I

Keep your token secure and store it safely, it can be used by anyone to control your bot.

For a description of the Bot API, see this page: https://core.telegram.org/bots/api
```

**Скопируйте токен** (например: `8475634513:AAE_ZOjKR7pqoZ39H8kzcyOcGtMdEOj2V2I`)

### Шаг 4: Обновите .env файл

Откройте файл `.env` и замените строку:
```bash
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
```

На:
```bash
BOT_TOKEN=8475634513:AAE_ZOjKR7pqoZ39H8kzcyOcGtMdEOj2V2I
```
(используйте ВАШИХ токен от @BotFather)

### Шаг 5: Получите ваш Telegram ID

1. Найдите в Telegram бота **@userinfobot**
2. Нажмите `/start`
3. Бот покажет ваш ID, например: `6034732402`

### Шаг 6: Обновите ADMIN_IDS в .env

Замените:
```bash
ADMIN_IDS=123456789
```

На:
```bash
ADMIN_IDS=6034732402
```
(используйте ваш реальный ID)

Если несколько админов:
```bash
ADMIN_IDS=6034732402,987654321,111222333
```

### Шаг 7: Запустите бота снова

```bash
python bot.py
```

Теперь вы должны увидеть:
```
[13:56:15] INFO - 🚀 Starting bot...
[13:56:15] INFO - ✅ Configuration validated
[13:56:15] INFO - ✅ Database initialized
[13:56:15] INFO - ✅ Bot started successfully!
[13:56:15] INFO - Bot username: @marketfilter_payment_bot
[13:56:15] INFO - Admins: [6034732402]
[13:56:15] INFO - Starting polling...
```

✅ **БОТ РАБОТАЕТ!**

## Дополнительные настройки (опционально)

### Установка команд бота
После запуска отправьте @BotFather команду:
```
/setcommands
```

Выберите вашего бота, затем отправьте:
```
start - Начать работу с ботом
help - Показать справку
terms - Условия обслуживания
refund - Политика возврата
invoice - [Admin] Создать инвойс
cancel - [Admin] Отменить текущее действие
```

### Настройка описания бота
```
/setdescription
```
Введите:
```
Бот для приема платежей в криптовалюте через NOWPayments API
```

### Настройка about
```
/setabouttext
```
Введите:
```
MarketFilter Payment Bot - профессиональная система приема крипто-платежей
```

---

## Проверка работы

### 1. Отправьте /start боту
Откройте вашего бота в Telegram и нажмите `/start`

**Ожидаемый ответ**:
```
Привет, [Ваше имя]! 👋

Добро пожаловать в платежного бота MarketFilter.
...
[Кнопки: Условия | Возврат | Поддержка]
```

### 2. Создайте инвойс (как админ)
Отправьте `/invoice`

**Ожидаемый ответ**:
```
📝 Создание инвойса

Шаг 1/3: Введите Telegram ID или @username клиента:
...
```

---

## Troubleshooting

### "User not found в БД"
**Проблема**: При создании инвойса для пользователя появляется "пользователь не найден"

**Решение**: Попросите клиента сначала отправить `/start` боту, чтобы он был зарегистрирован в БД

### Бот не отвечает
**Решение**: 
1. Проверьте что бот запущен (`python bot.py` работает)
2. Проверьте логи: `cat data/logs/bot.log`
3. Проверьте ошибки: `cat data/logs/bot_errors.log`

### NOWPayments API not configured
**Это нормально!** Бот работает в MOCK режиме:
```
[13:56:15] WARNING - ⚠️ NOWPayments API not configured - using MOCK mode
```

MOCK mode позволяет тестировать весь функционал без реальных API ключей NOWPayments.

---

## Готово! 🎉

Ваш бот успешно настроен и готов к использованию!

**Следующие шаги**:
1. Протестируйте все команды
2. Создайте тестовый инвойс
3. Проверьте FSM процесс
4. При необходимости настройте реальные NOWPayments API ключи
