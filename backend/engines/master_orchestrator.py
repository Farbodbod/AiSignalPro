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
        self.local_ai_engine = AIEngineProAdvanced()

    def analyze_single_dataframe(self, df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
        """تمام تحلیل‌ها را با مدیریت خطای داخلی اجرا می‌کند."""
        raw_analysis = {}
        try:
            if 'timestamp' in df.columns:
                df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms' if df['timestamp'].iloc[0] > 10**12 else 's')

            # --- اجرای موتورها با try-except مجزا برای هر کدام ---
            try:
                df_with_indicators = calculate_indicators(df.copy())
                latest_indicator_values = {}
                for col in df_with_indicators.columns:
                    if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'timestamp_dt']:
                        if not df_with_indicators[col].dropna().empty:
                            last_valid_value = df_with_indicators[col].dropna().iloc[-1]
                            latest_indicator_values[col] = last_valid_value
                if not df.empty and 'close' in df.columns:
                    latest_indicator_values['close'] = df['close'].iloc[-1]
                raw_analysis["indicators"] = latest_indicator_values
            except Exception as e:
                logger.error(f"Indicator analysis failed: {e}")
                raw_analysis["indicators"] = {}

            try:
                raw_analysis["trend"] = analyze_trend(df.copy(), timeframe=timeframe)
            except Exception as e:
                logger.error(f"Trend analysis failed: {e}")
                raw_analysis["trend"] = {}

            # ... (می‌توانید برای هر موتور دیگر نیز try-except مشابه اضافه کنید) ...
            
            raw_analysis["market_structure"] = LegPivotAnalyzer(df.copy()).analyze()

            # --- اجرای موتور استراتژی ---
            strategy_engine = StrategyEngine(raw_analysis)
            signal_type = "BUY" if "Uptrend" in raw_analysis.get("trend", {}).get('signal', '') else ("SELL" if "Downtrend" in raw_analysis.get("trend", {}).get('signal', '') else "HOLD")
            raw_analysis["strategy"] = strategy_engine.generate_strategy(signal_type)

        except Exception as e:
            logger.error(f"Major failure in analyze_single_dataframe for {timeframe}: {e}", exc_info=True)
            return {"error": str(e)}

        return raw_analysis

    def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        buy_score, sell_score = 0, 0
        for tf, data in all_tf_analysis.items():
            if not isinstance(data, dict): continue
            weight = TIMEFRAME_WEIGHTS.get(tf, 1)
            if "Uptrend" in data.get('trend', {}).get('signal', ''): buy_score += 1 * weight
            if "Downtrend" in data.get('trend', {}).get('signal', ''): sell_score += 1 * weight
        
        final_signal, gemini_confirmation = "HOLD", {"signal": "N/A", "confidence": 0}
        if buy_score > sell_score and buy_score > SCORE_THRESHOLD: final_signal = "BUY"
        elif sell_score > buy_score and sell_score > SCORE_THRESHOLD: final_signal = "SELL"

        if final_signal != "HOLD" and self.gemini_model:
            # ... (منطق تماس با Gemini)
            pass
        
        return {"rule_based_signal": final_signal, "buy_score": round(buy_score, 2), "sell_score": round(sell_score, 2), "gemini_confirmation": gemini_confirmation, "details": all_tf_analysis}

    # ... (بقیه توابع _generate_composite_prompt و _query_gemini) ...
