# engines/master_orchestrator.py (v18.0 - MTF Aware)

import pandas as pd
import logging
import time
import json
from typing import Dict, Any, List, Type, Optional

from .indicator_analyzer import IndicatorAnalyzer
from .gemini_handler import GeminiHandler
from .strategies import (
    BaseStrategy, TrendRiderStrategy, MeanReversionStrategy, 
    DivergenceSniperStrategy, PivotReversalStrategy, VolumeCatalystStrategy,
    IchimokuProStrategy
)

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderStrategy, MeanReversionStrategy, DivergenceSniperStrategy,
            PivotReversalStrategy, VolumeCatalystStrategy, IchimokuProStrategy,
        ]
        self.gemini_handler = GeminiHandler()
        self.last_gemini_call_time = 0
        self.ENGINE_VERSION = "18.0.0" # نسخه با قابلیت چند-زمانی
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (MTF-Aware) initialized.")

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "gemini_cooldown_seconds": 300,
            "min_confluence_for_super_signal": 3,
            "strategy_priority": [
                "SuperSignal Confluence", "DivergenceSniper", "VolumeCatalyst", "IchimokuPro",
                "TrendRider", "PivotReversalStrategy", "MeanReversionStrategy",
            ],
            'TrendRiderStrategy': { 'min_adx_strength': 25 },
            'MeanReversionStrategy': { 'rsi_oversold': 30, 'rsi_overbought': 70 },
            'DivergenceSniperStrategy': {
                'bullish_reversal_patterns': ['HAMMER', 'MORNINGSTAR', 'BULLISHENGULFING'],
                'bearish_reversal_patterns': ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING'],
            },
            'PivotReversalStrategy': { 'proximity_percent': 0.002, 'stoch_oversold': 25, 'stoch_overbought': 75},
            'VolumeCatalystStrategy': { 'enabled': True },
            'IchimokuProStrategy': { 'min_score_to_signal': 5 },
        }

    def _find_super_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        min_confluence = self.config.get("min_confluence_for_super_signal", 3)
        buy_signals = [s for s in signals if s['direction'] == 'BUY']
        sell_signals = [s for s in signals if s['direction'] == 'SELL']
        if len(buy_signals) >= min_confluence:
            # ... (Logic from previous full version)
            return {} # Placeholder for brevity, full logic assumed
        return None
    
    def _get_ai_confirmation(self, signal: Dict[str, Any], symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        # ... (Logic from previous full version)
        return {} # Placeholder for brevity, full logic assumed

    def run_full_pipeline(self, df_ltf: pd.DataFrame, timeframe_ltf: str, df_htf: pd.DataFrame, timeframe_htf: str, symbol: str) -> Optional[Dict[str, Any]]:
        analyzer_ltf = IndicatorAnalyzer(df_ltf); analyzer_ltf.calculate_all()
        analysis_ltf = analyzer_ltf.get_analysis_summary()
        if len(df_ltf) >= 2: analysis_ltf['price_data_prev'] = {'close': df_ltf.iloc[-2].get('close')}
        
        analyzer_htf = IndicatorAnalyzer(df_htf); analyzer_htf.calculate_all()
        analysis_htf = analyzer_htf.get_analysis_summary()

        valid_signals: List[Dict[str, Any]] = []
        for strategy_class in self._strategy_classes:
            strategy_name = strategy_class.__name__
            strategy_config = self.config.get(strategy_name, {})
            instance = strategy_class(analysis_ltf, strategy_config, htf_analysis=analysis_htf)
            signal = instance.check_signal()
            if signal:
                valid_signals.append(signal)
        
        if not valid_signals: return None

        best_signal = self._find_super_signal(valid_signals)
        if not best_signal:
             priority_list = self.config.get("strategy_priority", [])
             valid_signals.sort(key=lambda s: priority_list.index(s['strategy_name']) if s['strategy_name'] in priority_list else 99)
             best_signal = valid_signals[0]
        
        ai_confirmation = self._get_ai_confirmation(best_signal, symbol, timeframe_ltf)
        if ai_confirmation is None: return None
        
        return { 
            "symbol": symbol, "timeframe": timeframe_ltf, "base_signal": best_signal, 
            "ai_confirmation": ai_confirmation, "full_analysis": analysis_ltf 
        }
