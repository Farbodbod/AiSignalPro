# engines/indicator_analyzer.py (v18.0 - Final Bug Fix)

import pandas as pd
import logging
import json
import asyncio
import inspect
from typing import Dict, Any, Type, List, Optional, Tuple
from collections import deque
from .indicators import *

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    """Creates a unique, stable, and hashable key from parameters."""
    try:
        filtered_params = {
            k: v
            for k, v in params.items()
            if k not in ["enabled", "dependencies", "name"]
        }
        if not filtered_params:
            return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(",", ":"))
        return f"{name}_{param_str}"
    except TypeError as e:
        logger.error(f"Could not serialize params for {name}: {e}")
        param_str = "_".join(
            f"{k}_{v}"
            for k, v in sorted(params.items())
            if k not in ["enabled", "dependencies", "name"]
        )
        return f"{name}_{param_str}" if param_str else name


class IndicatorAnalyzer:
    """
    The Self-Aware Analysis Engine for AiSignalPro (v18.0 - Final Edition)
    ------------------------------------------------------------------------------------------
    This version includes the final fix for the core dependency resolution bug.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        config: Dict[str, Any],
        strategies_config: Dict[str, Any],
        timeframe: str,
        previous_df: Optional[pd.DataFrame] = None,
    ):
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Input must be a pandas DataFrame.")
        self.base_df = df
        self.previous_df = previous_df
        self.indicators_config = config
        self.strategies_config = strategies_config
        self.timeframe = timeframe
        self.recalc_buffer = 250

        self._indicator_classes: Dict[str, Type[BaseIndicator]] = {
            "rsi": RsiIndicator,
            "macd": MacdIndicator,
            "bollinger": BollingerIndicator,
            "ichimoku": IchimokuIndicator,
            "adx": AdxIndicator,
            "supertrend": SuperTrendIndicator,
            "obv": ObvIndicator,
            "stochastic": StochasticIndicator,
            "cci": CciIndicator,
            "mfi": MfiIndicator,
            "atr": AtrIndicator,
            "patterns": PatternIndicator,
            "divergence": DivergenceIndicator,
            "pivots": PivotPointIndicator,
            "structure": StructureIndicator,
            "whales": WhaleIndicator,
            "ema_cross": EMACrossIndicator,
            "vwap_bands": VwapBandsIndicator,
            "chandelier_exit": ChandelierExitIndicator,
            "donchian_channel": DonchianChannelIndicator,
            "fast_ma": FastMAIndicator,
            "williams_r": WilliamsRIndicator,
            "keltner_channel": KeltnerChannelIndicator,
            "zigzag": ZigzagIndicator,
            "fibonacci": FibonacciIndicator,
        }

        self._indicator_configs: Dict[str, Dict[str, Any]] = {}
        self._indicator_instances: Dict[str, BaseIndicator] = {}
        self.adj: Dict[str, List[str]] = {}  # ✅ FIX: Defined as class attributes
        self.in_degree: Dict[str, int] = {}  # ✅ FIX: Defined as class attributes
        self._calculation_order: List[str] = self._resolve_dependencies()
        self.final_df: Optional[pd.DataFrame] = None

    def _resolve_dependencies(self) -> List[str]:
        def discover_nodes(ind_name: str, params: Dict[str, Any]):
            key = get_indicator_config_key(ind_name, params)
            if key in self._indicator_configs:
                return
            self._indicator_configs[key] = {"name": ind_name, "params": params}
            self.adj[key], self.in_degree[key] = [], 0  # ✅ FIX: Use self.adj and self.in_degree
            for dep_name, dep_params in (params.get("dependencies") or {}).items():
                discover_nodes(dep_name, dep_params)
                dep_key = get_indicator_config_key(dep_name, dep_params)
                self.adj[dep_key].append(key)
                self.in_degree[key] += 1

        for name, params in self.indicators_config.items():
            if params.get("enabled", False):
                discover_nodes(name, params)

        for strat_name, strat_params in self.strategies_config.items():
            if strat_params.get("enabled", False):
                indicator_orders = {
                    **strat_params.get("default_params", {}).get("indicator_configs", {}),
                    **strat_params.get("indicator_configs", {}),
                }
                for alias, order in indicator_orders.items():
                    discover_nodes(order["name"], order["params"])

        queue = deque([k for k, deg in self.in_degree.items() if deg == 0])
        sorted_order: List[str] = []
        while queue:
            key = queue.popleft()
            sorted_order.append(key)
            for neighbor in self.adj.get(key, []):
                self.in_degree[neighbor] -= 1
                if self.in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(self._indicator_configs):
            raise ValueError(
                f"Circular dependency in {self.timeframe}: {set(self._indicator_configs) - set(sorted_order)}"
            )
        return sorted_order

    async def _calculate_and_store(self, key: str, base_df: pd.DataFrame) -> None:
        """Helper to run a single indicator task and store the result."""
        config = self._indicator_configs[key]
        name, params = config["name"], config["params"]
        cls = self._indicator_classes.get(name)
        if not cls:
            logger.warning(f"Indicator class not found for key: {key}")
            return

        dependencies = {}
        dep_configs = params.get("dependencies", {})
        for dep_name, dep_params in dep_configs.items():
            dep_key = get_indicator_config_key(dep_name, dep_params)
            dep_instance = self._indicator_instances.get(dep_key)
            
            if not isinstance(dep_instance, BaseIndicator):
                logger.error(
                    f"Dependency '{dep_name}' for '{name}' failed to calculate or is missing. Aborting calculation for '{name}'."
                )
                self._indicator_instances[key] = None
                return

            dependencies[dep_name] = dep_instance

        try:
            instance_params = {**params, "timeframe": self.timeframe}
            instance = cls(
                df=base_df.copy(), params=instance_params, dependencies=dependencies
            ).calculate()
            self._indicator_instances[key] = instance
        except Exception as e:
            logger.error(
                f"Indicator calculation for '{key}' failed: {e}", exc_info=True
            )
            self._indicator_instances[key] = None

    async def calculate_all(self) -> "IndicatorAnalyzer":
        df_for_calc = self.base_df.copy()
        if self.previous_df is not None and not self.previous_df.empty:
            if df_for_calc.index.tz is None and self.previous_df.index.tz is not None:
                df_for_calc.index = df_for_calc.index.tz_localize(self.previous_df.index.tz)
            elif df_for_calc.index.tz is not None and self.previous_df.index.tz is None:
                self.previous_df.index = self.previous_df.index.tz_localize(df_for_calc.index.tz)

            df_for_calc = pd.concat([self.previous_df, df_for_calc])
            df_for_calc = df_for_calc.sort_index()
            df_for_calc = df_for_calc[~df_for_calc.index.duplicated(keep="last")]
        
        logger.debug(
            f"Starting Sequential DI Calculations on {self.timeframe} with {len(self._calculation_order)} tasks."
        )
        
        # Parallel execution of independent indicators at each level.
        current_level_keys = deque([k for k, deg in self.in_degree.items() if deg == 0])
        processed_keys = set()
        
        while current_level_keys:
            tasks = [self._calculate_and_store(key, df_for_calc) for key in current_level_keys]
            await asyncio.gather(*tasks)
            
            processed_keys.update(current_level_keys)
            next_level_keys = deque()
            for key in current_level_keys:
                if key in self.adj:
                    for neighbor_key in self.adj[key]:
                        if neighbor_key not in processed_keys:
                            self.in_degree[neighbor_key] -= 1
                            if self.in_degree[neighbor_key] == 0:
                                next_level_keys.append(neighbor_key)
            current_level_keys = next_level_keys
            
        self.final_df = df_for_calc
        success_count = sum(
            1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator)
        )
        failed_count = len(self._calculation_order) - success_count
        logger.info(
            f"DI Calculations complete on {self.timeframe}: success={success_count}, failed={failed_count}"
        )
        return self

    async def get_analysis_summary(self) -> Dict[str, Any]:
        if self.final_df is None:
            return {"status": "Calculation Not Run"}
        if len(self.final_df) < 2:
            return {"status": "Insufficient Data"}

        summary: Dict[str, Any] = {"status": "OK", "final_df": self.final_df.tail(self.recalc_buffer + 50)}
        try:
            summary["price_data"] = {
                "open": self.final_df.iloc[-2]["open"],
                "high": self.final_df.iloc[-2]["high"],
                "low": self.final_df.iloc[-2]["low"],
                "close": self.final_df.iloc[-2]["close"],
                "volume": self.final_df.iloc[-2]["volume"],
                "timestamp": str(self.final_df.index[-2]),
            }
        except IndexError:
            return {"status": "Insufficient Data after calculations"}

        successful_analysis_count = 0
        total_calculated_instances = sum(
            1 for v in self._indicator_instances.values() if isinstance(v, BaseIndicator)
        )

        for unique_key, instance in self._indicator_instances.items():
            if not isinstance(instance, BaseIndicator):
                logger.warning(f"Skipping analysis for '{unique_key}' due to failed calculation.")
                summary[unique_key] = {"status": "Dependency Calculation Failed"}
                continue
            try:
                analyze_method = getattr(instance, "analyze", None)
                analysis = None
                if analyze_method:
                    if inspect.iscoroutinefunction(analyze_method):
                        analysis = await analyze_method()
                    else:
                        analysis = analyze_method()
                else:
                    analysis = {"status": "No analyze() method found"}

                if analysis and analysis.get("status") == "OK":
                    successful_analysis_count += 1

                summary[unique_key] = analysis

            except Exception as e:
                logger.error(
                    f"Analysis CRASH during aggregation for '{unique_key}': {e}", exc_info=True
                )
                summary[unique_key] = {"status": f"Analysis Error: {e}"}

        failed_or_no_result_count = total_calculated_instances - successful_analysis_count
        logger.info(
            f"Analysis aggregation complete on {self.timeframe}: success={successful_analysis_count}, no_result={failed_or_no_result_count}"
        )
        return summary
