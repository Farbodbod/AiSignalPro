import pandas as pd
import logging
from typing import Dict, Any, Type, List, Optional
from collections import deque

from .indicators import *

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    """Creates a unique, hashable key for an indicator and its specific parameters."""
    # Exclude non-essential keys and sort for consistency to create a stable key
    param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies'])
    return f"{name}_{param_str}" if param_str else name

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v9.0 - Multi-Version Engine)
    This world-class version features a true multi-version dependency management
    system. It can calculate and manage multiple instances of the same indicator
    with different parameters (e.g., ATR(10) and ATR(14)) in a single run,
    permanently solving the "wrong brick" problem.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], timeframe: str, previous_df: Optional[pd.DataFrame] = None):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")
        
        self.base_df = df
        self.config = config
        self.timeframe = timeframe
        self.previous_df = previous_df
        self.recalc_buffer = 250
        
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
        
        # ✅ MIRACLE UPGRADE: These now handle unique indicator versions, not just names
        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._calculation_order: List[str] = self._resolve_dependencies()
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = None

    def _resolve_dependencies(self) -> List[str]:
        """ ✅ Upgraded: Resolves dependencies for multiple versions of the same indicator. """
        adj: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}
        
        # Recursive function to discover all required indicator versions from the config
        def discover_nodes(indicator_name: str, params: Dict[str, Any]):
            unique_key = get_indicator_config_key(indicator_name, params)
            if unique_key in self._indicator_configs:
                return # Already discovered, no need to process again

            # Store the config for this unique version and initialize its graph nodes
            self._indicator_configs[unique_key] = {'name': indicator_name, 'params': params}
            adj[unique_key] = []
            in_degree[unique_key] = 0
            
            # Now, recursively discover the dependencies of this indicator
            dep_configs = params.get('dependencies', {})
            for dep_name, dep_params in dep_configs.items():
                discover_nodes(dep_name, dep_params)
                
                # Add a directed edge from the dependency to the current indicator
                dep_key = get_indicator_config_key(dep_name, dep_params)
                adj[dep_key].append(unique_key)
                in_degree[unique_key] += 1

        # Start the discovery process from the top-level enabled indicators in the main config
        for name, params in self.config.items():
            if params.get('enabled', False):
                discover_nodes(name, params)

        # Perform the topological sort on the completed graph
        queue = deque([key for key, degree in in_degree.items() if degree == 0])
        sorted_order = []
        while queue:
            key = queue.popleft()
            sorted_order.append(key)
            if key in adj:
                for neighbor in adj[key]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(sorted_order) != len(self._indicator_configs):
            raise ValueError("A circular dependency was detected in the indicator configurations. Please check your config.")
            
        logger.info(f"Resolved multi-version calculation order: {sorted_order}")
        return sorted_order

    def calculate_all(self) -> 'IndicatorAnalyzer':
        """ ✅ Upgraded: Calculates all unique versions of required indicators in the correct order. """
        if self.previous_df is not None and not self.previous_df.empty:
            logger.debug("Previous state found. Performing incremental calculation.")
            combined_df = pd.concat([self.previous_df, self.base_df])
            df_for_calc = combined_df[~combined_df.index.duplicated(keep='last')].sort_index()
        else:
            logger.debug("No previous state. Performing full calculation.")
            df_for_calc = self.base_df.copy()

        # Loop through the unique indicator versions in the topologically sorted order
        for unique_key in self._calculation_order:
            config = self._indicator_configs[unique_key]
            name = config['name']
            params = config['params']
            
            try:
                instance_params = {**params, 'timeframe': self.timeframe}
                indicator_class = self._indicator_classes[name]
                
                logger.debug(f"Calculating indicator version: '{unique_key}'")
                instance = indicator_class(df_for_calc, params=instance_params).calculate()
                
                df_for_calc = instance.df
                self._indicator_instances[unique_key] = instance
            except Exception as e:
                logger.error(f"Failed to calculate indicator version '{unique_key}': {e}", exc_info=True)
        
        self.final_df = df_for_calc
        logger.info(f"Calculations for timeframe {self.timeframe} complete. Final DF has {len(self.final_df)} rows.")
        return self

    def get_analysis_summary(self) -> Dict[str, Any]:
        """ ✅ Upgraded: Creates a summary mapping simple names to their primary versions for strategies. """
        if self.final_df is None or len(self.final_df) < 2: 
            return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            last_closed_candle = self.final_df.iloc[-2]
            summary['price_data'] = {'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name)}
        except IndexError:
            return {"status": "Insufficient Data after calculations"}
            
        # Analyze all calculated instances and build the final summary package
        for unique_key, instance in self._indicator_instances.items():
            try:
                analysis = instance.analyze()
                if analysis and analysis.get("status") == "OK":
                    # For strategies, we map the top-level indicators back to their simple names
                    # e.g., 'supertrend_period_10...' becomes accessible as 'supertrend'
                    simple_name = self._indicator_configs[unique_key]['name']
                    if self.config.get(simple_name, {}).get('enabled'):
                         summary[simple_name] = analysis
                else:
                    summary[simple_name] = {"status": "Analysis Failed or No Data", "analysis": {}}
            except Exception as e:
                logger.error(f"Failed to analyze indicator version '{unique_key}': {e}", exc_info=True)
                summary[unique_key] = {"status": f"Analysis Error: {e}"}
        return summary

