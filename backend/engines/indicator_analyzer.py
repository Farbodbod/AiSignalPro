import pandas as pd
import logging
from typing import Dict, Any, Type, List

# ایمپورت کردن تمام اندیکاتورهای پروژه
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Single-Timeframe Analysis Engine for AiSignalPro (v5.0 - Dependency-Aware)
    ---------------------------------------------------------------------------------
    This legendary version introduces a dependency-aware calculation order,
    permanently solving all KeyError issues related to inter-indicator dependencies.
    It ensures that base indicators are always calculated before composite ones.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe
        
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator,
            'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 'supertrend': SuperTrendIndicator,
            'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator,
            'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator,
            'structure': StructureIndicator, 'whales': WhaleIndicator,
            'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator,
            'kelt_channel': KeltnerChannelIndicator, 'zigzag': ZigzagIndicator,
            'fibonacci': FibonacciIndicator,
        }
        
        # ✨ THE MIRACLE: Define a calculation order based on dependencies
        self._calculation_order: List[str] = [
            # Level 0: No dependencies
            'atr', 'zigzag', 'patterns', 'vwap_bands', 'pivots',
            # Level 1: Depend on Level 0
            'rsi', 'mfi', 'stochastic', 'williams_r', 'bollinger', 'cci', 'macd',
            'supertrend', 'keltner_channel', 'donchian_channel', 'chandelier_exit',
            'fast_ma', 'ema_cross', 'obv', 'whales',
            # Level 2: Depend on Level 1
            'structure', 'fibonacci',
            # Level 3: The most complex dependencies
            'divergence',
        ]

        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = self.base_df.copy()

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """
        Calculates all enabled indicators in a dependency-aware order.
        """
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        df_for_calc = self.base_df.copy()

        # ✨ THE MIRACLE: Iterate in the correct dependency order
        for name in self._calculation_order:
            params = self.config.get(name, {})
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if not indicator_class:
                    logger.warning(f"Indicator class '{name}' not found for timeframe {self.timeframe}.")
                    continue
                try:
                    instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                    instance_params['timeframe'] = self.timeframe
                    
                    instance = indicator_class(df_for_calc, params=instance_params).calculate()
                    
                    df_for_calc = instance.df
                    self._indicator_instances[name] = instance
                    
                except Exception as e:
                    logger.error(f"Failed to calculate indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
        
        self.final_df = df_for_calc.copy()
        logger.info(f"Calculations for timeframe {self.timeframe} are complete.")
        return self

    def get_analysis_summary(self) -> Dict[str, Any]:
        """ Analyzes all calculated indicators and returns a self-contained summary report. """
        if len(self.final_df) < 2: return {"status": "Insufficient Data"}
        summary: Dict[str, Any] = {"status": "OK"}
        
        last_closed_candle = self.final_df.iloc[-2]
        summary['price_data'] = {
            'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'),
            'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'),
            'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name)
        }

        # ✨ REFINEMENT: Analyze in the same dependency order for consistency
        for name in self._calculation_order:
            if name in self._indicator_instances:
                instance = self._indicator_instances[name]
                try:
                    analysis = instance.analyze()
                    if analysis: summary[name] = analysis
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
                    summary[name] = {"error": str(e)}
        return summary
