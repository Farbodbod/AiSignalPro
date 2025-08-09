import pandas as pd
import logging
from typing import Dict, Any, Type, List

# ایمپورت کردن تمام اندیکاتورهای پروژه
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The strategic mastermind of the AiSignalPro project (v3.0 - Stateful & Optimized)
    ---------------------------------------------------------------------------------
    This version introduces a stateful, sequential data flow to correctly handle
    inter-indicator dependencies. It also resolves performance warnings and ensures
    all analyses are run on the complete, final dataset.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None, timeframes: List[str] = None):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex for MTF analysis.")
            
        self.base_df = df
        self.config = config if config is not None else self._get_default_config()
        self.timeframes = timeframes or ['5min', '15min', '1h', '4h']
        
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
        self._indicator_instances: Dict[str, Dict[str, BaseIndicator]] = {tf: {} for tf in self.timeframes}
        self.final_df = self.base_df.copy()

    def _get_default_config(self) -> Dict[str, Any]:
        # A sample config, should be completed
        return {'rsi': {'period': 14, 'enabled': True}, 'macd': {'enabled': True}}

    def calculate_all(self) -> pd.DataFrame:
        logger.info(f"Starting MTF calculation for timeframes: {self.timeframes}")
        
        # Start with a clean copy of the base dataframe
        df_for_calc = self.base_df.copy()

        for tf in self.timeframes:
            logger.info(f"--- Calculating for timeframe: {tf} ---")
            for name, params in self.config.items():
                if params.get('enabled', False):
                    indicator_class = self._indicator_classes.get(name)
                    if not indicator_class:
                        logger.warning(f"Indicator class '{name}' not found.")
                        continue
                    try:
                        instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                        instance_params['timeframe'] = tf
                        
                        # ✨ FIX #1: Sequential Data Flow
                        # The indicator is initialized with the most up-to-date dataframe
                        # ensuring dependencies from previous indicators are available.
                        instance = indicator_class(df_for_calc, params=instance_params).calculate()
                        
                        # The dataframe is updated for the next indicator in the chain.
                        df_for_calc = instance.df

                        self._indicator_instances[tf][name] = instance
                        
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}' on timeframe '{tf}': {e}", exc_info=True)
        
        # ✨ FIX #2: Defragment the final DataFrame for optimal performance.
        self.final_df = df_for_calc.copy()
        
        logger.info("All MTF calculations are complete.")
        return self.final_df

    def get_analysis_summary(self) -> Dict[str, Any]:
        if len(self.final_df) < 2:
            return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK"}
        last_closed_candle = self.base_df.iloc[-2]
        summary['price_data'] = {
            'close': last_closed_candle.get('close'),
            'timestamp': str(last_closed_candle.name)
        }

        for tf, instances in self._indicator_instances.items():
            tf_summary = {}
            for name, instance in instances.items():
                try:
                    # ✨ FIX #3: Ensure the instance analyzes the final, complete dataframe
                    # This gives every indicator's analyze() method full access to all columns.
                    instance.df = self.final_df
                    
                    analysis = instance.analyze()
                    if analysis:
                        tf_summary[name] = analysis
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}' on timeframe '{tf}': {e}", exc_info=True)
                    tf_summary[name] = {"error": str(e)}
            summary[tf] = tf_summary
            
        return summary
