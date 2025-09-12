# engines/telegram_handler.py (v2.0 - The Bulletproof Edition)

import os
import httpx
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    Handles all Telegram notifications with a robust, fault-resilient mechanism.
    v2.0 (The Bulletproof Edition):
    - Implements an intelligent retry logic to handle transient network errors.
    - Uses a persistent httpx.AsyncClient instance for improved performance.
    - Features a generous and configurable timeout.
    """
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Notifications disabled.")
            self.is_configured = False
            self.client = None
        else:
            self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            # ✅ UPGRADE: Define a generous timeout
            timeout = httpx.Timeout(10.0, read=20.0, connect=5.0)
            # ✅ UPGRADE: Create a single, persistent client for efficiency
            self.client = httpx.AsyncClient(timeout=timeout)
            self.is_configured = True
            logger.info("TelegramHandler initialized successfully.")

    async def send_message_async(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """Sends a message to Telegram asynchronously with retry logic."""
        if not self.is_configured or not self.client:
            logger.warning("Telegram is not configured. Skipping message sending.")
            return False

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        # ✅ UPGRADE: Intelligent Retry Logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.post(self.api_url, json=payload)
                response.raise_for_status()
                logger.info(f"Message sent to Telegram successfully on attempt {attempt + 1}.")
                return True
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.NetworkError) as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} to send Telegram message failed due to network error: {e}")
                if attempt + 1 < max_retries:
                    await asyncio.sleep(2 * (attempt + 1)) # Wait longer on each retry (2s, 4s)
                else:
                    logger.error("All attempts to send Telegram message failed. Giving up.", exc_info=True)
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to send message. HTTP Status: {e.response.status_code}, Response: {e.response.text}")
                return False # Don't retry on HTTP errors like 400 Bad Request
            except Exception as e:
                logger.error(f"An unexpected error occurred while sending Telegram message: {e}", exc_info=True)
                return False # Don't retry on unknown errors
        
        return False

    async def close(self):
        """Closes the httpx client gracefully."""
        if self.client:
            await self.client.aclose()
            logger.info("TelegramHandler client closed.")

