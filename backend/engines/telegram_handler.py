# engines/telegram_handler.py (نسخه async)

import os
import httpx
import logging

class TelegramHandler:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.token or not self.chat_id:
            logging.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in environment.")
            self.is_configured = False
        else:
            self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            self.is_configured = True
            logging.info("TelegramHandler initialized successfully.")

    async def send_message_async(self, message: str):
        """(جدید) پیام را به صورت غیرهمزمان (async) به تلگرام ارسال می‌کند."""
        if not self.is_configured:
            logging.warning("Telegram is not configured. Skipping message sending.")
            return

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload, timeout=10)
                response.raise_for_status()
                logging.info("Telegram message sent successfully.")
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to send Telegram message. Status: {e.response.status_code}, Response: {e.response.text}")
        except httpx.RequestError as e:
            logging.error(f"An error occurred while sending Telegram message: {e}")

