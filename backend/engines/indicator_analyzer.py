# engines/indicator_analyzer.py (v12.0 - Ultimate Transparency Edition)

import pandas as pd
import logging
import time
import json
from typing import Dict, Any, Type, List, Optional, Set
from collections import deque

from .indicators import *

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    """Creates a unique, stable, and hashable key from parameters, immune to type/order issues."""
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params:
            return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not create a stable key for indicator '{name}' due to un-serializable params. Error: {e}")
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v12.0 - Ultimate Transparency Edition)
    ------------------------------------------------------------------------------------------
    This version enhances logging to differentiate between standard indicators and
    custom variations requested by strategies, providing ultimate clarity on calculation counts.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], strategies_config: Dict[str, Any], timeframe: str, previous_df: Optional[pd.DataFrame] = None):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")
        
        self.base_df = df
        self.indicators_config = config
        self.strategies_config = strategies_config
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
        
        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._calculation_status: Dict[str, bool] = {}
        # ✅ NEW: A set to track which indicator keys are "standard" vs. "special requests"
        self._standard_indicator_keys: Set[str] = set()
        self._calculation_order: List[str] = self._resolve_dependencies()
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.final_df = None

    def _resolve_dependencies(self) -> List[str]:
        adj: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}
        
        def discover_nodes(indicator_name: str, params: Dict[str, Any]):
            unique_key = get_indicator_config_key(indicator_name, params)
            if unique_key in self._indicator_configs: return
            self._indicator_configs[unique_key] = {'name': indicator_name, 'params': params}
            adj[unique_key] = []
            in_degree[unique_key] = 0
            dep_configs = params.get('dependencies', {})
            for dep_name, dep_params in dep_configs.items():
                discover_nodes(dep_name, dep_params)
                dep_key = get_indicator_config_key(dep_name, dep_params)
                adj[dep_key].append(unique_key)
                in_degree[unique_key] += 1

        # Discover all "standard" indicators from the main config first
        for name, params in self.indicators_config.items():
            if params.get('enabled', False): discover_nodes(name, params)
        
        # ✅ NEW: Store the keys of all standard indicators discovered so far
        self._standard_indicator_keys = set(self._indicator_configs.keys())

        # Now, discover any additional "special request" indicators from strategies
        for strat_name, strat_params in self.strategies_config.items():
            if strat_params.get('enabled', False):
                indicator_orders = {**strat_params.get('default_params', {}).get('indicator_configs', {}), **strat_params.get('indicator_configs', {})}
                for alias, order in indicator_orders.items():
                    discover_nodes(order['name'], order['params'])

        # Topological sort remains the same
        queue = deque([key for key, degree in in_degree.items() if degree == 0])
        sorted_order = []
        while queue:
            key = queue.popleft()
            sorted_order.append(key)
            if key in adj:
                for neighbor in adj[key]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0: queue.append(neighbor)

        if len(sorted_order) != len(self._indicator_configs):
            raise ValueError(f"Circular dependency detected in indicator configurations for {self.timeframe}. Process halted.")
        return sorted_order

    def calculate_all(self) -> 'IndicatorAnalyzer':
        if self.previous_df is not None and not self.previous_df.empty:
            combined_df = pd.concat([self.previous_df, self.base_df])
            df_for_calc = combined_df[~combined_df.index.duplicated(keep='last')].sort_index()
        else:
            df_for_calc = self.base_df.copy()

        logger.info(f"--- Starting Calculations for {self.timeframe} ({len(self._calculation_order)} tasks) ---")
        
        # ✅ REFACTOR: Store unique_key for a more accurate success count
        success_keys, failed_keys, skipped_keys = [], [], []

        for unique_key in self._calculation_order:
            config = self._indicator_configs[unique_key]
            name, params = config['name'], config['params']
            
            # Dependency check logic is unchanged
            dependencies_ok = True
            failed_dependency = ""
            dep_configs = params.get('dependencies', {})
            for dep_name, dep_params in dep_configs.items():
                dep_key = get_indicator_config_key(dep_name, dep_params)
                if not self._calculation_status.get(dep_key, False):
                    dependencies_ok = False
                    failed_dependency = dep_key
                    break
            
            if not dependencies_ok:
                self._calculation_status[unique_key] = False
                skipped_keys.append(f"{unique_key}(dep:{failed_dependency})")
                continue
            
            try:
                instance_params = {**params, 'timeframe': self.timeframe}
                instance = self._indicator_classes[name](df_for_calc, params=instance_params).calculate()
                df_for_calc = instance.df
                self._indicator_instances[unique_key] = instance
                self._calculation_status[unique_key] = True
                success_keys.append(unique_key) # Store the full unique key
            except Exception as e:
                self._calculation_status[unique_key] = False
                failed_keys.append(f"{unique_key}({e})")
        
        self.final_df = df_for_calc
        
        # ✅ REFACTOR: Log the count of successful TASKS
        if success_keys:
            logger.info(f"✅ [Calc OK] {len(success_keys)} indicator tasks completed for {self.timeframe}.")
        if skipped_keys:
            logger.warning(f"⏭️ [Calc SKIPPED] {len(skipped_keys)} indicator tasks for {self.timeframe}: {', '.join(skipped_keys)}")
        if failed_keys:
            logger.error(f"❌ [Calc FAIL] {len(failed_keys)} indicator tasks for {self.timeframe}: {', '.join(failed_keys)}")
            
        return self

    def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None or len(self.final_df) < 2: 
            return {"status": "Insufficient Data"}
        
        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            last_closed_candle = self.final_df.iloc[-2]
            summary['price_data'] = { 'open': last_closed_candle.get('open'), 'high': last_closed_candle.get('high'), 'low': last_closed_candle.get('low'), 'close': last_closed_candle.get('close'), 'volume': last_closed_candle.get('volume'), 'timestamp': str(last_closed_candle.name) }
        except IndexError:
            return {"status": "Insufficient Data after calculations"}
        
        logger.info(f"--- Starting Analysis for {self.timeframe} ({len(self._indicator_instances)} tasks) ---")
        
        success_keys, warning_keys, error_keys, skipped_keys = [], [], []
        # ✅ NEW: A list to hold the names of successfully analyzed special requests
        special_request_success_keys = []

        for unique_key, instance in self._indicator_instances.items():
            simple_name = self._indicator_configs[unique_key]['name']

            if not self._calculation_status.get(unique_key, False):
                skipped_keys.append(simple_name)
                continue

            try:
                analysis = instance.analyze()
                is_globally_enabled = self.indicators_config.get(simple_name, {}).get('enabled')
                
                if analysis and analysis.get("status") == "OK":
                    success_keys.append(simple_name)
                    summary[unique_key] = analysis
                    if is_globally_enabled:
                         summary[simple_name] = analysis
                    
                    # ✅ NEW: Check if this was a special request and log it
                    if unique_key not in self._standard_indicator_keys:
                        special_request_success_keys.append(unique_key)
                else:
                    status_msg = analysis.get('status', 'No Data') if analysis else 'None'
                    warning_keys.append(f"{simple_name}({status_msg})")
                    if is_globally_enabled:
                        summary[simple_name] = {"status": "Analysis Failed or No Data"}
            except Exception as e:
                error_keys.append(f"{simple_name}({e})")
                summary[unique_key] = {"status": f"Analysis Error: {e}"}
        
        # ✅ REFACTOR: Log summaries with the new special request note
        unique_success = sorted(list(set(success_keys)))
        if unique_success:
            logger.info(f"✅ [Analysis OK] {len(unique_success)} unique indicators analyzed for {self.timeframe}: {', '.join(unique_success)}")
        
        # ✅ NEW: Add the clarifying note about special requests
        if special_request_success_keys:
            logger.info(f"💡 [Analysis NOTE] {len(special_request_success_keys)} additional custom indicator variations were also analyzed for specific strategies: {', '.join(special_request_success_keys)}")

        if skipped_keys:
            logger.info(f"⏭️ [Analysis SKIPPED] {len(set(skipped_keys))} unique indicators for {self.timeframe} (due to calc failure).")
        if warning_keys:
            logger.warning(f"⚠️ [Analysis WARN] {len(warning_keys)} indicators for {self.timeframe} had issues: {', '.join(warning_keys)}")
        if error_keys:
            logger.error(f"❌ [Analysis CRASH] {len(error_keys)} indicators for {self.timeframe}: {', '.join(error_keys)}")
            
        return summary
