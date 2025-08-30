# engines/gemini_handler.py (v3.0 - Hardened & Synchronous)

import os
import google.generativeai as genai
import logging
import random
import json
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class GeminiHandler:
    """
    Gemini Handler - (v3.0 - Hardened & Synchronous)
    ---------------------------------------------------------------------------
    This version is fully synchronous to align with the official library.
    It introduces hardened response parsing to safely extract confidence scores
    without inventing default values, ensures output key consistency across
    the system ('confidence_percent'), and uses the latest stable model names.
    """
    def __init__(self):
        keys_str = os.getenv('GEMINI_API_KEYS')
        if not keys_str:
            self.api_keys: List[str] = []
            logger.warning("GEMINI_API_KEYS environment variable not found. GeminiHandler is disabled.")
            return

        self.api_keys = [key.strip() for key in keys_str.split(',')]
        random.shuffle(self.api_keys)
        self.current_key_index = 0
        # FIX 1: Using the correct, latest model name
        self.model_names = ['gemini-2.0-flash'] 
        
        if self.api_keys:
            logger.info(f"GeminiHandler initialized successfully with {len(self.api_keys)} API keys and model '{self.model_names[0]}'.")

    def _get_next_key(self) -> Optional[str]:
        if not self.api_keys: return None
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        logger.debug(f"Using Gemini API key index: {self.current_key_index}")
        return key

    def query(self, prompt: str) -> Dict[str, Any]:
        """Sends a prompt to Gemini and processes the JSON response synchronously."""
        api_key = self._get_next_key()
        if not api_key:
            return {"signal": "HOLD", "confidence_percent": 0, "explanation_fa": "هیچ کلید API معتبری برای Gemini پیکربندی نشده است."}

        last_exception = None
        for model_name in self.model_names:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0
                    )
                )
                
                # Clean and parse the response text
                cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
                if not cleaned_response.startswith("{") or not cleaned_response.endswith("}"):
                    # Attempt to find JSON within the string if it's embedded
                    start = cleaned_response.find('{')
                    end = cleaned_response.rfind('}')
                    if start != -1 and end != -1:
                        cleaned_response = cleaned_response[start:end+1]
                    else:
                        raise ValueError(f"Could not find valid JSON object in response: {response.text}")

                json_response = json.loads(cleaned_response)
                
                # --- SURGICAL FIX in data extraction ---
                signal = json_response.get("signal", "HOLD").upper()

                # FIX 3: Robustly get confidence without inventing data
                confidence_val = json_response.get("confidence_percent")
                if confidence_val is None:
                    confidence_val = json_response.get("confidence") # Fallback key
                
                # Default to 0 if neither key is found
                confidence = int(confidence_val or 0)

                explanation = json_response.get("explanation_fa", "توضیحات توسط AI ارائه نشد.")
                
                # FIX 2: Use the consistent key "confidence_percent" in the output
                return {"signal": signal, "confidence_percent": confidence, "explanation_fa": explanation}
            
            except Exception as e:
                last_exception = e
                logger.warning(f"Failed to use Gemini model '{model_name}'. Trying next model. Error: {e}")
                time.sleep(1)
        
        logger.error(f"All Gemini models failed. Last error: {last_exception}")
        return {"signal": "HOLD", "confidence_percent": 0, "explanation_fa": f"خطا در پردازش پاسخ AI: {last_exception}"}

