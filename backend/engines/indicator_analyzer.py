import pandas as pd
import logging
from typing import Dict, Any, Type, List, Optional
from collections import deque

from .indicators import *

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v7.2 - Anti-Fragile Edition)
    This version introduces a try-except block in the summary generation, ensuring
    that the failure of a single indicator's analysis does not halt the entire pipeline.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str):
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input DataFrame cannot be empty.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe
        
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator, 'ichimoku': IchimokuIndicator,
            'adx': AdxIndicator, 'supertrend': SuperTrendIndicator, 'obv': ObvIndicator, 'stochastic': StochasticIndicator,
            'cci': CciIndicator, 'mfi': MfiIndicator, 'atr': AtrIndicator, 'patterns': PatternIndicator,
            'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator, 'structure': StructureIndicator,
            'whales': WhaleIndicator, 'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator,
            'chandelier_exit': ChandelierExitIndicator, 'donchian_channel': DonchianChannelIndicator,
            'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator,
            'keltner_channel': KeltnerChannelIndicator,
            'zigzag': ZigzagIndicator, 'fibonacci': FibonacciIndicator,
        }
        
        self._calculation_order = self._resolve_dependencies()
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = None

    def _resolve_dependencies(self) -> List[str]:
        nodes = {name for name, params in self.config.items() if params.get('enabled', False)}
        in_degree = {node: 0 for node in nodes}
        adj = {node: [] for node in nodes}
        for name in nodes:
            indicator_class = self._indicator_classes.get(name)
            if not indicator_class:
                logger.warning(f"Indicator '{name}' from config not found in _indicator_classes dict. Skipping.")
                continue
            for dep in indicator_class.dependencies:
                if dep in nodes:
                    adj[dep].append(name)
                    in_degree[name] += 1
        queue = deque([node for node in nodes if in_degree[node] == 0])
        sorted_order = []
        while queue:
            node = queue.popleft()
            sorted_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(sorted_order) != len(nodes):
            cycles = {n for n in nodes if in_degree[n] > 0}
            raise ValueError(f"Circular dependency detected in indicators: {cycles}")
        logger.info(f"Resolved calculation order for {self.timeframe}: {sorted_order}")
        return sorted_order

    def calculate_all(self) -> 'IndicatorAnalyzer':
        logger.info(f"Starting calculations for timeframe: {self.timeframe}")
        if self.timeframe:
            rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
            df_for_calc = self.base_df.resample(self.timeframe, label='right', closed='right').apply(rules).dropna()
        else:
            df_for_calc = self.base_df.copy()
        for name in self._calculation_order:
            params = self.config.get(name, {})
            if params.get('enabled', False):
                try:
                    instance_params = {k:v for k,v in params.items() if k != 'enabled'}
                    instance_params['timeframe'] = self.timeframe
                    instance = self._indicator_classes[name](df_for_calc, params=instance_params).calculate()
                    df_for_calc = instance.df
                    self._indicator_instances[name] = instance
                except Exception as e:
                    logger.error(f"Failed to calculate indicator '{name}' on {self.timeframe}: {e}", exc_info=True)
        if self.timeframe:
            self.final_df = self.base_df.copy()
            indicator_cols = [col for col in df_for_calc.columns if col not in self.base_df.columns]
            resampled_results = df_for_calc[indicator_cols]
            mapped_results = resampled_results.reindex(self.base_df.index, method='ffill')
            self.final_df[mapped_results.columns] = mapped_results
        else:
            self.final_df = df_for_calc.copy()
        logger.info(f"Calculations for timeframe {self.timeframe} are complete.")
        return self
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """ Analyzes all indicators and includes a data health report. """
        if self.final_df is None or len(self.final_df) < 2: return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK"}
        try:
            last_closed_candle = self.final_df.iloc[-2]
            summary['price_data'] = {
                'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 
                'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 
                'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name)
            }
        except IndexError:
            return {"status": "Insufficient Data after resampling"}
            
        for name in self._calculation_order:
            if name in self._indicator_instances:
                instance = self._indicator_instances[name]
                instance.df = self.final_df 
                try:
                    # ✅ FIX: This block is now wrapped in a try-except
                    analysis = instance.analyze()
                    # Only add to summary if analysis is not None and doesn't contain an error status
                    if analysis and analysis.get("status") != "Insufficient Data":
                        summary[name] = analysis
                    else:
                        summary[name] = {"status": "Analysis Failed or No Data", "analysis": {}}
                except Exception as e:
                    logger.error(f"CRITICAL: Failed to .analyze() indicator '{name}' on timeframe '{self.timeframe}': {e}", exc_info=True)
                    summary[name] = {"status": f"Analysis Error: {e}", "analysis": {}}
        return summary
