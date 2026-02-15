"""
Конфигурация бота и загрузка переменных окружения
"""
import os
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
    LAVA_SECRET_KEY: str = os.getenv("LAVA_SECRET_KEY", "")
    LAVA_PROJECT_ID: str = os.getenv("LAVA_PROJECT_ID", "")
    LAVA_WEBHOOK_PATH: str = os.getenv("LAVA_WEBHOOK_PATH", "/webhook/lava")
    
    # ========================================
    # WAYPAY SETTINGS (Card payments International — USD)
    # ========================================
    WAYPAY_MERCHANT_LOGIN: str = os.getenv("WAYPAY_MERCHANT_LOGIN", "")
    WAYPAY_MERCHANT_SECRET: str = os.getenv("WAYPAY_MERCHANT_SECRET", "")
    WAYPAY_WEBHOOK_PATH: str = os.getenv("WAYPAY_WEBHOOK_PATH", "/webhook/waypay")
    
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
