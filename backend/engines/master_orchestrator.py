# engines/master_orchestrator.py (نسخه نهایی با هر دو اصلاح)

import os
import google.generativeai as genai
import logging
import pandas as pd
from typing import Dict, Any
import time
import asyncio
import json

from .indicator_analyzer import calculate_indicators
from .trend_analyzer import analyze_trend
from .market_structure_analyzer import LegPivotAnalyzer
from .strategy_engine import StrategyEngine
from .candlestick_reader import CandlestickPatternDetector
from .divergence_detector import detect_divergences 
from .whale_analyzer import WhaleAnalyzer

logger = logging.getLogger(__name__)

ENGINE_VERSION = "5.2.0" # افزایش نسخه به دلیل تغییرات منطقی
TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2.5, '1h': 2, '15m': 1, '5m': 0.5}
SCORE_THRESHOLD = 5.0
GEMINI_CALL_COOLDOWN_SECONDS = 900

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
                self.gemini_model = None
                logger.error(f"Failed to configure Gemini: {e}")
        else:
            self.gemini_model = None
            logger.warning("GEMINI_API_KEY not found. Gemini confirmation will be disabled.")
        logger.info(f"MasterOrchestrator initialized. Engine Version: {ENGINE_VERSION}")

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Dict[str, Any]:
        if df is None or df.empty:
            return {"error": "Empty or None dataframe received", "symbol": symbol, "timeframe": timeframe}

        raw_analysis = {"symbol": symbol, "timeframe": timeframe, "dataframe": df}
        try:
            df_with_indicators = calculate_indicators(df.copy())
            latest_indicator_values = {col: df_with_indicators[col].dropna().iloc[-1] for col in df_with_indicators.columns if col not in df.columns and not df_with_indicators[col].dropna().empty}
            if 'close' in df.columns and not df['close'].empty:
                latest_indicator_values['close'] = df['close'].iloc[-1]
            raw_analysis["indicators"] = latest_indicator_values
            
            raw_analysis["trend"] = analyze_trend(df_with_indicators.copy(), timeframe=timeframe)
            raw_analysis["market_structure"] = LegPivotAnalyzer(df_with_indicators.copy()).analyze()
            
            # --- ✅ اصلاح اول: فیلتر کردن الگوهای کندلی ---
            pattern_detector = CandlestickPatternDetector(df.copy())
            filtered_patterns = pattern_detector.apply_filters(min_score=1.5, min_volume_ratio=1.1)
            raw_analysis["patterns"] = [p['pattern'] for p in filtered_patterns]
            
            raw_analysis["divergence"] = detect_divergences(df_with_indicators.copy())
            
            # --- ✅ اصلاح دوم: قانون "No Plan, No Signal" با تورفتگی صحیح ---
            strategy_engine = StrategyEngine(raw_analysis)
            initial_signal = "BUY" if "Uptrend" in raw_analysis.get("trend", {}).get('signal', '') else ("SELL" if "Downtrend" in raw_analysis.get("trend", {}).get('signal', '') else "HOLD")

            if initial_signal != "HOLD":
                strategy = strategy_engine.generate_strategy(initial_signal)
                # اگر استراتژی تولید شده معتبر نباشد (بدون حد ضرر یا تارگت)، سیگنال را نادیده بگیر
                if not strategy_engine.is_strategy_valid(strategy):
                    initial_signal = "HOLD" 
                raw_analysis["strategy"] = strategy
            else:
                raw_analysis["strategy"] = {}

            # سیگنال نهایی در این تایم فریم به روز می شود تا در امتیازدهی استفاده شود
            raw_analysis["trend"]["signal"] = initial_signal

        except Exception as e:
            logger.error(f"Major failure in analyze_single_dataframe for {symbol}@{timeframe}: {e}", exc_info=True)
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}
        return raw_analysis

    async def _query_gemini_with_rate_limit(self, prompt: str) -> Dict[str, Any]:
        default_response = {"signal": "N/A", "confidence": 0, "explanation_fa": "تحلیل AI به دلیل محدودیت فراخوانی انجام نشد."}
        
        if not self.gemini_model:
            logger.warning("Gemini model not initialized, skipping query.")
            default_response["explanation_fa"] = "مدل AI به درستی مقداردهی اولیه نشده است."
            return default_response

        now = time.time()
        if (now - self.last_gemini_call_time) < GEMINI_CALL_COOLDOWN_SECONDS:
            logger.info("Gemini call skipped due to rate limiting cooldown.")
            return default_response
        try:
            logger.info("Querying Gemini AI for signal confirmation and explanation...")
            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            self.last_gemini_call_time = time.time()
            cleaned_response = response.text.replace("`", "").replace("json", "").strip()
            if not cleaned_response.startswith("{") or not cleaned_response.endswith("}"):
                raise ValueError(f"Invalid Gemini response format: {cleaned_response}")
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
        symbol = next((data.get('symbol') for data in all_tf_analysis.values() if isinstance(data, dict)), "N/A")

        try:
            whale_analyzer = WhaleAnalyzer(timeframes=list(all_tf_analysis.keys()))
            for tf, data in all_tf_analysis.items():
                if isinstance(data, dict) and "dataframe" in data and not data["dataframe"].empty:
                    whale_analyzer.update_data(tf, data["dataframe"])
            whale_analyzer.generate_signals()
            whale_signals = whale_analyzer.get_signals()
            for tf, signals in whale_signals.items():
                if tf in all_tf_analysis and signals:
                    all_tf_analysis[tf]['whale_activity'] = signals[-1]
        except Exception as e:
            logger.error(f"Whale analysis failed: {e}", exc_info=True)

        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict) or "error" in data: continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            
            # حالا به جای 'Uptrend' یا 'Downtrend' از سیگنال نهایی و فیلتر شده استفاده می کنیم
            tf_signal = data.get('trend', {}).get('signal', 'HOLD')
            if tf_signal == 'BUY': buy_score += 1.5 * weight
            elif tf_signal == 'SELL': sell_score += 1.5 * weight

            if data.get('divergence', {}).get('rsi_bullish'): buy_score += 1.0 * weight
            if data.get('divergence', {}).get('rsi_bearish'): sell_score += 1.0 * weight
            if any('Bullish' in p for p in data.get('patterns', [])): buy_score += 0.5 * weight
            if any('Bearish' in p for p in data.get('patterns', [])): sell_score += 0.5 * weight
            
            activity = data.get('whale_activity', {}).get('type', '')
            if activity == 'volume_spike': buy_score += 0.75 * weight
            elif activity == 'anomaly': sell_score += 0.75 * weight
            elif activity == 'buy_wall': buy_score += 0.5 * weight
            elif activity == 'sell_pressure': sell_score += 0.5 * weight

        final_signal = "HOLD"
        if buy_score > sell_score and buy_score >= SCORE_THRESHOLD: final_signal = "BUY"
        elif sell_score > buy_score and sell_score >= SCORE_THRESHOLD: final_signal = "SELL"

        gemini_confirmation = {"signal": "N/A", "confidence": 0, "explanation_fa": "تحلیل AI انجام نشد (سیگنال اولیه ضعیف بود)."}
        if final_signal != "HOLD" and self.gemini_model:
            # ساخت یک نسخه تمیز از all_tf_analysis برای ارسال به Gemini
            prompt_details = {}
            for tf, data in all_tf_analysis.items():
                clean_data = data.copy()
                clean_data.pop('dataframe', None)
                prompt_details[tf] = clean_data
            
            prompt = f"""
            You are an expert crypto analyst. Analyze the JSON data for {symbol}.
            Provide a response ONLY in JSON format with two keys: "signal" (BUY, SELL, or HOLD) and "explanation_fa" (a concise, professional explanation in Persian).
            Technical Data: {json.dumps(prompt_details, indent=2, default=str)}
            """
            gemini_confirmation = await self._query_gemini_with_rate_limit(prompt)
        
        return {
            "symbol": symbol, "engine_version": ENGINE_VERSION, "rule_based_signal": final_signal,
            "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2),
            "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis
        }
