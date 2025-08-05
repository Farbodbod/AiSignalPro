# engines/master_orchestrator.py
import pandas as pd
import logging
from typing import Dict, Any, List, Type
from .indicator_analyzer import IndicatorAnalyzer
from .strategies import (
    BaseStrategy, TrendRiderStrategy, MeanReversionStrategy, 
    DivergenceSniperStrategy, PivotReversalStrategy, VolumeCatalystStrategy,
    IchimokuProStrategy # <--- کلاس جدید
)
logger = logging.getLogger(__name__)

class MasterOrchestrator:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        self._strategy_classes: List[Type[BaseStrategy]] = [
            TrendRiderStrategy, MeanReversionStrategy, DivergenceSniperStrategy,
            PivotReversalStrategy, VolumeCatalystStrategy, IchimokuProStrategy, # <--- استراتژی جدید
        ]
        self.ENGINE_VERSION = "15.5.0" # نسخه با شش استراتژی
        logger.info(f"MasterOrchestrator v{self.ENGINE_VERSION} (Hexa-Strategy) initialized.")

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            'TrendRiderStrategy': { 'min_adx_strength': 25 },
            'MeanReversionStrategy': { 'rsi_oversold': 30, 'rsi_overbought': 70 },
            'DivergenceSniperStrategy': {
                'bullish_reversal_patterns': ['HAMMER', 'MORNINGSTAR', 'BULLISHENGULFING'],
                'bearish_reversal_patterns': ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING'],
            },
            'PivotReversalStrategy': { 'proximity_percent': 0.002, 'stoch_oversold': 25, 'stoch_overbought': 75},
            'VolumeCatalystStrategy': { 'enabled': True },
            'IchimokuProStrategy': { 'min_score_to_signal': 5 }, # <--- کانفیگ جدید
        }
        
    def run_analysis_for_symbol(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        # ... (این متد کاملاً بدون تغییر باقی می‌ماند)
        if len(df) < 52: return []
        analyzer = IndicatorAnalyzer(df)
        analyzer.calculate_all()
        analysis_summary = analyzer.get_analysis_summary()
        if len(df) >= 2: analysis_summary['price_data_prev'] = { 'close': df.iloc[-2].get('close') }
        valid_signals: List[Dict[str, Any]] = []
        for strategy_class in self._strategy_classes:
            try:
                strategy_name = strategy_class.__name__
                strategy_config = self.config.get(strategy_name, {})
                strategy_instance = strategy_class(analysis_summary, strategy_config)
                signal = strategy_instance.check_signal()
                if signal:
                    valid_signals.append(signal)
            except Exception as e:
                logger.error(f"Error running strategy {strategy_class.__name__}: {e}", exc_info=True)
        return valid_signals
