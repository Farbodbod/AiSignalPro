# engines/master_orchestrator.py

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
from engines.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)

TIMEFRAME_WEIGHTS = {'1d': 3, '4h': 2, '1h': 1.5, '15m': 1, '5m': 0.5}
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
        """تمام تحلیل‌ها و استراتژی‌ها را روی یک دیتافریم اجرا می‌کند."""
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

        raw_analysis = {
            "indicators": latest_indicator_values,
            "trend": analyze_trend(df.copy(), timeframe=timeframe),
            "market_structure": LegPivotAnalyzer(df.copy()).analyze()
        }
        
        strategy_engine = StrategyEngine(raw_analysis)
        signal_type = "BUY" if "Uptrend" in raw_analysis["trend"].get('signal', '') else ("SELL" if "Downtrend" in raw_analysis["trend"].get('signal', '') else "HOLD")
        raw_analysis["strategy"] = strategy_engine.generate_strategy(signal_type)
        
        return raw_analysis

    def _generate_composite_prompt(self, all_tf_analysis: Dict[str, Any], scores: Dict[str, float]) -> str:
        prompt = f"""
        Analyze multi-timeframe market data. Rule-based scores are BUY: {scores['buy_score']:.2f}, SELL: {scores['sell_score']:.2f}.
        Provide a final signal (BUY, SELL, HOLD) and a confidence score (0-100).
        Respond ONLY with a valid JSON object: {{"signal": "...", "confidence": ...}}

        --- Data Summary ---
        """
        for tf, data in all_tf_analysis.items():
            prompt += f"\n- Timeframe: {tf}, Trend: {data.get('trend', {}).get('signal')}, Market Phase: {data.get('market_structure', {}).get('market_phase')}"
        return prompt
        
    def _query_gemini(self, prompt: str) -> Dict[str, Any]:
        if not self.gemini_model: return {"signal": "N/A", "confidence": 0}
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Gemini query failed: {e}")
            return {"signal": "Error", "confidence": 0}

    def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0, 0
        for tf, data in all_tf_analysis.items():
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            if "Uptrend" in data.get('trend', {}).get('signal', ''): buy_score += 1 * weight
            elif "Downtrend" in data.get('trend', {}).get('signal', ''): sell_score += 1 * weight
        
        final_signal, gemini_confirmation = "HOLD", {}
        if buy_score > sell_score and buy_score > SCORE_THRESHOLD: final_signal = "BUY"
        elif sell_score > buy_score and sell_score > SCORE_THRESHOLD: final_signal = "SELL"

        if final_signal != "HOLD":
            logging.info(f"Score threshold met (Buy: {buy_score:.2f}, Sell: {sell_score:.2f}). Querying Gemini.")
            scores = {"buy_score": buy_score, "sell_score": sell_score}
            prompt = self._generate_composite_prompt(all_tf_analysis, scores)
            gemini_confirmation = self._query_gemini(prompt)
        
        return {"rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}
