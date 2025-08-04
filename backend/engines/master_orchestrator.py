# engines/master_orchestrator.py (نسخه 8.0 با امتیازدهی هوشمند)

import os, logging, pandas as pd, time, asyncio, json
from typing import Dict, Any
from .indicator_analyzer import calculate_indicators
from .trend_analyzer import analyze_trend
from .market_structure_analyzer import LegPivotAnalyzer
from .strategy_engine import StrategyEngine
from .candlestick_reader import CandlestickPatternDetector
from .divergence_detector import detect_divergences
from .whale_analyzer import WhaleAnalyzer
from .gemini_handler import GeminiHandler

logger = logging.getLogger(__name__)

ENGINE_VERSION = "8.0.0" # نسخه با امتیازدهی هوشمند
TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2.5, '1h': 2, '15m': 1, '5m': 0.5}
SCORE_THRESHOLD = 7.0 # آستانه را کمی بالاتر می بریم چون امتیازهای بیشتری می دهیم
GEMINI_CALL_COOLDOWN_SECONDS = 300

class MasterOrchestrator:
    def __init__(self):
        self.gemini_handler = GeminiHandler(); self.last_gemini_call_time = 0
        logger.info(f"MasterOrchestrator initialized. Engine Version: {ENGINE_VERSION}")

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Dict[str, Any]:
        if df is None or df.empty: return {"error": "Empty or None dataframe received"}
        raw_analysis = {"symbol": symbol, "timeframe": timeframe, "dataframe": df}
        try:
            df_with_indicators = calculate_indicators(df.copy())
            raw_analysis["indicators"] = {col: df_with_indicators[col].dropna().iloc[-1] for col in df_with_indicators.columns if col not in df.columns and not df_with_indicators[col].dropna().empty}
            raw_analysis["trend"] = analyze_trend(df_with_indicators.copy(), timeframe=timeframe)
            if not raw_analysis.get("trend") or "error" in raw_analysis["trend"]:
                logger.warning(f"Trend analysis failed for {symbol}@{timeframe}. Aborting."); return {"error": "Trend analysis failed"}
            raw_analysis["market_structure"] = LegPivotAnalyzer(df_with_indicators.copy()).analyze()
            if not raw_analysis.get("market_structure"):
                logger.warning(f"Market structure analysis failed for {symbol}@{timeframe}. Aborting."); return {"error": "Market structure analysis failed"}
            raw_analysis["divergence"] = detect_divergences(df_with_indicators.copy())
            pattern_detector = CandlestickPatternDetector(df.copy(), raw_analysis)
            raw_analysis["patterns"] = pattern_detector.detect_high_quality_patterns() or []
            strategy_engine = StrategyEngine(raw_analysis)
            initial_signal = "HOLD"
            trend_signal_text = raw_analysis.get("trend", {}).get('signal', 'Neutral').lower()
            if "uptrend" in trend_signal_text: initial_signal = "BUY"
            elif "downtrend" in trend_signal_text: initial_signal = "SELL"
            if initial_signal != "HOLD":
                strategy = strategy_engine.generate_strategy(initial_signal)
                if strategy_engine.is_strategy_valid(strategy): 
                    raw_analysis["strategy"] = strategy; logger.info(f"✅ Valid strategy found for {symbol}@{timeframe}: {strategy.get('strategy_name')}")
                else: 
                    raw_analysis["strategy"] = {}; logger.info(f"Strategy for {symbol}@{timeframe} failed risk validation.")
            else: raw_analysis["strategy"] = {}
        except Exception as e:
            logger.error(f"Major failure in analyze_single_dataframe for {symbol}@{timeframe}: {e}", exc_info=True); return {"error": str(e)}
        return raw_analysis

    async def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0.0, 0.0
        symbol = next((data.get('symbol') for data in all_tf_analysis.values() if isinstance(data, dict)), "N/A")
        
        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict) or "error" in data: continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            
            bullish_factors, bearish_factors = [], []
            if "Uptrend" in data.get('trend', {}).get('signal', ''): bullish_factors.append(1.5)
            if data.get('divergence', {}).get('rsi_bullish') or data.get('divergence', {}).get('macd_bullish'): bullish_factors.append(1.5)
            if data.get('market_structure', {}).get('predicted_next_leg_direction') == 'up': bullish_factors.append(1.0)
            if any('Bullish' in p for p in data.get('patterns', [])): bullish_factors.append(0.5)
            if data.get('whale_activity', {}).get('type') == 'volume_spike': bullish_factors.append(0.75)
            
            if "Downtrend" in data.get('trend', {}).get('signal', ''): bearish_factors.append(1.5)
            if data.get('divergence', {}).get('rsi_bearish') or data.get('divergence', {}).get('macd_bearish'): bearish_factors.append(1.5)
            if data.get('market_structure', {}).get('predicted_next_leg_direction') == 'down': bearish_factors.append(1.0)
            if any('Bearish' in p for p in data.get('patterns', [])): bearish_factors.append(0.5)
            if data.get('whale_activity', {}).get('type') == 'anomaly': bearish_factors.append(0.75)

            if len(bullish_factors) > len(bearish_factors):
                buy_score += sum(bullish_factors) * weight
            elif len(bearish_factors) > len(bullish_factors):
                sell_score += sum(bearish_factors) * weight
        
        final_signal = "BUY" if buy_score > sell_score and buy_score >= SCORE_THRESHOLD else ("SELL" if sell_score > buy_score and sell_score >= SCORE_THRESHOLD else "HOLD")
        
        gemini_confirmation = {"signal": "N/A", "confidence": 0, "explanation_fa": "AI analysis not triggered."}
        if final_signal != "HOLD":
            now = time.time()
            if (now - self.last_gemini_call_time) < GEMINI_CALL_COOLDOWN_SECONDS:
                gemini_confirmation["explanation_fa"] = "AI analysis skipped due to cooldown."
            else:
                self.last_gemini_call_time = time.time()
                prompt_details = {tf: {k: v for k, v in data.items() if k != 'dataframe'} for tf, data in all_tf_analysis.items()}
                prompt = f'Analyze this JSON data for {symbol} and provide a response ONLY in JSON format with keys "signal" (BUY/SELL/HOLD) and "explanation_fa" (concise, professional explanation in Persian).\nTechnical Data: {json.dumps(prompt_details, indent=2, default=str)}'
                gemini_confirmation = await self.gemini_handler.query(prompt)
        
        return {"symbol": symbol, "engine_version": ENGINE_VERSION, "rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}
