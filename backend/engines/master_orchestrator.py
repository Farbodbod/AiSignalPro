import os
import google.generativeai as genai
import logging
from .ai_predictor import AIEngineProAdvanced

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self):
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        else:
            self.gemini_model = None
            logger.warning("Gemini API key not found.")
            
        # ساخت یک نمونه از موتور یادگیرنده خودمان
        self.local_ai_engine = AIEngineProAdvanced()

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

    def _query_gemini(self, prompt: str) -> str:
        if not self.gemini_model:
            return "Not Available"
        try:
            response = self.gemini_model.generate_content(prompt)
            # تمیز کردن خروجی برای گرفتن فقط یک کلمه
            cleaned_response = response.text.strip().upper().split()[0]
            if cleaned_response in ["BUY", "SELL", "HOLD"]:
                return cleaned_response
            return "HOLD" # اگر پاسخ نامفهوم بود
        except Exception as e:
            logger.error(f"Gemini query failed: {e}")
            return "Error"
            
    def get_consensus_signal(self, df, analysis_data: dict) -> dict:
        prompt = self._generate_prompt(analysis_data)
        
        # ۱. دریافت سیگنال از Gemini
        gemini_signal = self._query_gemini(prompt)

        # ۲. دریافت سیگنال از موتور یادگیرنده خودمان
        self.local_ai_engine.load_data(df)
        self.local_ai_engine.feature_engineering()
        local_ai_report = self.local_ai_engine.generate_advanced_report()

        # منطق رأی‌گیری نهایی
        final_signal = "HOLD"
        local_signal = local_ai_report.get('signal')
        votes = [s for s in [gemini_signal, local_signal] if s in ["BUY", "SELL", "HOLD"]]
        
        if len(votes) == 2 and votes[0] == votes[1]: # اگر هر دو موافق بودند
            final_signal = votes[0]
        elif "BUY" in votes and "SELL" not in votes: # اگر حداقل یک خرید داشتیم و هیچ فروشی نبود
            final_signal = "BUY"
        elif "SELL" in votes and "BUY" not in votes: # اگر حداقل یک فروش داشتیم و هیچ خریدی نبود
            final_signal = "SELL"
        # در غیر این صورت (مثلا یکی خرید و یکی فروش) سیگنال HOLD باقی می‌ماند
            
        return {
            "final_signal": final_signal,
            "gemini_vote": gemini_signal,
            "local_ai_vote": local_ai_report,
            "data_summary": analysis_data
        }
