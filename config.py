"""
Конфигурация бота и загрузка переменных окружения
"""
import os
import json
from typing import List
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


class Config:
    """Класс конфигурации бота"""
    
    # ========================================
    # BOT SETTINGS
    # ========================================
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [
        int(admin_id.strip()) 
        for admin_id in os.getenv("ADMIN_IDS", "").split(",") 
        if admin_id.strip()
    ]
    
    # ========================================
    # DATABASE SETTINGS
    # ========================================
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite+aiosqlite:///./bot_database.db"
    )
    
    # ========================================
    # CRYPTOMUS API SETTINGS (Legacy - можно удалить после миграции)
    # ========================================
    CRYPTOMUS_API_KEY: str = os.getenv("CRYPTOMUS_API_KEY", "")
    CRYPTOMUS_MERCHANT_ID: str = os.getenv("CRYPTOMUS_MERCHANT_ID", "")
    CRYPTOMUS_WEBHOOK_SECRET: str = os.getenv("CRYPTOMUS_WEBHOOK_SECRET", "")
    
    # ========================================
    # NOWPAYMENTS API SETTINGS
    # ========================================
    NOWPAYMENTS_API_KEY: str = os.getenv("NOWPAYMENTS_API_KEY", "")
    NOWPAYMENTS_IPN_SECRET: str = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
    NOWPAYMENTS_WEBHOOK_URL: str = os.getenv(
        "NOWPAYMENTS_WEBHOOK_URL",
        "https://telegram-payment-bot-production-2c8f.up.railway.app/webhook/nowpayments"
    )
    
    # ========================================
    # LAVA.TOP SETTINGS (Card payments RU — Рубли)
    # ========================================
    LAVA_API_KEY: str = os.getenv("LAVA_API_KEY", "")
    LAVA_WEBHOOK_SECRET: str = os.getenv("LAVA_WEBHOOK_SECRET", "")

    try:
        LAVA_OFFER_MAP: dict = json.loads(os.getenv("LAVA_OFFER_MAP", "{}") or "{}")
    except json.JSONDecodeError:
        LAVA_OFFER_MAP: dict = {}
    LAVA_WEBHOOK_PATH: str = os.getenv("LAVA_WEBHOOK_PATH", "/webhook/lava")
    
    # ========================================
    # LAVA.TOP PRODUCT MAP (service_key → полный URL продукта на lava.top)
    # Редактируй lava_products.json в корне проекта —
    # заменяй "ВСТАВЬ_URL" на скопированный URL со страницы продукта lava.top
    # ========================================
    try:
        _lava_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lava_products.json")
        if os.path.exists(_lava_json_path):
            with open(_lava_json_path, "r", encoding="utf-8") as _f:
                _raw = json.load(_f)
            # Поддерживаем форматы:
            #   Новый:  "service_key": {"url": "...", "price_rub": 37050, "offer_id": "UUID"}
            #   Старый: "service_key": "https://..."
            LAVA_PRODUCT_MAP: dict = {}
            LAVA_PRICE_RUB_MAP: dict = {}
            LAVA_OFFER_ID_MAP: dict = {}  # UUID оффера для V3 API (создаёт инвойс с order_id)
            for k, v in _raw.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict):
                    url = v.get("url", "")
                    price_rub = v.get("price_rub", 0)
                    offer_id = v.get("offer_id", "")
                    if url and url != "ВСТАВЬ_URL":
                        LAVA_PRODUCT_MAP[k] = url
                        # Автоизвлечение offer_id из URL если явно не задан
                        # URL формат: https://app.lava.top/products/<product_id>/<offer_id>
                        if not offer_id or offer_id in ("", "ВСТАВЬ_OFFER_ID"):
                            offer_id = url.rstrip("/").split("/")[-1]
                    if price_rub:
                        LAVA_PRICE_RUB_MAP[k] = int(price_rub)
                    if offer_id and offer_id not in ("", "ВСТАВЬ_OFFER_ID"):
                        LAVA_OFFER_ID_MAP[k] = offer_id
                elif isinstance(v, str) and v and v != "ВСТАВЬ_URL":
                    LAVA_PRODUCT_MAP[k] = v
        else:
            # Fallback: .env переменная (для старых конфигураций)
            LAVA_PRODUCT_MAP: dict = json.loads(os.getenv("LAVA_PRODUCT_MAP", "{}") or "{}")
            LAVA_PRICE_RUB_MAP: dict = {}
            LAVA_OFFER_ID_MAP: dict = {}
    except Exception:
        LAVA_PRODUCT_MAP: dict = {}
        LAVA_PRICE_RUB_MAP: dict = {}
        LAVA_OFFER_ID_MAP: dict = {}

    # ========================================
    # LAVA.TOP CUSTOM PRICE TIERS ($10–$2500, шаг $10)
    # Редактируй lava_custom_tiers.json: вставляй offer_id по мере создания
    # продуктов на lava.top. price_rub=0 → конвертация по ЦБ*1.08 в WebApp.
    # ========================================
    try:
        _tiers_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lava_custom_tiers.json")
        if os.path.exists(_tiers_path):
            with open(_tiers_path, "r", encoding="utf-8") as _tf:
                _tiers_raw = json.load(_tf)
            LAVA_CUSTOM_TIERS: dict = {}  # {amount_usd: {"offer_id": str, "price_rub": int}}
            for _tier in _tiers_raw.get("tiers", []):
                _usd = int(_tier.get("amount_usd", 0))
                if _usd > 0:
                    LAVA_CUSTOM_TIERS[_usd] = {
                        "offer_id":  _tier.get("offer_id", ""),
                        "price_rub": int(_tier.get("price_rub", 0)),
                    }
        else:
            LAVA_CUSTOM_TIERS: dict = {}
    except Exception:
        LAVA_CUSTOM_TIERS: dict = {}

    
    # ========================================
    # TOP PRICES TABLE (USD)
    # Формат: TOP_PRICES[tier][position][period] = amount
    # tier: "tier1", "tier2", "tier3", "tier4", "world"
    # position: 1..10
    # period: "week" | "month"
    # ========================================
    TOP_PRICES: dict = {
        # Tier 1: TRADING, SIGNALS, ARBITRAGE
        "tier1": {
            1:  {"week": 1525, "month": 3975},
            2:  {"week": 1078, "month": 3058},
            3:  {"week": 980,  "month": 2780},
            4:  {"week": 882,  "month": 2502},
            5:  {"week": 784,  "month": 2224},
            6:  {"week": 686,  "month": 1946},
            7:  {"week": 637,  "month": 1807},
            8:  {"week": 588,  "month": 1668},
            9:  {"week": 539,  "month": 1529},
            10: {"week": 490,  "month": 1390},
        },
        # Tier 2: ANALYTICS_REVIEWS, DEFI_WEB3, ECOSYSTEMS, PROJECT_REVIEWS, INVESTMENTS
        "tier2": {
            1:  {"week": 1275, "month": 3125},
            2:  {"week": 858,  "month": 2398},
            3:  {"week": 780,  "month": 2180},
            4:  {"week": 702,  "month": 1962},
            5:  {"week": 624,  "month": 1744},
            6:  {"week": 546,  "month": 1526},
            7:  {"week": 507,  "month": 1417},
            8:  {"week": 468,  "month": 1308},
            9:  {"week": 429,  "month": 1199},
            10: {"week": 390,  "month": 1090},
        },
        # Tier 3: CRYPTO_NEWS, EDUCATION, ANALYTICAL_POSTS, GUIDES_EDUCATION
        "tier3": {
            1:  {"week": 800,  "month": 2225},
            2:  {"week": 704,  "month": 1958},
            3:  {"week": 640,  "month": 1780},
            4:  {"week": 576,  "month": 1602},
            5:  {"week": 512,  "month": 1424},
            6:  {"week": 448,  "month": 1246},
            7:  {"week": 416,  "month": 1157},
            8:  {"week": 384,  "month": 1068},
            9:  {"week": 352,  "month": 979},
            10: {"week": 320,  "month": 890},
        },
        # Tier 4: NFT_GAMEFI, AIRDROPS, OPINIONS_BLOG
        "tier4": {
            1:  {"week": 625,  "month": 1725},
            2:  {"week": 550,  "month": 1518},
            3:  {"week": 500,  "month": 1380},
            4:  {"week": 450,  "month": 1242},
            5:  {"week": 400,  "month": 1104},
            6:  {"week": 350,  "month": 966},
            7:  {"week": 325,  "month": 897},
            8:  {"week": 300,  "month": 828},
            9:  {"week": 275,  "month": 759},
            10: {"week": 250,  "month": 690},
        },
        # World TOP
        "world": {
            1:  {"week": 1990, "month": 5900},
            2:  {"week": 1690, "month": 4990},
            3:  {"week": 1490, "month": 4490},
            4:  {"week": 1290, "month": 3990},
            5:  {"week": 1090, "month": 3490},
            6:  {"week": 990,  "month": 2990},
            7:  {"week": 890,  "month": 2690},
            8:  {"week": 790,  "month": 2390},
            9:  {"week": 690,  "month": 2090},
            10: {"week": 590,  "month": 1790},
        },
    }
    
    # ========================================
    # WAYPAY SETTINGS (Card payments International — USD)
    # ========================================
    WAYPAY_MERCHANT_LOGIN: str = os.getenv("WAYPAY_MERCHANT_LOGIN", "")
    WAYPAY_MERCHANT_SECRET: str = os.getenv("WAYPAY_MERCHANT_SECRET", "")
    WAYPAY_WEBHOOK_PATH: str = os.getenv("WAYPAY_WEBHOOK_PATH", "/webhook/waypay")
    WAYPAY_TEST_MODE: bool = os.getenv("WAYPAY_TEST_MODE", "false").lower() == "true"
    
    # ========================================
    # CURRENCY CONVERSION
    # ========================================
    USD_TO_RUB_RATE: float = float(os.getenv("USD_TO_RUB_RATE", "95.0"))
    
    # ========================================
    # WEBHOOK SETTINGS (для продакшн)
    # ========================================
    # В Railway публичный домен доступен через RAILWAY_PUBLIC_DOMAIN
    RAILWAY_PUBLIC_DOMAIN: str = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    
    # Автоматическое определение URL вебхука
    @property
    def BASE_WEBHOOK_URL(self) -> str:
        if self.WEBHOOK_URL:
            return self.WEBHOOK_URL
        if self.RAILWAY_PUBLIC_DOMAIN:
            return f"https://{self.RAILWAY_PUBLIC_DOMAIN}"
        return ""

    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook/telegram")
    
    CRYPTOMUS_WEBHOOK_PATH: str = os.getenv(
        "CRYPTOMUS_WEBHOOK_PATH", 
        "/webhook/cryptomus"
    )
    NOWPAYMENTS_WEBHOOK_PATH: str = os.getenv(
        "NOWPAYMENTS_WEBHOOK_PATH",
        "/webhook/nowpayments"
    )
    
    WEB_SERVER_HOST: str = os.getenv("WEB_SERVER_HOST", "0.0.0.0")
    WEB_SERVER_PORT: int = int(os.getenv("PORT", "8080"))  # Railway использует PORT
    
    # ========================================
    # LOGGING SETTINGS
    # ========================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "bot.log")
    
    # ========================================
    # RATE LIMITING
    # ========================================
    RATE_LIMIT_MESSAGES: int = int(os.getenv("RATE_LIMIT_MESSAGES", "5"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    # ========================================
    # TERMS & POLICIES
    # ========================================
    TERMS_OF_SERVICE_URL: str = os.getenv(
        "TERMS_OF_SERVICE_URL",
        "https://telegra.ph/Usloviya-obsluzhivaniya-i-Politika-vozvrata--MarketFilter-02-08"
    )
    REFUND_POLICY_URL: str = os.getenv(
        "REFUND_POLICY_URL",
        "https://telegra.ph/POLITIKA-VOZVRATA--Servis-MarketFilter-02-09"
    )
    # URL договора оферты (отображается в кнопке инвойса)
    OFERTA_URL: str = os.getenv(
        "OFERTA_URL",
        "https://telegra.ph/Usloviya-obsluzhivaniya-i-Politika-vozvrata--MarketFilter-02-08"
    )
    SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "MarketFilterSupport")
    
    @classmethod
    def validate(cls) -> None:
        """Валидация обязательных настроек"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        
        if not cls.ADMIN_IDS:
            errors.append("ADMIN_IDS is required")
        
        if errors:
            raise ValueError(
                f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )
    
    @classmethod
    def is_webhook_mode(cls) -> bool:
        """Проверка, используется ли режим webhook
        
        Автоматически включается если задан WEBHOOK_URL или RAILWAY_PUBLIC_DOMAIN
        """
        return bool(cls.WEBHOOK_URL or cls.RAILWAY_PUBLIC_DOMAIN)


# Валидация конфигурации при импорте
Config.validate()
