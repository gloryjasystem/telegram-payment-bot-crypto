# MarketFilter Payment Bot 💳

Professional Telegram bot for processing cryptocurrency payments for advertising placement and channel verification services using NOWPayments payment gateway.

---

## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Local Development](#local-development)
  - [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [NOWPayments API Setup](#nowpayments-api-setup)
  - [Terms & Policies](#terms--policies)
- [Database](#database)
  - [Schema](#schema)
  - [Migrations](#migrations)
- [Usage](#usage)
  - [User Workflow](#user-workflow)
  - [Admin Commands](#admin-commands)
- [API Integration](#api-integration)
  - [NOWPayments Payment Gateway](#nowpayments-payment-gateway)
  - [Webhook Configuration](#webhook-configuration)
- [Development](#development)
  - [Project Structure Details](#project-structure-details)
  - [Adding New Features](#adding-new-features)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [License](#license)

---

## ✨ Features

- **Professional Payment Flow**: Guided invoice creation with Web App payment integration
- **NOWPayments Integration**: Secure cryptocurrency payment processing
- **FSM-Based Admin Panel**: Step-by-step invoice creation with validation
- **Real-time Notifications**: Instant notifications to users and admins on payment events
- **Anti-Spam Protection**: Rate limiting and spam prevention
- **Comprehensive Logging**: Full audit trail of all transactions
- **Terms & Refund Policy**: Built-in legal compliance for payment processor approval
- **Multi-Currency Support**: Accept BTC, ETH, USDT, and other cryptocurrencies
- **Database Persistence**: SQLite (dev) or PostgreSQL (production)
- **Webhook Security**: HMAC signature verification for payment callbacks

---

## 🛠 Tech Stack

- **Python**: 3.11+
- **Framework**: aiogram 3.x (async Telegram Bot API)
- **Database**: SQLAlchemy (async) with SQLite/PostgreSQL
- **Payment Gateway**: NOWPayments API
- **Web Server**: aiohttp (for webhooks)
- **Logging**: Python logging module
- **Containerization**: Docker & Docker Compose

---

## 📁 Project Structure

```
new tg payment bot crypto/
│
├── bot.py                          # Main bot entry point
├── config.py                       # Configuration management
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker container definition
├── docker-compose.yml              # Docker Compose setup
├── .env.example                    # Example environment variables
├── .gitignore                      # Git ignore rules
├── CLAUDE.md                       # Full technical specification
├── README.md                       # This file
│
├── database/
│   ├── __init__.py
│   ├── models.py                   # SQLAlchemy ORM models
│   └── db.py                       # Database connection management
│
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py            # User commands (/start, /help)
│   ├── admin_handlers.py           # Admin commands (/invoice)
│   ├── payment_handlers.py         # Payment webhooks
│   └── callback_handlers.py        # Inline keyboard callbacks
│
├── states/
│   ├── __init__.py
│   └── admin_states.py             # FSM states for admin actions
│
├── services/
│   ├── __init__.py
│   ├── payment_service.py          # NOWPayments API integration (compat shim)
│   ├── invoice_service.py          # Invoice management logic
│   └── notification_service.py     # User/admin notifications
│
├── middlewares/
│   ├── __init__.py
│   ├── auth_middleware.py          # Admin authentication
│   ├── antispam_middleware.py      # Rate limiting
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
│   ├── validators.py               # Input validation
│   └── helpers.py                  # Helper functions
│
└── data/
    └── .gitkeep
```

---

## 📌 Requirements

- Python 3.11 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- NOWPayments Account & API Key
- (Optional) PostgreSQL for production
- (Optional) Docker & Docker Compose

---

## 🚀 Installation

### Local Development

#### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd "new tg payment bot crypto"
```

#### Step 2: Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your values
notepad .env  # Windows
nano .env     # Linux/macOS
```

Fill in **required** values:
- `BOT_TOKEN` - Your Telegram bot token
- `ADMIN_IDS` - Comma-separated admin Telegram IDs
- `NOWPAYMENTS_API_KEY` - Your NOWPayments API key
- `NOWPAYMENTS_IPN_SECRET` - Your IPN secret for webhook verification

#### Step 5: Initialize Database

```bash
python -c "from database.db import create_tables; import asyncio; asyncio.run(create_tables())"
```

This creates `bot_database.db` in the project directory.

#### Step 6: Run the Bot

```bash
python bot.py
```

You should see:
```
INFO - Bot started successfully!
INFO - Bot username: @YourBillingBot
```

---

### Docker Deployment

#### Step 1: Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

#### Step 2: Build and Start

```bash
docker-compose up --build -d
```

#### Step 3: View Logs

```bash
docker-compose logs -f bot
```

#### Step 4: Stop the Bot

```bash
docker-compose down
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# ========================================
# BOT CONFIGURATION
# ========================================
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789,987654321

# ========================================
# DATABASE
# ========================================
# SQLite (Development)
DATABASE_URL=sqlite+aiosqlite:///./bot_database.db

# PostgreSQL (Production)
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/marketfilter_bot

# ========================================
# NOWPAYMENTS API
# ========================================
NOWPAYMENTS_API_KEY=your_nowpayments_api_key_here
NOWPAYMENTS_IPN_SECRET=your_ipn_secret_here
NOWPAYMENTS_WEBHOOK_URL=https://yourdomain.com/webhook/nowpayments

# ========================================
# WEBHOOK (Production Only)
# ========================================
# Leave empty for polling mode (development)
WEBHOOK_URL=
WEBHOOK_PATH=/webhook/telegram
NOWPAYMENTS_WEBHOOK_PATH=/webhook/nowpayments
WEB_SERVER_HOST=0.0.0.0
WEB_SERVER_PORT=8080

# ========================================
# LOGGING
# ========================================
LOG_LEVEL=INFO
LOG_FILE=bot.log

# ========================================
# RATE LIMITING
# ========================================
RATE_LIMIT_MESSAGES=5
RATE_LIMIT_WINDOW=60

# ========================================
# TERMS & POLICIES
# ========================================
TERMS_OF_SERVICE_URL=https://telegra.ph/MarketFilter-Terms-of-Service-01-01
REFUND_POLICY_URL=https://telegra.ph/MarketFilter-Refund-Policy-01-01
SUPPORT_USERNAME=MarketFilterSupport
```

### NOWPayments API Setup

1. **Create Account**
   - Go to [NOWPayments](https://nowpayments.io/)
   - Sign up and verify your account
   - Navigate to **Store Settings** → **API Keys**

2. **Get API Credentials**
   - Copy **API Key**
   - Create **IPN Secret** for webhook verification

3. **Configure Webhook (IPN)**
   - Webhook URL: `https://yourdomain.com/webhook/nowpayments`
   - Events: `payment_status`

4. **Test Mode**
   - Use Sandbox environment for development
   - Switch to production keys when ready

### Terms & Policies

Create Telegraph pages for legal compliance:

#### 1. Terms of Service

1. Go to [telegra.ph](https://telegra.ph/)
2. Create new page titled **"MarketFilter - Условия обслуживания"**
3. Content template:

```markdown
# MarketFilter - Условия обслуживания

## 1. Общие положения
Мы оказываем услуги по размещению рекламных материалов и верификации Telegram-каналов.

## 2. Описание услуг
- **Размещение рекламы**: публикация рекламных постов в согласованных каналах
- **Верификация**: получение официального знака MarketFilter

## 3. Сроки выполнения
- Размещение рекламы: от 24 до 72 часов после оплаты
- Верификация: от 1 до 5 рабочих дней

## 4. Обязательства сторон
- Клиент обязуется предоставить корректные рекламные материалы
- Исполнитель обязуется выполнить услугу в согласованные сроки

## 5. Контакты
Поддержка: @MarketFilterSupport
```

4. Publish and copy URL to `.env` → `TERMS_OF_SERVICE_URL`

#### 2. Refund Policy

1. Create new page titled **"MarketFilter - Политика возврата"**
2. Content template:

```markdown
# MarketFilter - Политика возврата

## 1. Условия возврата
Возврат средств возможен в следующих случаях:
- Услуга не была оказана в согласованные сроки
- Отказ от услуги до начала выполнения работ

## 2. Невозвратные ситуации
- Услуга уже выполнена
- Клиент предоставил некорректные данные
- Изменение решения после начала работ

## 3. Процедура возврата
1. Обратитесь к вашему менеджеру или в поддержку @MarketFilterSupport
2. Укажите номер инвойса и причину возврата
3. Возврат осуществляется в течение 3-5 рабочих дней

## 4. Способ возврата
Возврат производится в криптовалюте на указанный кошелек
```

3. Publish and copy URL to `.env` → `REFUND_POLICY_URL`

---

## 🗄 Database

### Schema

The bot uses three main tables:

#### 1. Users Table

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
```

Stores user information when they first interact with the bot.

#### 2. Invoices Table

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
    external_invoice_id VARCHAR(255),  -- NOWPayments payment ID
    admin_id BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

Stores invoice information created by admins.

**Status Values:**
- `pending` - Waiting for payment
- `paid` - Payment confirmed
- `expired` - Invoice expired (1 hour timeout)
- `cancelled` - Manually cancelled by admin

#### 3. Payments Table

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
```

Stores payment transaction details from NOWPayments.

### Migrations

For production deployments with schema changes, use **Alembic**:

```bash
# Install Alembic
pip install alembic

# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

---

## 📖 Usage

### User Workflow

1. **Start Bot**
   - User clicks bot link from manager
   - Sends `/start` command
   - Receives welcome message with Terms of Service and Refund Policy links

2. **Receive Invoice**
   - Admin creates invoice using `/invoice` command
   - User receives invoice message with Web App payment button

3. **Make Payment**
   - User clicks "💳 Перейти к оплате" button
   - Opens NOWPayments page inside Telegram
   - Selects cryptocurrency (BTC, ETH, USDT, etc.)
   - Completes payment

4. **Payment Confirmation**
   - User receives success message
   - Admin receives payment notification
   - Invoice status updated to "paid"

### Admin Commands

#### `/invoice` - Create Invoice

**Step-by-Step Flow:**

```
Admin: /invoice

Bot: Введите ID пользователя или @username клиента
Admin: @johndoe

Bot: Введите сумму в USD (например: 150 или 150.50)
Admin: 150

Bot: Введите описание услуги
Admin: Размещение рекламы на 7 дней

Bot: [Shows preview]
  Подтвердите создание инвойса:
  
  Клиент: @johndoe (ID: 123456789)
  Сумма: $150
  Услуга: Размещение рекламы на 7 дней
  
  [✅ Подтвердить] [❌ Отменить]

Admin: [Clicks ✅ Подтвердить]

Bot: ✅ Счет выставлен успешно
     Invoice ID: #INV-1707398400
```

**Alternative Syntax (One Command):**

```bash
/invoice @username 150 Размещение рекламы на 7 дней
# OR
/invoice 123456789 150 Верификация канала
```

#### `/cancel` - Cancel Current Operation

Cancel any FSM state and return to normal mode.

#### `/stats` - View Statistics (Future Feature)

View payment statistics, revenue, etc.

---

## 🔌 API Integration

### NOWPayments Payment Gateway

#### Create Payment Invoice

```python
import aiohttp
import hmac
import hashlib
import json

async def create_invoice(amount: float, order_id: str):
    url = "https://api.nowpayments.io/v1/invoice"
    
    payload = {
        "price_amount": amount,
        "price_currency": "usd",
        "order_id": order_id,
        "ipn_callback_url": f"{WEBHOOK_URL}/webhook/nowpayments",
        "is_fixed_rate": False
    }
    
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json()
            return data["invoice_url"]  # Payment URL
```

#### Verify IPN Signature

```python
def verify_ipn(raw_body: bytes, signature: str) -> bool:
    calculated = hmac.new(
        IPN_SECRET.encode(),
        raw_body,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(calculated, signature)
```

### Webhook Configuration

**Webhook Endpoint:** `/webhook/nowpayments`

**IPN Payload Example:**

```json
{
  "payment_id": "5745065052",
  "order_id": "INV-1707398400",
  "payment_status": "finished",
  "pay_amount": 150,
  "pay_currency": "usdttrc20",
  "actually_paid": 150,
  "outcome_amount": 150
}
```

**Handling IPN Webhook:**

1. Verify signature in `x-nowpayments-sig` header (HMAC SHA512)
2. Check `payment_status` field (`finished` = paid)
3. Update invoice status in database
4. Send notifications to user and admin
5. Return `200 OK` to NOWPayments

---

## 🔧 Development

### Project Structure Details

#### `bot.py` - Main Entry Point

Initializes bot, registers handlers, starts polling/webhook.

```python
async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # Setup database
    await init_db()
    
    # Register middlewares
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(AntiSpamMiddleware())
    
    # Register routers
    dp.include_router(user_router)
    dp.include_router(admin_router)
    
    # Start bot
    await dp.start_polling(bot)
```

#### `handlers/` - Message Handlers

- **user_handlers.py**: `/start`, `/help`, callback queries
- **admin_handlers.py**: `/invoice` with FSM states
- **payment_handlers.py**: Webhook processing

#### `services/` - Business Logic

- **payment_service.py**: NOWPayments API compat shim → nowpayments_service.py
- **invoice_service.py**: Invoice CRUD operations
- **notification_service.py**: Send messages to users/admins

#### `middlewares/` - Request Processing

- **auth_middleware.py**: Check if user is admin for admin commands
- **antispam_middleware.py**: Rate limit: 5 messages/minute
- **logging_middleware.py**: Log all requests

### Adding New Features

#### Example: Add `/refund` Command

1. **Create handler** in `handlers/admin_handlers.py`:

```python
@admin_router.message(Command("refund"))
async def refund_command(message: Message, state: FSMContext):
    await message.answer("Введите Invoice ID для возврата:")
    await state.set_state(RefundStates.waiting_for_invoice_id)
```

2. **Add FSM state** in `states/admin_states.py`:

```python
class RefundStates(StatesGroup):
    waiting_for_invoice_id = State()
    waiting_for_confirmation = State()
```

3. **Implement refund logic** in `services/payment_service.py`:

```python
async def process_refund(invoice_id: str):
    # Call NOWPayments API
    # Update database
    # Notify user
    pass
```

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] **User Flow**
  - [ ] Send `/start` → verify welcome message
  - [ ] Click "Условия обслуживания" → opens Telegraph
  - [ ] Click "Политика возврата" → opens Telegraph
  - [ ] Send `/help` → shows help message

- [ ] **Admin Flow**
  - [ ] Send `/invoice` as admin → starts FSM
  - [ ] Enter valid user ID → proceeds to amount
  - [ ] Enter valid amount → proceeds to service description
  - [ ] Enter service description → shows preview
  - [ ] Confirm → creates invoice and sends to user

- [ ] **Payment Flow**
  - [ ] User receives invoice with Web App button
  - [ ] Click payment button → opens NOWPayments page
  - [ ] Complete test payment → webhook received
  - [ ] User receives success message
  - [ ] Admin receives payment notification

- [ ] **Error Handling**
  - [ ] Send `/invoice` as non-admin → access denied
  - [ ] Enter invalid amount → error message
  - [ ] Enter invalid user ID → error message
  - [ ] Send too many messages → rate limited

### Automated Testing (Future)

Add unit tests for:
- Input validation functions
- Payment signature verification
- Invoice creation logic
- Database operations

---

## 🚢 Deployment

### Production Checklist

- [ ] **Environment**
  - [ ] Use PostgreSQL instead of SQLite
  - [ ] Set `DATABASE_URL` to PostgreSQL connection string
  - [ ] Use strong `NOWPAYMENTS_IPN_SECRET`

- [ ] **Security**
  - [ ] Enable HTTPS for webhooks
  - [ ] Verify all webhook signatures
  - [ ] Use environment variables, never hardcode secrets
  - [ ] Set proper file permissions on `.env` (600)

- [ ] **Performance**
  - [ ] Use webhook mode instead of polling
  - [ ] Enable database connection pooling
  - [ ] Set up Redis for rate limiting (optional)

- [ ] **Monitoring**
  - [ ] Set up log rotation (logrotate)
  - [ ] Monitor webhook failures
  - [ ] Track payment success rate
  - [ ] Set up error alerts

### Docker Production Deployment

**docker-compose.production.yml:**

```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - postgres
    networks:
      - bot-network

  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: marketfilter_bot
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - bot-network

volumes:
  postgres-data:

networks:
  bot-network:
```

**Deploy:**

```bash
docker-compose -f docker-compose.production.yml up -d
```

---

## 🐛 Troubleshooting

### Bot doesn't respond

**Check:**
1. Bot token is correct in `.env`
2. Bot is running (`python bot.py` shows no errors)
3. Bot is not already running in another process
4. Admin IDs are correct

**Debug:**
```bash
# Check logs
tail -f bot.log

# Test bot token
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe
```

### Webhook not receiving payments

**Check:**
1. Webhook URL is accessible (HTTPS required)
2. NOWPayments IPN webhook is configured correctly
3. Signature verification passes
4. Firewall allows incoming connections

**Debug:**
```bash
# Check webhook logs
grep "webhook" bot.log

# Test webhook locally with ngrok
ngrok http 8080
# Update WEBHOOK_URL in .env
```

### Database errors

**Check:**
1. Database file exists (`bot_database.db`)
2. Database tables created
3. Write permissions on database file

**Fix:**
```bash
# Recreate database
rm bot_database.db
python -c "from database.db import create_tables; import asyncio; asyncio.run(create_tables())"
```

### Payment not confirming

**Check:**
1. NOWPayments API keys are correct
2. Invoice was created successfully
3. IPN webhook received `payment_status: "finished"`
4. Invoice status updated in database

**Debug:**
```python
# Check invoice status
from database.db import get_session
from database.models import Invoice

async with get_session() as session:
    invoice = await session.get(Invoice, invoice_id="INV-xxx")
    print(invoice.status)
```

---

## 🔒 Security

### Best Practices

1. **Never commit `.env` file**
   - Add to `.gitignore`
   - Use `.env.example` as template

2. **Verify webhook signatures**
   - Always use `hmac.compare_digest()` to prevent timing attacks
   - Log invalid signature attempts

3. **Validate user inputs**
   - Sanitize amounts (positive, max 2 decimals)
   - Validate user IDs exist
   - Limit service description length

4. **Rate limiting**
   - Prevent spam and abuse
   - Default: 5 messages per minute

5. **Admin authentication**
   - Check `ADMIN_IDS` before executing admin commands
   - Log unauthorized access attempts

6. **Database security**
   - Use parameterized queries (SQLAlchemy ORM handles this)
   - Regular backups
   - Encrypt sensitive data in production

7. **API keys**
   - Store in environment variables
   - Never log API keys
   - Rotate periodically

---

## 📄 License

This project is proprietary software for MarketFilter. All rights reserved.

---

## 📞 Support

For technical support or questions:
- **Telegram**: @MarketFilterSupport
- **Email**: support@marketfilter.com

---

## 🎯 Verification After Installation

After installing and setting up the bot, verify everything works:

### 1. Environment Check
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Verify dependencies
pip list | grep aiogram
pip list | grep sqlalchemy
```

### 2. Configuration Check
```bash
# Verify .env file exists and has values
cat .env | grep BOT_TOKEN
cat .env | grep NOWPAYMENTS_API_KEY
```

### 3. Database Check
```bash
# Check database file exists
ls -lh bot_database.db

# Verify tables created
sqlite3 bot_database.db "SELECT name FROM sqlite_master WHERE type='table';"
# Should show: users, invoices, payments
```

### 4. Bot Startup Check
```bash
# Start bot
python bot.py

# Expected output:
# INFO - Bot started successfully!
# INFO - Bot username: @YourBillingBot
```

### 5. Telegram Check
- Open Telegram and search for your bot
- Send `/start` → Should receive welcome message
- Send `/help` → Should receive help message
- Click buttons → Should open Telegraph pages

### 6. Admin Check (requires admin ID in .env)
- Send `/invoice` → Should start FSM flow
- Follow prompts to create test invoice
- Verify invoice message sent to user

### 7. Webhook Check (production only)
```bash
# Test webhook endpoint
curl -X POST https://yourdomain.com/webhook/nowpayments \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: test" \
  -d '{"test": "payload"}'

# Should return 200 OK
```

---

**🎉 Congratulations! Your MarketFilter Payment Bot is ready to process payments professionally!**
