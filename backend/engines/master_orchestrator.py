# engines/master_orchestrator.py

import os
import openai
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self):
        # خواندن کلیدهای API از متغیرهای محیطی
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        
        if self.openai_key:
            self.openai_client = openai.OpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None
            logger.warning("OpenAI API key not found.")

        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.0-pro')
        else:
            self.gemini_model = None
            logger.warning("Gemini API key not found.")

    def _generate_prompt(self, analysis_data: dict) -> str:
        # ساخت یک خلاصه متنی از تمام تحلیل‌ها
        prompt = f"""
        Analyze the following market data for {analysis_data.get('symbol')} at the {analysis_data.get('interval')} timeframe and provide a final trading signal (BUY, SELL, or HOLD). 
        Base your decision ONLY on the data provided. Be decisive. Your final answer must be just one word.

        Data Summary:
        - Data Source: {analysis_data.get('source')}
        - Trend Analysis Signal: {analysis_data.get('trend', {}).get('signal')}
        - Trend ADX: {analysis_data.get('trend', {}).get('adx')}
        - Whale Signals Detected: {len(analysis_data.get('whales', {}).get('signals', []))}
        - Divergences Detected: {analysis_data.get('divergence', {}).get('divergences')}
        - Key Indicators: {analysis_data.get('indicators')}
        - Candlestick Patterns: {analysis_data.get('candlesticks', {}).get('patterns')}
        
        Final Signal (BUY, SELL, or HOLD):
        """
        return prompt

    def _query_openai(self, prompt: str) -> str:
        if not self.openai_client:
            return "Error"
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=5
            )
            return response.choices[0].message.content.strip().upper()
        except Exception as e:
            logger.error(f"OpenAI query failed: {e}")
            return "Error"

    def _query_gemini(self, prompt: str) -> str:
        if not self.gemini_model:
            return "Error"
        try:
            response = self.gemini_model.generate_content(prompt)
            return response.text.strip().upper()
        except Exception as e:
            logger.error(f"Gemini query failed: {e}")
            return "Error"
            
    def get_consensus_signal(self, analysis_data: dict) -> dict:
        prompt = self._generate_prompt(analysis_data)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_openai = executor.submit(self._query_openai, prompt)
            future_gemini = executor.submit(self._query_gemini, prompt)
            
            openai_signal = future_openai.result()
            gemini_signal = future_gemini.result()

        # منطق رأی‌گیری
        final_signal = "HOLD"
        votes = [s for s in [openai_signal, gemini_signal] if s in ["BUY", "SELL", "HOLD"]]
        
        if len(votes) == 2 and votes[0] == votes[1]:
            final_signal = votes[0] # توافق کامل
        elif "BUY" in votes and "SELL" not in votes:
            final_signal = "BUY"
        elif "SELL" in votes and "BUY" not in votes:
            final_signal = "SELL"
            
        return {
            "final_signal": final_signal,
            "openai_vote": openai_signal,
            "gemini_vote": gemini_signal,
            "data_summary": analysis_data
        }

