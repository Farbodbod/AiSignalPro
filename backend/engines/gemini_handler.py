# engines/gemini_handler.py (نسخه نهایی با مدل صحیح)

import os, google.generativeai as genai, logging, random, asyncio, json
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class GeminiHandler:
    def __init__(self):
        keys_str = os.getenv('GEMINI_API_KEYS')
        if not keys_str:
            self.api_keys: List[str] = []
            logger.warning("GEMINI_API_KEYS environment variable not found. GeminiHandler is disabled.")
            return

        self.api_keys = [key.strip() for key in keys_str.split(',')]
        random.shuffle(self.api_keys)
        self.current_key_index = 0
        
        # --- ✨ اصلاح نهایی: استفاده از نام مدلی که شما پیدا کردید ---
        self.model_names = ['gemini-2.0-flash'] 
        
        if self.api_keys:
            logger.info(f"GeminiHandler initialized successfully with {len(self.api_keys)} API keys.")

    def _get_next_key(self) -> Optional[str]:
        if not self.api_keys: return None
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Using Gemini API key index: {self.current_key_index}")
        return key

    async def query(self, prompt: str) -> Dict[str, Any]:
        api_key = self._get_next_key()
        if not api_key:
            return {"signal": "N/A", "explanation_fa": "هیچ کلید API معتبری پیکربندی نشده است."}

        last_exception = None
        for model_name in self.model_names:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(model.generate_content, prompt)
                cleaned_response = response.text.replace("`", "").replace("json", "").strip()
                if not cleaned_response.startswith("{") or not cleaned_response.endswith("}"):
                    raise ValueError(f"Invalid Gemini response format")
                
                json_response = json.loads(cleaned_response)
                signal = json_response.get("signal", "HOLD").upper()
                return {"signal": signal, "confidence": 85 if signal != "HOLD" else 50, "explanation_fa": json_response.get("explanation_fa", "توضیحات توسط AI ارائه نشد.")}
            except Exception as e:
                last_exception = e
                logger.warning(f"Failed to use Gemini model '{model_name}'. Error: {e}")
        
        logger.error(f"All Gemini models failed. Last error: {last_exception}")
        return {"signal": "Error", "explanation_fa": "خطا در پردازش پاسخ AI."}
