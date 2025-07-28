# engines/master_orchestrator.py (نسخه نهایی با مدیریت محدودیت Gemini)

import os
import google.generativeai as genai
import logging
import pandas as pd
from typing import Dict, Any
import time
import json

from engines.candlestick_reader import CandlestickPatternDetector
from engines.indicator_analyzer import calculate_indicators
from engines.trend_analyzer import analyze_trend
from engines.whale_analyzer import WhaleAnalyzer
from engines.divergence_detector import detect_divergences
from engines.market_structure_analyzer import LegPivotAnalyzer
from engines.ai_predictor import AIEngineProAdvanced
from engines.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)

TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2.5, '1h': 2, '15m': 1, '5m': 0.5}
SCORE_THRESHOLD = 4.0
GEMINI_CALL_COOLDOWN_SECONDS = 600  # هر ۱۰ دقیقه حداکثر یک بار با جمینی تماس گرفته می‌شود

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
                logger.error(f"Failed to configure Gemini: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None
            logger.warning("GEMINI_API_KEY not found. Gemini confirmation will be disabled.")
            
        self.local_ai_engine = AIEngineProAdvanced()

    ## --- اصلاح شد: پارامتر symbol به تابع اضافه شد --- ##
    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Dict[str, Any]:
        raw_analysis = {"symbol": symbol, "timeframe": timeframe} # اطلاعات پایه
        try:
            if 'timestamp' in df.columns:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms' if df['timestamp'].iloc[0] > 10**12 else 's')

            try:
                df_with_indicators = calculate_indicators(df.copy())
                latest_indicator_values = {col: df_with_indicators[col].dropna().iloc[-1] for col in df_with_indicators.columns if col not in df.columns and not df_with_indicators[col].dropna().empty}
                if not df.empty and 'close' in df.columns:
                    latest_indicator_values['close'] = df['close'].iloc[-1]
                raw_analysis["indicators"] = latest_indicator_values
            except Exception as e:
                logger.error(f"Indicator analysis failed for {symbol}@{timeframe}: {e}")
                raw_analysis["indicators"] = {}

            try:
                raw_analysis["trend"] = analyze_trend(df.copy(), timeframe=timeframe)
            except Exception as e:
                logger.error(f"Trend analysis failed for {symbol}@{timeframe}: {e}")
                raw_analysis["trend"] = {}
            
            try:
                raw_analysis["market_structure"] = LegPivotAnalyzer(df.copy()).analyze()
            except Exception as e:
                logger.error(f"Market structure analysis failed for {symbol}@{timeframe}: {e}")
                raw_analysis["market_structure"] = {}
                
            strategy_engine = StrategyEngine(raw_analysis)
            signal_type = "BUY" if "Uptrend" in raw_analysis.get("trend", {}).get('signal', '') else ("SELL" if "Downtrend" in raw_analysis.get("trend", {}).get('signal', '') else "HOLD")
            raw_analysis["strategy"] = strategy_engine.generate_strategy(signal_type)

        except Exception as e:
            logger.error(f"Major failure in analyze_single_dataframe for {symbol}@{timeframe}: {e}", exc_info=True)
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}

        return raw_analysis

    def _query_gemini_with_rate_limit(self, prompt: str) -> Dict[str, Any]:
        """با مدیریت زمانبندی با جمینی ارتباط برقرار می‌کند تا از محدودیت‌ها جلوگیری شود."""
        now = time.time()
        if (now - self.last_gemini_call_time) < GEMINI_CALL_COOLDOWN_SECONDS:
            logger.info("Gemini call skipped due to rate limiting cooldown.")
            return {"signal": "N/A", "reason": "Rate limit cooldown", "confidence": 0}
        
        try:
            logger.info("Querying Gemini AI for signal confirmation...")
            response = self.gemini_model.generate_content(prompt)
            self.last_gemini_call_time = time.time() # ثبت زمان آخرین تماس موفق
            
            # (منطق ساده برای استخراج تحلیل از پاسخ جمینی)
            text_response = response.text.lower()
            if "buy" in text_response: signal = "BUY"
            elif "sell" in text_response: signal = "SELL"
            else: signal = "HOLD"
            return {"signal": signal, "reason": response.text, "confidence": 75 if signal != "HOLD" else 50}

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return {"signal": "Error", "reason": str(e), "confidence": 0}

    def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0, 0
        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict): continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            trend_signal = data.get('trend', {}).get('signal', '')
            if "Uptrend" in trend_signal: buy_score += 1 * weight
            if "Downtrend" in trend_signal: sell_score += 1 * weight
        
        final_signal, gemini_confirmation = "HOLD", {"signal": "N/A", "confidence": 0}
        if buy_score > sell_score and buy_score >= SCORE_THRESHOLD: final_signal = "BUY"
        elif sell_score > buy_score and sell_score >= SCORE_THRESHOLD: final_signal = "SELL"

        if final_signal != "HOLD" and self.gemini_model:
            # ## --- اصلاح شد: منطق تماس با جمینی با مدیریت محدودیت --- ##
            symbol = next((data['symbol'] for data in all_tf_analysis.values() if 'symbol' in data), "N/A")
            prompt = f"Analyze the market situation for {symbol}. The current rule-based signal is {final_signal}. Should I proceed? Provide a short 'BUY', 'SELL', or 'HOLD' recommendation and a brief justification."
            gemini_confirmation = self._query_gemini_with_rate_limit(prompt)
        
        return {
            "rule_based_signal": final_signal, 
            "buy_score": round(buy_score, 2), 
            "sell_score": round(sell_score, 2), 
            "gemini_confirmation": gemini_confirmation, 
            "details": all_tf_analysis
        }
