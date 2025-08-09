import pandas as pd
import logging
from typing import Dict, Any, Type

# ایمپورت کردن تمام اندیکاتورهای پروژه
from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Single-Timeframe Analysis Engine for AiSignalPro (v4.1 - Final & Harmonized)
    ---------------------------------------------------------------------------------
    This final version includes price_data in its summary output to be fully
    harmonized with the BaseStrategy toolkit.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe # The single timeframe this instance is responsible for
        
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
        self.final_df = self.base_df.copy()

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """
        Calculates all enabled indicators sequentially for the single timeframe.
        This stateful, chained data flow ensures dependencies are met.
        """
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        
        df_for_calc = self.base_df.copy()

        for name, params in self.config.items():
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
        """
        Analyzes all calculated indicators for the single timeframe and returns a
        self-contained summary report.
        """
        if len(self.final_df) < 2:
            return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK"}
        
        # ✨ REFINEMENT: Add the last closed candle's price data to the summary.
        # This makes each summary a self-contained report for the strategies.
        last_closed_candle = self.final_df.iloc[-2]
        summary['price_data'] = {
            'open': last_closed_candle.get('open'),
            'high': last_closed_candle.get('high'),
            'low': last_closed_candle.get('low'),
            'close': last_closed_candle.get('close'),
            'volume': last_closed_candle.get('volume'),
            'timestamp': str(last_closed_candle.name)
        }

        for name, instance in self._indicator_instances.items():
            try:
                # The instance's internal dataframe is the complete, final one.
                # Its analyze() method is internally bias-free.
                analysis = instance.analyze()
                if analysis:
                    summary[name] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
                summary[name] = {"error": str(e)}
                
        return summary
