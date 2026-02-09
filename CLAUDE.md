# CLAUDE.md - Telegram Payment Bot Specification

## Project Overview
**Project Name:** MarketFilter Payment Bot  
**Purpose:** Professional Telegram bot for processing payments for advertising placement and verification services through Cryptomus/Heleket payment gateways  
**Primary Language:** Python 3.11+  
**Framework:** aiogram 3.x (async Telegram Bot API framework)

---

## Bot Behavior & Message Flows

### 1. User Journey Flow

#### Flow 1: Manager → Client Communication (Outside Bot)
**Context:** Manager discusses pricing with client in private messages

**Manager Message Template:**
```
Благодарю за согласование. Для обеспечения безопасности транзакции и автоматического учета вашей заявки, мы используем наш официальный платежный шлюз.

Пожалуйста, перейдите в наш бот-кассир: @YourBillingBot
Нажмите кнопку START, и я моментально выставлю вам счет на согласованную сумму ($XXX).
```

#### Flow 2: Client Starts Bot (`/start` command)
**Trigger:** Client clicks START or sends `/start`

**Bot Response:**
```
Добро пожаловать в финансовый департамент MarketFilter 💳

Данный бот предназначен для безопасной оплаты услуг размещения рекламы и верификации каналов через сертифицированные платежные шлюзы.

Как это работает:
✅ Дождитесь уведомления о выставленном счете от вашего менеджера.
✅ Проверьте детали (услуга, сумма).
✅ Нажмите "Оплатить" и выберите удобный способ оплаты.

Ваши платежные данные защищены и не сохраняются в системе.
```

**Inline Keyboard:**
```
[📋 Условия обслуживания] [↩️ Политика возврата]
[❓ Помощь]
```

#### Flow 3: Admin Creates Invoice (`/invoice user_id amount service_description`)
**Trigger:** Admin sends `/invoice` command

**Command Format:**
```
/invoice @username 150 Размещение рекламы на 7 дней
OR
/invoice 123456789 150 Верификация канала MarketFilter
```

**Admin Confirmation Message:**
```
✅ Счет выставлен успешно

Клиент: @username (ID: 123456789)
Сумма: $150
Услуга: Размещение рекламы на 7 дней
Система: Cryptomus Gateway
Статус: Ожидание транзакции...

Invoice ID: #INV-1234567890
```

#### Flow 4: Client Receives Invoice
**Invoice Message to Client:**
```
🧾 Электронный инвойс №INV-1234567890
────────────────────

Услуга: Размещение рекламы на 7 дней
Статус: Ожидает оплаты
К оплате: 150 USD

────────────────────
Нажмите на кнопку ниже, чтобы перейти на защищенную страницу оплаты Cryptomus/Heleket.
Вы сможете выбрать любую удобную криптовалюту.
```

**Inline Keyboard:**
```
[💳 Перейти к оплате 150 USD] ← Web App Button
```

#### Flow 5: Payment Success
**Message to Client:**
```
✅ Оплата получена!

Ваш платеж на сумму $150 успешно обработан.

Информация о вашей заявке передана в отдел исполнения. Менеджер свяжется с вами в ближайшее время для подтверждения публикации.

Спасибо, что выбрали MarketFilter!
```

**Message to Admin:**
```
💰 ПОСТУПИЛА ОПЛАТА

Заказ: #INV-1234567890
Клиент: @username (ID: 123456789)
Сумма: $150
Услуга: Размещение рекламы на 7 дней

✅ Можно приступать к выполнению заявки.
```

#### Flow 6: Help Command (`/help`)
**Bot Response:**
```
❓ Помощь и поддержка MarketFilter Payment Bot

Основные команды:
/start - Начать работу с ботом
/help - Показать это сообщение

Как оплатить услугу:
1. Получите уведомление от менеджера о выставленном счете
2. Проверьте детали услуги и сумму
3. Нажмите кнопку "Перейти к оплате"
4. Выберите удобную криптовалюту
5. Совершите платеж

Если у вас возникли вопросы, обратитесь к вашему менеджеру или в поддержку.
```

**Inline Keyboard:**
```
[📋 Условия обслуживания] [↩️ Политика возврата]
[💬 Связаться с поддержкой]
```

---

## Project Structure

```
new tg payment bot crypto/
│
├── bot.py                          # Main bot entry point
├── config.py                       # Configuration and environment variables
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker container definition
├── docker-compose.yml              # Docker Compose configuration
├── .env.example                    # Example environment variables
├── .gitignore                      # Git ignore file
├── CLAUDE.md                       # This specification file
├── README.md                       # Project documentation
│
├── database/
│   ├── __init__.py
│   ├── models.py                   # SQLAlchemy database models
│   ├── db.py                       # Database connection and session management
│   └── migrations/                 # Alembic migrations (if using Alembic)
│
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py            # User command handlers (/start, /help)
│   ├── admin_handlers.py           # Admin command handlers (/invoice, /stats)
│   ├── payment_handlers.py         # Payment callbacks and webhooks
│   └── callback_handlers.py        # Inline keyboard callback handlers
│
├── states/
│   ├── __init__.py
│   └── admin_states.py             # FSM states for admin invoice creation
│
├── services/
│   ├── __init__.py
│   ├── payment_service.py          # Cryptomus/Heleket API integration
│   ├── invoice_service.py          # Invoice creation and management
│   └── notification_service.py     # User/admin notification logic
│
├── middlewares/
│   ├── __init__.py
│   ├── auth_middleware.py          # Admin authentication
│   ├── antispam_middleware.py      # Rate limiting and anti-spam
│   └── logging_middleware.py       # Request/response logging
│
├── keyboards/
│   ├── __init__.py
│   ├── user_keyboards.py           # User inline keyboards
│   └── admin_keyboards.py          # Admin inline keyboards
│
├── utils/
│   ├── __init__.py
│   ├── logger.py                   # Logging configuration
│   ├── validators.py               # Input validation functions
│   └── helpers.py                  # Helper functions
│
└── data/
    └── .gitkeep                     # Keep directory in git
```

---

## File Descriptions

### Core Files

#### `bot.py`
**Purpose:** Main application entry point  
**Responsibilities:**
- Initialize bot and dispatcher
- Register all handlers and middlewares
- Start polling or webhook server
- Graceful shutdown handling

**Key Components:**
```python
async def main():
    # Initialize bot
    # Setup database
    # Register routers
    # Start polling
```

#### `config.py`
**Purpose:** Configuration management  
**Responsibilities:**
- Load environment variables
- Validate configuration
- Provide configuration objects

**Configuration Sections:**
- Bot settings (token, admin IDs)
- Database settings (connection string)
- Payment gateway settings (API key, merchant ID)
- Logging settings
- Rate limiting settings

**Example Structure:**
```python
class Config:
    BOT_TOKEN: str
    ADMIN_IDS: list[int]
    DATABASE_URL: str
    CRYPTOMUS_API_KEY: str
    CRYPTOMUS_MERCHANT_ID: str
    WEBHOOK_URL: str (optional)
```

### Database Module

#### `database/models.py`
**Purpose:** Define database schema using SQLAlchemy ORM

**Models:**

**1. User Model**
```python
class User(Base):
    id: int (primary key)
    telegram_id: int (unique)
    username: str (nullable)
    first_name: str
    last_name: str (nullable)
    created_at: datetime
    updated_at: datetime
```

**2. Invoice Model**
```python
class Invoice(Base):
    id: int (primary key)
    invoice_id: str (unique, format: INV-{timestamp})
    user_id: int (foreign key → User)
    amount: Decimal
    currency: str (default: USD)
    service_description: str
    status: str (pending/paid/expired/cancelled)
    payment_url: str (nullable)
    cryptomus_invoice_id: str (nullable)
    created_at: datetime
    paid_at: datetime (nullable)
    admin_id: int (who created the invoice)
```

**3. Payment Model**
```python
class Payment(Base):
    id: int (primary key)
    invoice_id: int (foreign key → Invoice)
    transaction_id: str (from Cryptomus)
    amount: Decimal
    currency: str
    status: str
    payment_method: str (BTC, ETH, USDT, etc.)
    created_at: datetime
    confirmed_at: datetime (nullable)
```

#### `database/db.py`
**Purpose:** Database connection and session management

**Functions:**
- `init_db()`: Initialize database connection
- `get_session()`: Async session generator for dependency injection
- `create_tables()`: Create all tables (on first run)

### Handlers Module

#### `handlers/user_handlers.py`
**Purpose:** Handle user commands

**Handlers:**
- `/start` command
- `/help` command
- Callback handlers for:
  - Terms of Service button
  - Refund Policy button
  - Support button

#### `handlers/admin_handlers.py`
**Purpose:** Handle admin commands

**Handlers:**
- `/invoice` command (with FSM for step-by-step)
- `/stats` command (show statistics)
- `/cancel` command (cancel current operation)

**FSM States for Invoice Creation:**
```python
class InvoiceStates(StatesGroup):
    waiting_for_user = State()      # Enter user ID or @username
    waiting_for_amount = State()    # Enter amount
    waiting_for_service = State()   # Enter service description
    waiting_for_confirmation = State()  # Confirm invoice details
```

#### `handlers/payment_handlers.py`
**Purpose:** Handle payment webhooks and callbacks

**Handlers:**
- Cryptomus webhook handler (POST endpoint)
- Payment status updates
- Payment confirmation logic

#### `handlers/callback_handlers.py`
**Purpose:** Handle inline keyboard callbacks

**Callbacks:**
- `pay_invoice:{invoice_id}` - Open payment Web App
- `tos` - Show Terms of Service
- `refund` - Show Refund Policy
- `support` - Open support contact

### Services Module

#### `services/payment_service.py`
**Purpose:** Integrate with Cryptomus/Heleket API

**Functions:**
- `create_payment_invoice(amount, currency, order_id)` → returns payment URL
- `check_payment_status(invoice_id)` → returns payment status
- `verify_webhook_signature(request_data, signature)` → validates webhook authenticity
- `get_supported_currencies()` → returns list of available cryptocurrencies

**API Integration:**
- Endpoint: `https://api.cryptomus.com/v1/`
- Authentication: API Key + Merchant ID
- Webhook signature verification using HMAC SHA256

#### `services/invoice_service.py`
**Purpose:** Invoice creation and management logic

**Functions:**
- `create_invoice(user_id, amount, service_description, admin_id)` → creates invoice in DB
- `get_invoice(invoice_id)` → retrieves invoice
- `update_invoice_status(invoice_id, status)` → updates status
- `expire_old_invoices()` → mark expired invoices (runs periodically)

#### `services/notification_service.py`
**Purpose:** Send notifications to users and admins

**Functions:**
- `send_invoice_to_user(user_id, invoice_data)`
- `notify_admin_invoice_created(admin_id, invoice_data)`
- `notify_admin_payment_received(admin_id, payment_data)`
- `notify_user_payment_success(user_id, payment_data)`

### Middlewares Module

#### `middlewares/auth_middleware.py`
**Purpose:** Admin authentication

**Logic:**
- Check if user ID is in ADMIN_IDS list
- Block non-admins from using admin commands
- Log unauthorized access attempts

#### `middlewares/antispam_middleware.py`
**Purpose:** Rate limiting and spam protection

**Features:**
- Rate limit: max 5 messages per minute per user
- Command cooldown: 3 seconds between commands
- Store rate limit data in memory (or Redis for production)

#### `middlewares/logging_middleware.py`
**Purpose:** Log all incoming messages and commands

**Logs:**
- User ID, username, command, timestamp
- Response status
- Errors and exceptions

### Keyboards Module

#### `keyboards/user_keyboards.py`
**Purpose:** User-facing inline keyboards

**Keyboards:**
- `get_welcome_keyboard()` - Start screen with ToS, Refund, Help
- `get_invoice_keyboard(payment_url, amount)` - Payment Web App button
- `get_help_keyboard()` - Help screen with support link

#### `keyboards/admin_keyboards.py`
**Purpose:** Admin inline keyboards

**Keyboards:**
- `get_invoice_confirmation_keyboard()` - Confirm/Cancel invoice creation
- `get_stats_keyboard()` - Navigation for statistics

### Utils Module

#### `utils/logger.py`
**Purpose:** Logging configuration

**Setup:**
- Configure logging to file and console
- Separate log files for errors and general logs
- Log rotation (e.g., 10MB per file, keep last 5 files)
- Log format: `[%(asctime)s] %(levelname)s - %(name)s - %(message)s`

#### `utils/validators.py`
**Purpose:** Input validation

**Functions:**
- `validate_amount(amount_str)` → validates and converts amount to Decimal
- `validate_user_id(user_input)` → extracts user ID from @username or numeric ID
- `validate_service_description(text)` → ensures description is not empty

#### `utils/helpers.py`
**Purpose:** Helper functions

**Functions:**
- `generate_invoice_id()` → creates unique invoice ID (INV-{timestamp})
- `format_currency(amount)` → formats amount as $XXX.XX
- `escape_markdown(text)` → escapes special characters for Telegram markdown

---

## FSM (Finite State Machine) States

### Admin Invoice Creation Flow

**State Machine:** `InvoiceStates`

**State 1: `waiting_for_user`**
- **Entry:** Admin sends `/invoice` command
- **Prompt:** "Введите ID пользователя или @username"
- **Input:** User ID or @username
- **Validation:** Check if user exists in database
- **Next State:** `waiting_for_amount`

**State 2: `waiting_for_amount`**
- **Entry:** User ID validated
- **Prompt:** "Введите сумму в USD (например: 150 или 150.50)"
- **Input:** Amount (numeric)
- **Validation:** Must be positive number, max 2 decimal places
- **Next State:** `waiting_for_service`

**State 3: `waiting_for_service`**
- **Entry:** Amount validated
- **Prompt:** "Введите описание услуги (например: Размещение рекламы на 7 дней)"
- **Input:** Service description text
- **Validation:** Min 10 characters, max 200 characters
- **Next State:** `waiting_for_confirmation`

**State 4: `waiting_for_confirmation`**
- **Entry:** Service description provided
- **Prompt:** Show invoice preview with Confirm/Cancel buttons
- **Display:**
  ```
  Подтвердите создание инвойса:
  
  Клиент: @username (ID: 123456789)
  Сумма: $150
  Услуга: Размещение рекламы на 7 дней
  ```
- **Actions:**
  - ✅ Confirm → Create invoice, send to user, notify admin, clear state
  - ❌ Cancel → Cancel operation, clear state

**Cancel Command:** `/cancel` at any state returns to normal mode

---

## API Integration

### Cryptomus API

**Base URL:** `https://api.cryptomus.com/v1/`

**Authentication:**
- Header: `merchant: {MERCHANT_ID}`
- Header: `sign: {HMAC_SHA256_SIGNATURE}`

**Endpoints:**

#### 1. Create Payment Invoice
```http
POST /payment
Content-Type: application/json

{
  "amount": "150",
  "currency": "USD",
  "order_id": "INV-1234567890",
  "url_callback": "https://yourdomain.com/webhook/cryptomus",
  "url_success": "https://t.me/YourBillingBot",
  "is_payment_multiple": false,
  "lifetime": 3600
}

Response:
{
  "state": 0,
  "result": {
    "uuid": "cryptomus-uuid-here",
    "order_id": "INV-1234567890",
    "amount": "150",
    "currency": "USD",
    "url": "https://pay.cryptomus.com/pay/uuid",
    "expired_at": 1234567890
  }
}
```

#### 2. Check Payment Status
```http
POST /payment/info
Content-Type: application/json

{
  "uuid": "cryptomus-uuid-here",
  "order_id": "INV-1234567890"
}

Response:
{
  "state": 0,
  "result": {
    "uuid": "cryptomus-uuid-here",
    "order_id": "INV-1234567890",
    "status": "paid",
    "payment_amount": "150",
    "payer_amount": "150",
    "currency": "USD"
  }
}
```

#### 3. Webhook Handler
**Endpoint:** Your server receives POST request from Cryptomus

```http
POST /webhook/cryptomus
Content-Type: application/json
sign: {HMAC_SHA256_SIGNATURE}

{
  "uuid": "cryptomus-uuid-here",
  "order_id": "INV-1234567890",
  "status": "paid",
  "payment_amount": "150",
  "currency": "USD",
  "payer_currency": "USDT",
  "payer_amount": "150.00"
}
```

**Signature Verification:**
```python
import hmac
import hashlib
import json

def verify_signature(request_data: dict, signature: str, api_key: str) -> bool:
    # Sort keys and create string
    payload = json.dumps(request_data, sort_keys=True)
    
    # Calculate HMAC SHA256
    calculated_signature = hmac.new(
        api_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(calculated_signature, signature)
```

---

## Environment Variables

**File:** `.env`

```env
# Bot Configuration
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789,987654321

# Database
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db
# For PostgreSQL: postgresql+asyncpg://user:password@localhost/dbname

# Cryptomus API
CRYPTOMUS_API_KEY=your_cryptomus_api_key_here
CRYPTOMUS_MERCHANT_ID=your_merchant_id_here
CRYPTOMUS_WEBHOOK_SECRET=your_webhook_secret_here

# Webhook (optional, for production)
WEBHOOK_URL=https://yourdomain.com/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
CRYPTOMUS_WEBHOOK_PATH=/webhook/cryptomus
WEB_SERVER_HOST=0.0.0.0
WEB_SERVER_PORT=8080

# Logging
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Rate Limiting
RATE_LIMIT_MESSAGES=5
RATE_LIMIT_WINDOW=60

# Terms and Policies (Telegraph URLs)
TERMS_OF_SERVICE_URL=https://telegra.ph/MarketFilter-Terms-of-Service-01-01
REFUND_POLICY_URL=https://telegra.ph/MarketFilter-Refund-Policy-01-01
SUPPORT_USERNAME=MarketFilterSupport
```

---

## Database Schema

### Tables

#### `users`
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
```

#### `invoices`
```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    service_description TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    payment_url TEXT,
    cryptomus_invoice_id VARCHAR(255),
    admin_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_user_id ON invoices(user_id);
```

#### `payments`
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    transaction_id VARCHAR(255) UNIQUE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    payment_method VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);

CREATE INDEX idx_payments_transaction_id ON payments(transaction_id);
```

---

## Key Requirements

### 1. FSM States
- Use `aiogram.fsm` for state management
- States: `waiting_for_user`, `waiting_for_amount`, `waiting_for_service`, `waiting_for_confirmation`
- Allow `/cancel` to exit any state

### 2. API Integration
- Cryptomus API for payment processing
- Proper signature verification for webhooks
- Error handling for API failures
- Retry logic for failed API calls

### 3. Validation
- Amount: positive decimal, max 2 decimal places
- User ID: must exist in database or be valid Telegram ID
- Service description: 10-200 characters
- Signature verification for webhooks

### 4. Navigation
- Inline keyboards for all user interactions
- Web App button for payment (opens Cryptomus payment page inside Telegram)
- Back buttons where appropriate

### 5. Admin Notifications
- Invoice created notification
- Payment received notification
- Error notifications for failed operations

### 6. Logging
- All incoming messages
- All API calls
- All errors and exceptions
- Payment status changes

### 7. Anti-Spam
- Rate limiting: 5 messages per minute per user
- Command cooldown: 3 seconds
- Block spam bots

### 8. Database
- SQLite for development
- PostgreSQL for production
- Async database operations using `asyncpg` or `aiosqlite`
- Connection pooling

### 9. Error Handling
- Try-catch all API calls
- User-friendly error messages
- Admin notifications for critical errors
- Graceful degradation

---

## Critical Details

### 1. Web App Payment Button
**Implementation:**
```python
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

def get_payment_keyboard(payment_url: str, amount: float) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💳 Перейти к оплате ${amount}",
            web_app=WebAppInfo(url=payment_url)
        )]
    ])
    return keyboard
```

This opens payment page as overlay inside Telegram (professional look).

### 2. Webhook Security
- Always verify `sign` header from Cryptomus
- Use `hmac.compare_digest()` to prevent timing attacks
- Log all webhook requests
- Return 200 OK to Cryptomus even if processing fails (process async)

### 3. Invoice Expiration
- Set `lifetime: 3600` (1 hour) in Cryptomus API call
- Run periodic task to mark expired invoices
- Notify user if invoice expired

### 4. Idempotency
- Check if invoice already exists before creating
- Prevent duplicate payments for same invoice
- Use unique `order_id` for Cryptomus

### 5. Terms of Service & Refund Policy
**Create Telegraph pages:**
- Go to https://telegra.ph/
- Create "MarketFilter - Условия обслуживания"
- Create "MarketFilter - Политика возврата"
- Add URLs to `.env` file

**Content Suggestions:**

**Terms of Service:**
```
MarketFilter - Условия обслуживания

1. Общие положения
Мы оказываем услуги по размещению рекламных материалов и верификации Telegram-каналов.

2. Описание услуг
- Размещение рекламы: публикация рекламных постов в согласованных каналах
- Верификация: получение официального знака MarketFilter

3. Сроки
Размещение рекламы: от 24 до 72 часов после оплаты
Верификация: от 1 до 5 рабочих дней

4. Обязательства сторон
Клиент обязуется предоставить корректные материалы
Исполнитель обязуется выполнить услугу в согласованные сроки

5. Контакты
Поддержка: @MarketFilterSupport
```

**Refund Policy:**
```
MarketFilter - Политика возврата

1. Условия возврата
Возврат средств возможен в следующих случаях:
- Услуга не была оказана в согласованные сроки
- Отказ от услуги до начала выполнения

2. Невозвратные ситуации
- Услуга уже выполнена
- Клиент предоставил некорректные данные

3. Процедура возврата
Обратитесь к вашему менеджеру или в поддержку @MarketFilterSupport
Возврат осуществляется в течение 3-5 рабочих дней

4. Способ возврата
Возврат производится в криптовалюте на указанный кошелек
```

---

## Critical Files for Verification

After creating the project, **MUST CHECK**:

1. **`bot.py`**
   - Bot token loaded correctly
   - All routers registered
   - Database initialized
   - Graceful shutdown implemented

2. **`config.py`**
   - All environment variables loaded
   - Validation for required variables
   - Type conversion correct

3. **`database/models.py`**
   - All relationships defined
   - Indexes created
   - Default values set

4. **`handlers/admin_handlers.py`**
   - FSM states work correctly
   - Invoice creation flow complete
   - Validation at each step

5. **`services/payment_service.py`**
   - API signature calculation correct
   - Webhook verification works
   - Error handling for API failures

6. **`keyboards/user_keyboards.py`**
   - Web App button configured correctly
   - All URLs valid

7. **`.env` file**
   - All required variables present
   - No placeholder values in production

---

## Verification Checklist (After Project Creation)

### Step 1: Environment Setup
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Activate virtual environment:
  - Windows: `venv\Scripts\activate`
  - Linux/Mac: `source venv/bin/activate`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy `.env.example` to `.env`
- [ ] Fill in real values in `.env` (bot token, API keys)

### Step 2: Database Setup
- [ ] Run `python` and import database module
  ```python
  from database.db import init_db, create_tables
  import asyncio
  asyncio.run(create_tables())
  ```
- [ ] Check that `bot_database.db` file created
- [ ] Verify tables exist using SQLite viewer

### Step 3: Bot Startup
- [ ] Run `python bot.py`
- [ ] Check for errors in console
- [ ] Verify "Bot started successfully" message
- [ ] Check that bot responds in Telegram

### Step 4: User Flow Testing
- [ ] Send `/start` to bot
- [ ] Verify welcome message appears
- [ ] Click "Условия обслуживания" button → should open Telegraph
- [ ] Click "Политика возврата" button → should open Telegraph
- [ ] Send `/help` → should show help message

### Step 5: Admin Flow Testing
- [ ] Send `/invoice` from admin account
- [ ] Enter valid user ID
- [ ] Enter valid amount (e.g., 150)
- [ ] Enter service description
- [ ] Verify invoice preview shows correctly
- [ ] Confirm invoice creation
- [ ] Check that user receives invoice message
- [ ] Verify Web App button opens payment page

### Step 6: Payment Testing
- [ ] Use Cryptomus test environment
- [ ] Create test invoice
- [ ] Complete test payment
- [ ] Verify webhook received
- [ ] Check that invoice status updated to "paid"
- [ ] Verify user receives success message
- [ ] Verify admin receives payment notification

### Step 7: Error Handling
- [ ] Send invalid command → should ignore or show help
- [ ] Send `/invoice` as non-admin → should deny access
- [ ] Enter invalid amount → should show error and ask again
- [ ] Enter invalid user ID → should show error and ask again
- [ ] Test rate limiting by sending many messages quickly

### Step 8: Logging
- [ ] Check `bot.log` file created
- [ ] Verify all actions logged
- [ ] Check error logs for any issues

### Step 9: Docker Testing (Optional)
- [ ] Build image: `docker-compose build`
- [ ] Start container: `docker-compose up -d`
- [ ] Check logs: `docker-compose logs -f bot`
- [ ] Test bot functionality in container
- [ ] Stop container: `docker-compose down`

---

This specification provides complete guidance for building the MarketFilter Payment Bot. Follow this document exactly when implementing the bot to ensure all features work correctly and professionally for payment processor moderation approval.
