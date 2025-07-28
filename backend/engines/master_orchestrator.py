import os
import google.generativeai as genai
import logging
import pandas as pd
from typing import Dict, Any
import json

from engines.candlestick_reader import CandlestickPatternDetector
from engines.indicator_analyzer import calculate_indicators
from engines.trend_analyzer import analyze_trend
from engines.whale_analyzer import WhaleAnalyzer
from engines.divergence_detector import detect_divergences
from engines.market_structure_analyzer import LegPivotAnalyzer
from engines.ai_predictor import AIEngineProAdvanced

logger = logging.getLogger(__name__)

TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2, '1h': 1.5, '15m': 1, '5m': 0.5}
# --- حد آستانه برای تماس با هوش مصنوعی ---
SCORE_THRESHOLD = 4.0

class MasterOrchestrator:
    def __init__(self):
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        else:
            self.gemini_model = None
            logger.warning("Gemini API key not found.")
        
        self.local_ai_engine = AIEngineProAdvanced()

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        """تمام تحلیل‌ها را روی یک دیتافریم اجرا می‌کند."""
        if 'timestamp' in df.columns:
            if df['timestamp'].iloc[0] > 10**12:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='s')

        df_with_indicators = calculate_indicators(df.copy())
        latest_indicator_values = {}
        for col in df_with_indicators.columns:
            if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'timestamp_dt']:
                if not df_with_indicators[col].dropna().empty:
                    last_valid_value = df_with_indicators[col].dropna().iloc[-1]
                    latest_indicator_values[col] = last_valid_value
        
        if not df.empty and 'close' in df.columns:
            latest_indicator_values['close'] = df['close'].iloc[-1]

        trend_res = analyze_trend(df.copy(), timeframe=timeframe)
        whale_analyzer_instance = WhaleAnalyzer(timeframes=[timeframe])
        df_for_whale = df.copy()
        if 'timestamp_dt' in df_for_whale.columns:
            df_for_whale = df_for_whale.set_index('timestamp_dt')
        whale_analyzer_instance.update_data(timeframe, df_for_whale)
        whale_res = {"signals": whale_analyzer_instance.get_signals(timeframe)}
        
        df_reset = df.copy().reset_index()
        divergence_res = detect_divergences(df_reset)
        candlestick_res = {"patterns": CandlestickPatternDetector(df_reset).apply_filters()}
        market_structure_res = LegPivotAnalyzer(df.copy()).analyze()
        self.local_ai_engine.load_data(df.copy())
        self.local_ai_engine.feature_engineering()
        local_ai_res = self.local_ai_engine.generate_advanced_report()

        return {"trend": trend_res, "whales": whale_res, "divergence": divergence_res, "indicators": latest_indicator_values, "candlesticks": candlestick_res, "market_structure": market_structure_res, "local_ai": local_ai_res}

    def _generate_composite_prompt(self, all_tf_analysis: Dict[str, Any], scores: Dict[str, float]) -> str:
        prompt = f"""
        Analyze the following multi-timeframe market data and provide a final trading signal (BUY, SELL, or HOLD) and a confidence score (0-100). 
        The rule-based system score is BUY: {scores['buy_score']:.2f} and SELL: {scores['sell_score']:.2f}.
        Use this score as a primary factor, but also use your own intelligence based on the detailed data.
        Respond ONLY with a valid JSON object like this: {{"signal": "...", "confidence": ...}}
        --- Data Summary ---
        """
        for tf, data in all_tf_analysis.items():
            prompt += f"\n--- Timeframe: {tf} ---\n"
            prompt += f"- Trend: {data.get('trend', {}).get('signal')}\n"
            prompt += f"- Market Phase: {data.get('market_structure', {}).get('market_phase')}\n"
            prompt += f"- Local AI Signal: {data.get('local_ai', {}).get('signal')}\n"
            prompt += f"- Whale Signals Detected: {len(data.get('whales', {}).get('signals', []))}\n"
            prompt += f"- Bullish Divergences: {len([d for d in data.get('divergence', {}).get('rsi', []) if 'bullish' in d.get('type', '')])}\n"
            prompt += f"- Bearish Divergences: {len([d for d in data.get('divergence', {}).get('rsi', []) if 'bearish' in d.get('type', '')])}\n"
        return prompt
        
    def _query_gemini(self, prompt: str) -> Dict[str, Any]:
        if not self.gemini_model:
            return {"signal": "N/A", "confidence": 0}
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Gemini query or JSON parsing failed: {e}")
            return {"signal": "Error", "confidence": 0}

    def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score = 0
        sell_score = 0

        for tf, data in all_tf_analysis.items():
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            if "Uptrend" in data.get('trend', {}).get('signal', ''): buy_score += 1 * weight
            elif "Downtrend" in data.get('trend', {}).get('signal', ''): sell_score += 1 * weight
            if data.get('market_structure', {}).get('market_phase') == 'strong_trend': buy_score += 1 * weight
            if len([d for d in data.get('divergence', {}).get('rsi', []) if 'bullish' in d.get('type', '')]) > 0: buy_score += 1.5 * weight
            if len([d for d in data.get('divergence', {}).get('rsi', []) if 'bearish' in d.get('type', '')]) > 0: sell_score += 1.5 * weight
            if data.get('local_ai', {}).get('signal') == 'Buy': buy_score += 1 * weight
            elif data.get('local_ai', {}).get('signal') == 'Sell': sell_score += 1 * weight

        # --- منطق نگهبان ---
        gemini_confirmation = {"signal": "N/A", "confidence": 0}
        if buy_score > SCORE_THRESHOLD or sell_score > SCORE_THRESHOLD:
            logging.info(f"Score threshold met (Buy: {buy_score:.2f}, Sell: {sell_score:.2f}). Querying Gemini.")
            scores = {"buy_score": buy_score, "sell_score": sell_score}
            prompt = self._generate_composite_prompt(all_tf_analysis, scores)
            gemini_confirmation = self._query_gemini(prompt)
        else:
            logging.info(f"Score threshold NOT met (Buy: {buy_score:.2f}, Sell: {sell_score:.2f}). Skipping Gemini call.")

        # --- تعیین سیگنال نهایی بر اساس امتیازات ---
        final_signal = "HOLD"
        if buy_score > sell_score and buy_score > SCORE_THRESHOLD:
            final_signal = "BUY"
        elif sell_score > buy_score and sell_score > SCORE_THRESHOLD:
            final_signal = "SELL"

        return {"rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}
