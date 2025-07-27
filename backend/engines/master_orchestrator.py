# engines/master_orchestrator.py - نسخه نهایی با StrategyEngine

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
from engines.strategy_engine import StrategyEngine # <<-- موتور جدید اضافه شد

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
        whale_res = # ... (کد کامل این بخش مانند قبل)
        divergence_res = # ... (کد کامل این بخش مانند قبل)
        candlestick_res = # ... (کد کامل این بخش مانند قبل)
        market_structure_res = # ... (کد کامل این بخش مانند قبل)
        local_ai_res = # ... (کد کامل این بخش مانند قبل)

        # جمع‌آوری نتایج خام
        raw_analysis = {
            "trend": trend_res, "whales": whale_res, "divergence": divergence_res,
            "indicators": latest_indicator_values, "candlesticks": candlestick_res,
            "market_structure": market_structure_res,
            "local_ai": local_ai_res
        }
        
        # --- بخش جدید: اجرای موتور استراتژی ---
        strategy_engine = StrategyEngine(raw_analysis)
        # فرض می‌کنیم سیگنال اصلی از روند گرفته می‌شود
        signal_type = "BUY" if "Uptrend" in trend_res.get('signal', '') else ("SELL" if "Downtrend" in trend_res.get('signal', '') else "HOLD")
        strategy_res = strategy_engine.generate_strategy(signal_type)
        
        # اضافه کردن نتایج استراتژی به تحلیل کلی
        raw_analysis["strategy"] = strategy_res
        
        return raw_analysis

    def _generate_composite_prompt(self, all_tf_analysis: Dict[str, Any], scores: Dict[str, float]) -> str:
        # ... (این تابع بدون تغییر باقی می‌ماند)
        pass
        
    def _query_gemini(self, prompt: str) -> Dict[str, Any]:
        # ... (این تابع بدون تغییر باقی می‌ماند)
        pass

    def get_multi_timeframe_signal(self, all_tf_analysis: Dict[str, Any]) -> Dict[str, Any]:
        # ... (منطق امتیازدهی و سیگنال نهایی بدون تغییر باقی می‌ماند)
        pass
