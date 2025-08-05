# engines/telegram_handler.py

import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.bot_token or not self.chat_id:
            logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables not set. Telegram notifications are disabled.")
            self.is_configured = False
        else:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            self.is_configured = True
            logger.info("TelegramHandler initialized successfully.")

    async def send_message_async(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """یک پیام را به صورت غیرهمزمان به تلگرام ارسال می‌کند."""
        if not self.is_configured:
            logger.warning("Telegram is not configured. Skipping message sending.")
            return False

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status() # برای خطاهای HTTP استثنا ایجاد می‌کند
                logger.info(f"Message sent to Telegram successfully. Response: {response.json()}")
                return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message to Telegram. HTTP Status: {e.response.status_code}, Response: {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending Telegram message: {e}", exc_info=True)
        
        return False
