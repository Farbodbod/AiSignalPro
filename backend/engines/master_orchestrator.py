# engines/master_orchestrator.py (نسخه نهایی با منطق صحیح)
import os, google.generativeai as genai, logging, pandas as pd, time, asyncio, json
from typing import Dict, Any
from .indicator_analyzer import calculate_indicators
from .trend_analyzer import analyze_trend
from .market_structure_analyzer import LegPivotAnalyzer
from .strategy_engine import StrategyEngine
from .candlestick_reader import CandlestickPatternDetector
from .divergence_detector import detect_divergences
from .whale_analyzer import WhaleAnalyzer

logger = logging.getLogger(__name__)
ENGINE_VERSION, TIMEFRAME_WEIGHTS, SCORE_THRESHOLD, GEMINI_CALL_COOLDOWN_SECONDS = "5.3.0", {'1d': 3, '4h': 2.5, '1h': 2, '15m': 1, '5m': 0.5}, 5.0, 900

class MasterOrchestrator:
    def __init__(self):
        self.gemini_key = os.getenv('GEMINI_API_KEY')
        self.last_gemini_call_time = 0
        if self.gemini_key:
            try:
                genai.configure(api_key=self.gemini_key); self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest'); logger.info("Gemini AI model configured successfully.")
            except Exception as e: self.gemini_model = None; logger.error(f"Failed to configure Gemini: {e}")
        else: self.gemini_model = None; logger.warning("GEMINI_API_KEY not found.")
        logger.info(f"MasterOrchestrator initialized. Engine Version: {ENGINE_VERSION}")

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Dict[str, Any]:
        if df is None or df.empty: return {"error": "Empty DataFrame"}
        raw_analysis = {"symbol": symbol, "timeframe": timeframe, "dataframe": df}
        try:
            df_with_indicators = calculate_indicators(df.copy())
            raw_analysis["indicators"] = {col: df_with_indicators[col].dropna().iloc[-1] for col in df_with_indicators.columns if col not in df.columns and not df_with_indicators[col].dropna().empty}
            raw_analysis["trend"] = analyze_trend(df_with_indicators.copy(), timeframe=timeframe)
            raw_analysis["market_structure"] = LegPivotAnalyzer(df_with_indicators.copy()).analyze()
            pattern_detector = CandlestickPatternDetector(df.copy()); filtered_patterns = pattern_detector.apply_filters(min_score=1.5, min_volume_ratio=1.1)
            raw_analysis["patterns"] = [p['pattern'] for p in filtered_patterns]
            raw_analysis["divergence"] = detect_divergences(df_with_indicators.copy())
            strategy_engine = StrategyEngine(raw_analysis)
            initial_signal = raw_analysis.get("trend", {}).get('signal', 'HOLD')
            if initial_signal != "HOLD":
                strategy = strategy_engine.generate_strategy(initial_signal)
                if strategy_engine.is_strategy_valid(strategy): raw_analysis["strategy"] = strategy
                else: raw_analysis["strategy"] = {}
            else: raw_analysis["strategy"] = {}
        except Exception as e:
            logger.error(f"Failure in analyze_single_dataframe for {symbol}@{timeframe}: {e}", exc_info=True); return {"error": str(e)}
        return raw_analysis

    async def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0.0, 0.0
        symbol = next((data.get('symbol') for data in all_tf_analysis.values() if isinstance(data, dict)), "N/A")
        try:
            whale_analyzer = WhaleAnalyzer(timeframes=list(all_tf_analysis.keys()))
            for tf, data in all_tf_analysis.items():
                if isinstance(data, dict) and "dataframe" in data: whale_analyzer.update_data(tf, data["dataframe"])
            whale_analyzer.generate_signals(); whale_signals = whale_analyzer.get_signals()
            for tf, signals in whale_signals.items():
                if tf in all_tf_analysis and signals: all_tf_analysis[tf]['whale_activity'] = signals[-1]
        except Exception as e: logger.error(f"Whale analysis failed: {e}")

        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict) or "error" in data: continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            # ✨ اصلاح: امتیازدهی بر اساس سیگنال روند خام، قبل از فیلتر استراتژی
            trend_signal = data.get('trend', {}).get('signal', 'HOLD')
            if "Uptrend" in trend_signal: buy_score += 1.5 * weight
            if "Downtrend" in trend_signal: sell_score += 1.5 * weight
            if data.get('divergence', {}).get('rsi_bullish'): buy_score += 1.0 * weight
            if data.get('divergence', {}).get('rsi_bearish'): sell_score += 1.0 * weight
            if any('Bullish' in p for p in data.get('patterns', [])): buy_score += 0.5 * weight
            if any('Bearish' in p for p in data.get('patterns', [])): sell_score += 0.5 * weight

        final_signal = "BUY" if buy_score > sell_score and buy_score >= SCORE_THRESHOLD else ("SELL" if sell_score > buy_score and sell_score >= SCORE_THRESHOLD else "HOLD")
        
        gemini_confirmation = {"signal": "N/A"}
        now = time.time()
        if final_signal != "HOLD" and self.gemini_model and (now - self.last_gemini_call_time) > GEMINI_CALL_COOLDOWN_SECONDS:
            prompt_details = {tf: {k: v for k, v in data.items() if k != 'dataframe'} for tf, data in all_tf_analysis.items()}
            prompt = f'Analyze this JSON data for {symbol} and provide a response ONLY in JSON format with keys "signal" (BUY/SELL/HOLD) and "explanation_fa" (concise, professional explanation in Persian).\nTechnical Data: {json.dumps(prompt_details, indent=2, default=str)}'
            try:
                self.last_gemini_call_time = time.time(); response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
                json_response = json.loads(response.text.replace("`", "").replace("json", "").strip())
                gemini_confirmation = {"signal": json_response.get("signal", "HOLD").upper(), "explanation_fa": json_response.get("explanation_fa"), "confidence": 85 if json_response.get("signal") != "HOLD" else 50}
            except Exception as e: logger.error(f"Gemini API call failed: {e}"); gemini_confirmation['signal'] = "Error"
        
        return {"symbol": symbol, "engine_version": ENGINE_VERSION, "rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}
