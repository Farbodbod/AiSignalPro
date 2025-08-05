# engines/gemini_handler.py (نسخه نهایی 2.1 - یکپارچه و کامل)

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
        
        # --- ✨ اصلاح: استفاده از نام رسمی و جدیدترین مدل برای پایداری بیشتر ---
        self.model_names = ['gemini-2.0-flash'] 
        
        if self.api_keys:
            logger.info(f"GeminiHandler initialized successfully with {len(self.api_keys)} API keys and model '{self.model_names[0]}'.")

    def _get_next_key(self) -> Optional[str]:
        """ کلید API بعدی را برای توزیع بار انتخاب می‌کند. """
        if not self.api_keys: return None
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.info(f"Using Gemini API key index: {self.current_key_index}")
        return key

    async def query(self, prompt: str) -> Dict[str, Any]:
        """ یک پرامپت را به Gemini ارسال کرده و پاسخ JSON را پردازش می‌کند. """
        api_key = self._get_next_key()
        if not api_key:
            return {"signal": "N/A", "confidence": 0, "explanation_fa": "هیچ کلید API معتبری پیکربندی نشده است."}

        last_exception = None
        # تلاش برای استفاده از مدل‌ها به ترتیب اولویت
        for model_name in self.model_names:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(model.generate_content, prompt)
                
                cleaned_response = response.text.replace("`", "").replace("json", "").strip()
                if not cleaned_response.startswith("{") or not cleaned_response.endswith("}"):
                    raise ValueError(f"Invalid Gemini response format: {cleaned_response}")
                
                json_response = json.loads(cleaned_response)
                signal = json_response.get("signal", "HOLD").upper()
                
                # --- ✨ اصلاح کلیدی: خواندن درصد اطمینان پویا از پاسخ AI ---
                # اگر AI درصد اطمینان را نفرستاد، یک مقدار پیش‌فرض منطقی در نظر می‌گیریم.
                confidence = int(json_response.get("confidence_percent", 75 if signal != "HOLD" else 50))
                
                explanation = json_response.get("explanation_fa", "توضیحات توسط AI ارائه نشد.")
                
                return {"signal": signal, "confidence": confidence, "explanation_fa": explanation}
            
            except Exception as e:
                last_exception = e
                logger.warning(f"Failed to use Gemini model '{model_name}'. Trying next model. Error: {e}")
                await asyncio.sleep(1) # تاخیر کوتاه قبل از تلاش مجدد با مدل بعدی
        
        logger.error(f"All Gemini models failed. Last error: {last_exception}")
        return {"signal": "Error", "confidence": 0, "explanation_fa": "خطا در پردازش پاسخ AI."}

