# engines/gemini_handler.py (مدیر هوشمند استخر کلید Gemini)

import os
import google.generativeai as genai
import logging
import random
import asyncio
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class GeminiHandler:
    def __init__(self):
        keys_str = os.getenv('GEMINI_API_KEYS')
        if not keys_str:
            self.api_keys: List[str] = []
            self.models: List[Any] = []
            logger.warning("GEMINI_API_KEYS environment variable not found. GeminiHandler is disabled.")
            return

        self.api_keys = [key.strip() for key in keys_str.split(',')]
        random.shuffle(self.api_keys) # برای تقسیم بار بهتر، لیست را در ابتدا بهم می‌ریزیم
        self.models = self._configure_models()
        self.current_key_index = 0
        if self.models:
            logger.info(f"GeminiHandler initialized successfully with {len(self.models)} API keys.")

    def _configure_models(self) -> List[Any]:
        configured_models = []
        for key in self.api_keys:
            try:
                # هر مدل باید با کلید مخصوص به خود کانفیگ شود
                # این بخش نیاز به بازبینی در کتابخانه genai دارد، اما ایده کلی صحیح است
                # در حال حاضر، genai.configure گلوبال است، پس ما یک مدل برای هر کلید نمی‌سازیم
                # بلکه در زمان استفاده، کلید را تغییر می‌دهیم (راه حل جایگزین در متد query)
                pass # فعلا از این بخش عبور می‌کنیم
            except Exception as e:
                logger.error(f"Failed to configure Gemini model for one of the keys: {e}")
        # از آنجایی که genai.configure گلوبال است، فقط یک مدل می‌سازیم و با کلیدهای مختلف استفاده می‌کنیم
        if self.api_keys:
            try:
                genai.configure(api_key=self.api_keys[0])
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                configured_models.append(model)
            except Exception as e:
                 logger.error(f"Failed to configure the initial Gemini model: {e}")
        return configured_models


    def _get_next_key(self) -> Optional[str]:
        """یک کلید API را به صورت چرخشی از استخر انتخاب می‌کند."""
        if not self.api_keys:
            return None
        
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Using Gemini API key index: {self.current_key_index}")
        return key

    async def query(self, prompt: str) -> Dict[str, Any]:
        """یک درخواست را با استفاده از کلید بعدی در استخر، به Gemini ارسال می‌کند."""
        api_key = self._get_next_key()
        if not api_key:
            return {"signal": "N/A", "confidence": 0, "explanation_fa": "هیچ کلید API معتبری برای Gemini پیکربندی نشده است."}

        try:
            # استفاده از مدل جنرال با کلید مشخص
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = await asyncio.to_thread(model.generate_content, prompt, client_options={"api_key": api_key})
            
            cleaned_response = response.text.replace("`", "").replace("json", "").strip()
            if not cleaned_response.startswith("{") or not cleaned_response.endswith("}"):
                raise ValueError(f"Invalid Gemini response format: {cleaned_response}")
            
            json_response = json.loads(cleaned_response)
            signal = json_response.get("signal", "HOLD").upper()
            return {
                "signal": signal,
                "confidence": 85 if signal != "HOLD" else 50,
                "explanation_fa": json_response.get("explanation_fa", "توضیحات توسط AI ارائه نشد.")
            }
        except Exception as e:
            logger.error(f"Gemini API call or JSON parsing failed with key index {self.current_key_index}: {e}")
            return {"signal": "Error", "confidence": 0, "explanation_fa": "خطا در پردازش پاسخ AI."}

