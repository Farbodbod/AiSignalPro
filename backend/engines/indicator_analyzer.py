import pandas as pd
import logging
from typing import Dict, Any, Type, List

# ایمپورت کردن تمام اندیکاتورهای پروژه (نسخه‌های کلاس جهانی و MTF)
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The strategic mastermind of the AiSignalPro project.
    -----------------------------------------------------
    This world-class version is a Multi-Timeframe (MTF) Orchestrator.
    It manages the calculation and analysis of all indicators across multiple
    timeframes, providing a comprehensive, bias-free, and real-time snapshot
    of the market, perfectly designed for a fully automated trading system.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None, timeframes: List[str] = None):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("DataFrame index must be a DatetimeIndex for MTF analysis.")
            
        self.base_df = df
        self.config = config if config is not None else self._get_default_config()
        self.timeframes = timeframes or ['5T', '15T', '1H', '4H']
        
        # Dictionary mapping indicator names to their classes
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
        # A nested dictionary to store instances: { '1H': { 'rsi': RsiInstance, ... }, '4H': { ... } }
        self._indicator_instances: Dict[str, Dict[str, BaseIndicator]] = {tf: {} for tf in self.timeframes}
        self.final_df = self.base_df.copy()

    def _get_default_config(self) -> Dict[str, Any]:
        # A more complete default config for our world-class indicators
        return {
            'rsi': {'period': 14, 'enabled': True},
            'macd': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9, 'enabled': True},
            'bollinger': {'period': 20, 'std_dev': 2.0, 'enabled': True},
            'supertrend': {'period': 10, 'multiplier': 3.0, 'enabled': True},
            'ichimoku': {'enabled': True},
            # ... add other indicator defaults here
        }

    def calculate_all(self) -> pd.DataFrame:
        """
        Orchestrates the calculation of all enabled indicators across all configured timeframes.
        This method follows the "Calculate Once" principle.
        """
        logger.info(f"Starting MTF calculation for timeframes: {self.timeframes}")
        
        # We work on a copy to aggregate all indicator columns
        df_with_all_indicators = self.base_df.copy()

        for tf in self.timeframes:
            logger.info(f"--- Calculating for timeframe: {tf} ---")
            for name, params in self.config.items():
                if params.get('enabled', False):
                    indicator_class = self._indicator_classes.get(name)
                    if not indicator_class:
                        logger.warning(f"Indicator class '{name}' not found.")
                        continue
                    try:
                        # Create instance with the base_df and pass the timeframe parameter
                        instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                        instance_params['timeframe'] = tf
                        
                        instance = indicator_class(self.base_df, params=instance_params)
                        instance.calculate()
                        
                        # Merge the newly calculated columns into our main df
                        for col in instance.df.columns:
                            if col not in df_with_all_indicators.columns:
                                df_with_all_indicators[col] = instance.df[col]

                        self._indicator_instances[tf][name] = instance
                        
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}' on timeframe '{tf}': {e}", exc_info=True)
        
        self.final_df = df_with_all_indicators
        logger.info("All MTF calculations are complete.")
        return self.final_df

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Analyzes all calculated indicators across all timeframes.
        This method is highly efficient as it performs no recalculations.
        It is also bias-free because each indicator's analyze() method is bias-free.
        """
        if len(self.final_df) < 2:
            return {"status": "Insufficient Data"}
        
        # The summary will be nested by timeframe
        summary: Dict[str, Any] = {"status": "OK"}
        
        # --- Price data is based on the base timeframe's last closed candle ---
        last_closed_candle = self.base_df.iloc[-2]
        summary['price_data'] = {
            'close': last_closed_candle.get('close'),
            'timestamp': str(last_closed_candle.name)
        }

        for tf, instances in self._indicator_instances.items():
            tf_summary = {}
            for name, instance in instances.items():
                try:
                    # Each indicator's analyze() method is already bias-free.
                    # We simply call it on the stored instance.
                    analysis = instance.analyze()
                    if analysis:
                        tf_summary[name] = analysis
                except Exception as e:
                    logger.error(f"Failed to analyze indicator '{name}' on timeframe '{tf}': {e}", exc_info=True)
                    tf_summary[name] = {"error": str(e)}
            summary[tf] = tf_summary
            
        return summary
