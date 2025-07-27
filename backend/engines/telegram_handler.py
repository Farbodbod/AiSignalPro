# engines/telegram_handler.py
import os
import requests
import logging

logger = logging.getLogger(__name__)

class TelegramHandler:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.token or not self.chat_id:
            logger.error("Telegram Token or Chat ID not found in environment variables.")
            raise ValueError("Telegram credentials are not set.")
        self.base_url = f"https://api.telegram.org/bot{self.token}/"

    def send_message(self, message_text: str):
        """یک پیام متنی ساده به تلگرام ارسال می‌کند."""
        url = self.base_url + "sendMessage"
        params = {
            'chat_id': self.chat_id,
            'text': message_text,
            'parse_mode': 'Markdown'
        }
        try:
            response = requests.post(url, json=params)
            response.raise_for_status()
            logger.info("Telegram message sent successfully.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")

