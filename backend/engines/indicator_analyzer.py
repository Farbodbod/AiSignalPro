#backend/engines/indicator_analyzer.py
import pandas as pd
import logging
import json
import asyncio
import inspect
from typing import Dict, Any, Type, List, Optional, Tuple
from collections import deque
from copy import deepcopy
from .indicators import *
from .strategies import BaseStrategy

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ["enabled", "dependencies", "name"]}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not serialize params for {name}: {e}")
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ["enabled", "dependencies", "name"])
        return f"{name}_{param_str}" if param_str else name

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges dict2 into dict1."""
    result = deepcopy(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v18.1 - The Deep Merge Restoration)
    ------------------------------------------------------------------------------------------
    This version includes a critical, definitive fix for the dependency resolution
    logic. The engine now uses a 'deep_merge' operation when combining global and
    strategy-specific indicator parameters. This permanently fixes the "Parameter
    Inheritance Failure" bug for nested parameters like 'dependencies', restoring
    full functionality and ensuring all indicators are calculated correctly.
    """
    def __init__(self, df: pd.DataFrame, config: Dict[str, Any], strategies_config: Dict[str, Any], 
                 strategy_classes: List[Type[BaseStrategy]],
                 timeframe: str, symbol: str, previous_df: Optional[pd.DataFrame] = None):
        if not isinstance(df, pd.DataFrame): raise ValueError("Input must be a pandas DataFrame.")
        self.base_df, self.previous_df, self.indicators_config, self.strategies_config = df, previous_df, config, strategies_config
        self.strategy_classes = strategy_classes
        self.timeframe, self.symbol, self.recalc_buffer = timeframe, symbol, 250
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = { 
            'rsi': RsiIndicator, 'macd': MacdIndicator, 'bollinger': BollingerIndicator, 'ichimoku': IchimokuIndicator, 'adx': AdxIndicator, 
            'supertrend': SuperTrendIndicator, 'obv': ObvIndicator, 'stochastic': StochasticIndicator, 'cci': CciIndicator, 'mfi': MfiIndicator, 
            'atr': AtrIndicator, 'patterns': PatternIndicator, 'divergence': DivergenceIndicator, 'pivots': PivotPointIndicator, 'structure': StructureIndicator, 
            'whales': WhaleIndicator, 'ema_cross': EMACrossIndicator, 'vwap_bands': VwapBandsIndicator, 'chandelier_exit': ChandelierExitIndicator, 
            'donchian_channel': DonchianChannelIndicator, 'fast_ma': FastMAIndicator, 'williams_r': WilliamsRIndicator, 'keltner_channel': KeltnerChannelIndicator, 
            'zigzag': ZigzagIndicator, 'fibonacci': FibonacciIndicator, 'volume': VolumeIndicator,
        }
        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self._calculation_order: List[str] = self._resolve_dependencies()
        self.final_df: Optional[pd.DataFrame] = None

    def _resolve_dependencies(self) -> List[str]:
        adj, in_degree = {}, {}
        def discover_nodes(ind_name: str, params: Dict[str, Any]):
            core_params = {k: v for k, v in params.items() if k not in ["enabled", "dependencies", "name"]}
            key = get_indicator_config_key(ind_name, core_params)
            
            if key in self._indicator_configs: return
            
            self._indicator_configs[key] = {'name': ind_name, 'params': params}
            adj[key], in_degree[key] = [], 0
            
            for dep_name, dep_params in (params.get("dependencies") or {}).items():
                full_dep_config = self.indicators_config.get(dep_name, {})
                final_dep_params = deep_merge(full_dep_config, dep_params) # Use deep_merge for dependencies
                discover_nodes(dep_name, final_dep_params)
                
                dep_core_params = {k: v for k, v in final_dep_params.items() if k not in ["enabled", "dependencies", "name"]}
                dep_key = get_indicator_config_key(dep_name, dep_core_params)
                
                adj[dep_key].append(key)
                in_degree[key] += 1
        
        # --- Discovery Phase ---
        # 1. Discover from main indicators config (Global Defaults)
        for name, params in self.indicators_config.items():
            if params.get("enabled", False): discover_nodes(name, params)
        
        # 2. Discover from user-defined strategy configs (Custom Overrides)
        for strat_name, strat_params in self.strategies_config.items():
            if strat_params.get("enabled", False):
                indicator_orders = {**strat_params.get("default_params", {}).get("indicator_configs", {}), **strat_params.get("indicator_configs", {})}
                
                # --- DEFINITIVE FIX v18.1: USE DEEP MERGE FOR PARAMETER INHERITANCE ---
                for alias, order in indicator_orders.items():
                    indicator_name = order["name"]
                    custom_params = order.get("params", {})
                    base_params = self.indicators_config.get(indicator_name, {})
                    
                    # Use deep_merge to correctly handle nested parameters like 'dependencies'
                    final_params = deep_merge(base_params, custom_params)
                    
                    discover_nodes(indicator_name, final_params)
                # --- END OF FIX ---
        
        # 3. Discover from strategy class default_configs (Implicit Dependencies)
        for strat_class in self.strategy_classes:
            default_cfg = getattr(strat_class, 'default_config', {})
            if default_cfg.get('htf_confirmation_enabled'):
                htf_rules = default_cfg.get('htf_confirmations', {})
                for rule_name in htf_rules:
                    if rule_name != 'min_required_score':
                        indicator_params_from_config = self.indicators_config.get(rule_name, {})
                        discover_nodes(rule_name, indicator_params_from_config)
        
        # --- Sorting Phase (Topological Sort) ---
        queue = deque([k for k, deg in in_degree.items() if deg == 0]); sorted_order: List[str] = []
        while queue:
            key = queue.popleft(); sorted_order.append(key)
            for neighbor in adj.get(key, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0: queue.append(neighbor)
        if len(sorted_order) != len(self._indicator_configs):
            failed_nodes = set(self._indicator_configs) - set(sorted_order)
            logger.error(f"Circular dependency or unresolved node in {self.symbol}@{self.timeframe}: {failed_nodes}")
            raise ValueError(f"Circular dependency detected in indicator graph.")
        return sorted_order

    async def _calculate_and_store(self, key: str, base_df: pd.DataFrame) -> None:
        config = self._indicator_configs[key]; name, params_block = config["name"], config["params"]
        cls = self._indicator_classes.get(name)
        if not cls: logger.warning(f"Indicator class not found for key '{key}'"); return
        try:
            instance_params = {**params_block, "timeframe": self.timeframe, "symbol": self.symbol}
            instance = cls(df=base_df.copy(), params=instance_params, dependencies=self._indicator_instances).calculate()
            self._indicator_instances[key] = instance
        except Exception as e:
            logger.error(f"Indicator calculation CRASHED for key '{key}' on {self.symbol}@{self.timeframe}: {e}", exc_info=True)
            self._indicator_instances[key] = e 

    async def calculate_all(self) -> "IndicatorAnalyzer":
        df_for_calc = self.base_df.copy()
        if self.previous_df is not None and not self.previous_df.empty:
            df_for_calc = pd.concat([self.previous_df, df_for_calc])
            df_for_calc = df_for_calc.sort_index(); df_for_calc = df_for_calc[~df_for_calc.index.duplicated(keep="last")]
            
        logger.info(f"--- Starting DI Calculations for {self.symbol}@{self.timeframe} ({len(self._calculation_order)} tasks) ---")
        for key in self._calculation_order:
            await self._calculate_and_store(key, df_for_calc)
        self.final_df = df_for_calc

        success_count = sum(1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator))
        failed_count = len(self._calculation_order) - success_count
        if failed_count > 0:
            failed_keys = [key for key, instance in self._indicator_instances.items() if not isinstance(instance, BaseIndicator)]
            failed_names = [self._indicator_configs.get(key, {}).get('name', key) for key in failed_keys]
            logger.warning(f"⚠️ DI Calculations for {self.symbol}@{self.timeframe}: {success_count} succeeded, {failed_count} FAILED. Failed indicators: [{', '.join(failed_names)}]")
        else:
            logger.info(f"✅ DI Calculations complete for {self.symbol}@{self.timeframe}: {success_count} succeeded, {failed_count} failed.")
        if self.final_df is not None: 
            logger.info(f"📊 Final stateful DF for {self.symbol}@{self.timeframe} now contains {len(self.final_df)} rows.")
        return self

    async def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None: return {"status": "Calculation Not Run"}
        if len(self.final_df) < 2: return {"status": "Insufficient Data"}
        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            last_closed = self.final_df.iloc[-1]
            summary["price_data"] = {"open": last_closed["open"], "high": last_closed["high"], "low": last_closed["low"], "close": last_closed["close"], "volume": last_closed["volume"], "timestamp": str(last_closed.name),}
        except IndexError:
            return {"status": "Insufficient Data after calculations"}
        
        indicator_map = {}
        for unique_key, config in self._indicator_configs.items():
            simple_name = config['name']
            if simple_name in self.indicators_config: indicator_map[simple_name] = unique_key
        summary["_indicator_map"] = indicator_map

        total_calculated_instances = sum(1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator))
        logger.info(f"--- Starting Analysis Aggregation for {self.symbol}@{self.timeframe} ({total_calculated_instances} successful instances) ---")
        analysis_failures = []
        for unique_key, instance in self._indicator_instances.items():
            if not isinstance(instance, BaseIndicator): summary[unique_key] = {"status": "Calculation Failed"}; continue
            try:
                analyze_method = getattr(instance, "analyze", None)
                analysis = await analyze_method() if inspect.iscoroutinefunction(analyze_method) else analyze_method() if analyze_method else {"status": "No analyze() method found"}
                summary[unique_key] = analysis
                if not analysis or analysis.get("status") != "OK":
                    indicator_name = self._indicator_configs.get(unique_key, {}).get('name', unique_key)
                    status_reason = analysis.get("status", "Unknown Error")
                    analysis_failures.append(f"{indicator_name}({status_reason})")
            except Exception as e:
                logger.error(f"Analysis CRASH during aggregation for '{unique_key}': {e}", exc_info=True); summary[unique_key] = {"status": f"Analysis Error: {e}"}
        
        successful_analysis_count = total_calculated_instances - len(analysis_failures)
        logger.info(f"✅ Analysis aggregation phase for {self.symbol}@{self.timeframe} complete.")
        if analysis_failures:
            logger.warning(f"📊 Analysis Summary for {self.symbol}@{self.timeframe}: {successful_analysis_count} succeeded, {len(analysis_failures)} HAD NO RESULT. Details: [{', '.join(analysis_failures)}]")
        else:
            logger.info(f"📊 Analysis Summary for {self.symbol}@{self.timeframe}: All {successful_analysis_count} analyses succeeded.")
        return summary
