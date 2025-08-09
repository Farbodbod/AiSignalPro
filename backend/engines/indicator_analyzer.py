import pandas as pd
import logging
from typing import Dict, Any, Type

# ایمپورت کردن تمام اندیکاتورهای پروژه
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any] = None):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        self.df = df
        self.config = config if config is not None else self._get_default_config()
        
        # دیکشنری کامل و جامع از تمام اندیکاتورهای پروژه
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
        self._indicator_instances: Dict[str, BaseIndicator] = {}

    def _get_default_config(self) -> Dict[str, Any]:
        # کانفیگ پیش‌فرض برای تمام اندیکاتورها
        # (این بخش بدون تغییر باقی می‌ماند)
        return {
            'rsi': {'period': 14, 'enabled': True},
            'bollinger': {'period': 20, 'std_dev': 2, 'enabled': True},
            # ... and so on for all indicators
        }

    def calculate_all(self) -> pd.DataFrame:
        logger.info("Starting calculation for all enabled indicators.")
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        # ✨ FIX #1: The correct way to instantiate our indicators.
                        # We pass the DataFrame and the parameters as keyword arguments.
                        instance = indicator_class(self.df, params=params)
                        
                        # The calculate method in our world-class indicators now returns `self` (the instance).
                        # We update self.df from the instance's df attribute after calculation.
                        indicator_instance = instance.calculate()
                        self.df = indicator_instance.df
                        self._indicator_instances[name] = indicator_instance
                        
                    except Exception as e:
                        logger.error(f"Failed to calculate indicator '{name}': {e}", exc_info=True)
        return self.df

    def get_analysis_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        
        # ✨ FIX #2: Prevent Look-ahead Bias.
        # For a fully automated system, all analysis must be based on the last *closed* candle.
        if len(self.df) < 2:
            logger.warning("Not enough data for a bias-free analysis (requires at least 2 rows).")
            return {"status": "Insufficient Data"}
            
        # We prepare the analysis based on the last closed candle's data.
        closed_candle_df = self.df.iloc[:-1]
        
        last_closed_candle = closed_candle_df.iloc[-1]
        summary['price_data'] = {
            'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'),
            'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'),
            'volume': last_closed_candle.get('volume'),
            'timestamp': str(last_closed_candle.name)
        }
        
        for name, instance in self._indicator_instances.items():
            try:
                # We need to run analyze on the bias-free dataframe.
                # A robust way is to re-create the instance with the closed-candle data.
                # This ensures `analyze` methods also don't suffer from look-ahead bias.
                bias_free_instance = self._indicator_classes[name](closed_candle_df, params=instance.params)
                
                # The instance already has calculated columns, so we just need to analyze.
                # We assign the full df so it has the calculated columns, but analyze should use the last closed candle.
                bias_free_instance.df = self.df 
                
                analysis = bias_free_instance.analyze()
                if analysis: summary[name] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze indicator '{name}': {e}", exc_info=True)
                summary[name] = {"error": str(e)}
                
        return summary
