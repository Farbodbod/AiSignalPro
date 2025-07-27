import os
import google.generativeai as genai
import logging
import pandas as pd
from typing import Dict, Any
import json

# وارد کردن تمام موتورهای تحلیلی
from engines.candlestick_reader import CandlestickPatternDetector
from engines.indicator_analyzer import calculate_indicators
from engines.trend_analyzer import analyze_trend
from engines.whale_analyzer import WhaleAnalyzer
from engines.divergence_detector import detect_divergences
from engines.market_structure_analyzer import LegPivotAnalyzer
from engines.ai_predictor import AIEngineProAdvanced
from engines.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)

TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2, '1h': 1.5, '15m': 1, '5m': 0.5}

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
        """تمام تحلیل‌ها و استراتژی‌ها را روی یک دیتافریم اجرا می‌کند."""
        
        if 'timestamp' in df.columns:
            if df['timestamp'].iloc[0] > 10**12:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='s')

        # اجرای تمام موتورهای تحلیلی پایه
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

        # جمع‌آوری نتایج خام
        raw_analysis = {
            "trend": trend_res, "whales": whale_res, "divergence": divergence_res,
            "indicators": latest_indicator_values, "candlesticks": candlestick_res,
            "market_structure": market_structure_res,
            "local_ai": local_ai_res
        }
        
        # اجرای موتور استراتژی
        strategy_engine = StrategyEngine(raw_analysis)
        signal_type = "BUY" if "Uptrend" in trend_res.get('signal', '') else ("SELL" if "Downtrend" in trend_res.get('signal', '') else "HOLD")
        strategy_res = strategy_engine.generate_strategy(signal_type)
        
        raw_analysis["strategy"] = strategy_res
        
        return raw_analysis

    def _generate_composite_prompt(self, all_tf_analysis: Dict[str, Any], scores: Dict[str, float]) -> str:
        """یک پرامپت جامع و کامل‌تر برای Gemini می‌سازد."""
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
        """پرس و جو از مدل Gemini و بازگرداندن پاسخ در فرمت دیکشنری."""
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
        """سیگنال نهایی را بر اساس تحلیل جامع مولتی-تایم‌فریم تولید می‌کند."""
        buy_score = 0
        sell_score = 0

        for tf, data in all_tf_analysis.items():
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            
            if "Uptrend" in data.get('trend', {}).get('signal', ''):
                buy_score += 1 * weight
            elif "Downtrend" in data.get('trend', {}).get('signal', ''):
                sell_score += 1 * weight

            if data.get('market_structure', {}).get('market_phase') == 'strong_trend':
                buy_score += 1 * weight

            if len([d for d in data.get('divergence', {}).get('rsi', []) if 'bullish' in d.get('type', '')]) > 0:
                buy_score += 1.5 * weight
            if len([d for d in data.get('divergence', {}).get('rsi', []) if 'bearish' in d.get('type', '')]) > 0:
                sell_score += 1.5 * weight
            
            if data.get('local_ai', {}).get('signal') == 'Buy':
                buy_score += 1 * weight
            elif data.get('local_ai', {}).get('signal') == 'Sell':
                sell_score += 1 * weight

        if buy_score > sell_score * 1.5:
            final_signal = "BUY"
        elif sell_score > buy_score * 1.5:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        scores = {"buy_score": buy_score, "sell_score": sell_score}
        prompt = self._generate_composite_prompt(all_tf_analysis, scores)
        gemini_confirmation = self._query_gemini(prompt)

        return {
            "rule_based_signal": final_signal,
            "buy_score": round(buy_score, 2),
            "sell_score": round(sell_score, 2),
            "gemini_confirmation": gemini_confirmation,
            "details": all_tf_analysis
        }
