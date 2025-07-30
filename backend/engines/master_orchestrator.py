# engines/master_orchestrator.py (نسخه افسانه‌ای با تمام موتورها و تحلیل فارسی)

import os
import google.generativeai as genai
import logging
import pandas as pd
from typing import Dict, Any
import time
import asyncio
import json

# --- وارد کردن تمام موتورهای تحلیلی شما ---
from .indicator_analyzer import calculate_indicators
from .trend_analyzer import analyze_trend
from .market_structure_analyzer import LegPivotAnalyzer
from .strategy_engine import StrategyEngine
from .candlestick_reader import CandlestickPatternDetector
from .divergence_detector import DivergenceDetector
from .whale_analyzer import WhaleAnalyzer

logger = logging.getLogger(__name__)

TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2.5, '1h': 2, '15m': 1, '5m': 0.5}
SCORE_THRESHOLD = 5.0

class MasterOrchestrator:
    def __init__(self):
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        self.last_gemini_call_time = 0
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
                logger.info("Gemini AI model configured successfully.")
            except Exception as e:
                self.gemini_model = None; logger.error(f"Failed to configure Gemini: {e}")
        else:
            self.gemini_model = None
            logger.warning("GEMINI_API_KEY not found. Gemini confirmation will be disabled.")

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Dict[str, Any]:
        raw_analysis = {"symbol": symbol, "timeframe": timeframe}
        try:
            # اجرای تمام موتورها با مدیریت خطای مجزا برای هر کدام
            df_with_indicators = calculate_indicators(df.copy())
            latest_indicator_values = {col: df_with_indicators[col].dropna().iloc[-1] for col in df_with_indicators.columns if col not in df.columns and not df_with_indicators[col].dropna().empty}
            if not df.empty and 'close' in df.columns: latest_indicator_values['close'] = df['close'].iloc[-1]
            raw_analysis["indicators"] = latest_indicator_values
            
            raw_analysis["trend"] = analyze_trend(df_with_indicators.copy(), timeframe=timeframe)
            raw_analysis["market_structure"] = LegPivotAnalyzer(df_with_indicators.copy()).analyze()
            raw_analysis["candlestick_patterns"] = CandlestickPatternDetector(df.copy()).analyze()
            raw_analysis["divergence"] = DivergenceDetector(df_with_indicators.copy()).analyze()
            raw_analysis["whale_activity"] = WhaleAnalyzer(df.copy()).analyze()
            
            strategy_engine = StrategyEngine(raw_analysis)
            signal_type = "BUY" if "Uptrend" in raw_analysis.get("trend", {}).get('signal', '') else ("SELL" if "Downtrend" in raw_analysis.get("trend", {}).get('signal', '') else "HOLD")
            raw_analysis["strategy"] = strategy_engine.generate_strategy(signal_type)

        except Exception as e:
            logger.error(f"Major failure in analyze_single_dataframe for {symbol}@{timeframe}: {e}", exc_info=True)
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}
        return raw_analysis

    async def _query_gemini_with_rate_limit(self, prompt: str) -> Dict[str, Any]:
        default_response = {"signal": "N/A", "confidence": 0, "explanation_fa": "تحلیل AI به دلیل محدودیت فراخوانی انجام نشد."}
        now = time.time()
        if (now - self.last_gemini_call_time) < GEMINI_CALL_COOLDOWN_SECONDS:
            logger.info("Gemini call skipped due to rate limiting cooldown.")
            return default_response
        
        try:
            logger.info("Querying Gemini AI for signal confirmation and explanation...")
            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            self.last_gemini_call_time = time.time()
            
            cleaned_response = response.text.replace("`", "").replace("json", "").strip()
            json_response = json.loads(cleaned_response)
            
            signal = json_response.get("signal", "HOLD").upper()
            explanation = json_response.get("explanation_fa", "توضیحات توسط AI ارائه نشد.")
            confidence = 85 if signal != "HOLD" else 50
            
            return {"signal": signal, "confidence": confidence, "explanation_fa": explanation}

        except Exception as e:
            logger.error(f"Gemini API call or JSON parsing failed: {e}")
            default_response["explanation_fa"] = "خطا در پردازش پاسخ AI."
            default_response["signal"] = "Error"
            return default_response

    async def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0.0, 0.0
        
        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict): continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            
            if "Uptrend" in data.get('trend', {}).get('signal', ''): buy_score += 1.5 * weight
            if "Downtrend" in data.get('trend', {}).get('signal', ''): sell_score += 1.5 * weight
            if data.get('divergence', {}).get('rsi_bullish'): buy_score += 1.0 * weight
            if data.get('divergence', {}).get('rsi_bearish'): sell_score += 1.0 * weight
            if any('Bullish' in p for p in data.get('candlestick_patterns', [])): buy_score += 0.5 * weight
            if any('Bearish' in p for p in data.get('candlestick_patterns', [])): sell_score += 0.5 * weight
            if data.get('whale_activity', {}).get('activity') == 'Accumulation': buy_score += 0.75 * weight
            if data.get('whale_activity', {}).get('activity') == 'Distribution': sell_score += 0.75 * weight

        final_signal = "HOLD"
        if buy_score > sell_score and buy_score >= SCORE_THRESHOLD: final_signal = "BUY"
        elif sell_score > buy_score and sell_score >= SCORE_THRESHOLD: final_signal = "SELL"

        gemini_confirmation = {"signal": "N/A", "confidence": 0, "explanation_fa": "تحلیل AI انجام نشد (سیگنال اولیه ضعیف بود)."}
        if final_signal != "HOLD" and self.gemini_model:
            symbol = next((data['symbol'] for data in all_tf_analysis.values() if 'symbol' in data), "N/A")
            
            prompt = f"""
            You are an expert, senior crypto technical analyst providing analysis for a trader.
            Analyze the following JSON data for the cryptocurrency {symbol}.
            Based SOLELY on the provided data, provide your final signal recommendation and a concise, easy-to-understand explanation in Persian.
            Your analysis MUST highlight the most important technical factors and mention any conflicts between timeframes if they exist.

            Technical Data:
            {json.dumps(all_tf_analysis, indent=2, default=str)}

            Provide your response ONLY in the following JSON format. Do not add any other text or formatting.
            {{
              "signal": "BUY",
              "explanation_fa": "یک توضیح خلاصه و حرفه‌ای به زبان فارسی در اینجا بنویس."
            }}
            
            Replace "BUY" with "SELL" or "HOLD" based on your final conclusion from the data.
            """
            gemini_confirmation = await self._query_gemini_with_rate_limit(prompt)
        
        return {"rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}

