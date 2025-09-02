from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ClassVar, Tuple
import logging
import pandas as pd
import json
from copy import deepcopy

logger = logging.getLogger(__name__)

# --- Helper functions (unchanged) ---
def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict): result[k] = deep_merge(result[k], v)
        else: result[k] = v
    return result

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v15.0 - ADX-Adaptive Targeting Engine)
    ---------------------------------------------------------------------------------------------
    This major upgrade integrates a quantum leap in risk management intelligence.
    The framework now natively supports ADX-Adaptive Targeting, allowing any
    strategy to define dynamic take-profit levels that adapt to the real-time
    strength of the market trend.

    🚀 New in v15.0:
    1.  **ADX-Adaptive Targeting Engine:** The `_calculate_tp_from_blueprint`
        method can now process a new `tp_logic` type:
        'atr_multiple_by_trend_strength', making profit-taking smarter.
    """
    strategy_name: str = "BaseStrategy"
    default_config: ClassVar[Dict[str, Any]] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis, self.config, self.main_config, self.htf_analysis = primary_analysis, deep_merge(self.default_config, config or {}), main_config, htf_analysis or {}
        self.primary_timeframe, self.symbol, self.price_data, self.df = primary_timeframe, symbol, self.analysis.get('price_data'), self.analysis.get('final_df')
        self.indicator_configs, self.log_details, self.name = self.config.get('indicator_configs', {}), {"criteria_results": [], "indicator_trace": [], "risk_trace": []}, self.config.get('name', self.strategy_name)

    # ... [Logging methods and other helpers remain unchanged] ...
    def _log_criteria(self, criterion_name: str, status: Any, reason: str = ""):
        is_ok = bool(status); focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol");
        if focus_symbol and self.symbol != focus_symbol: return
        self.log_details["criteria_results"].append({"criterion": criterion_name, "status": is_ok, "reason": reason})
        status_emoji = "▶️" if is_ok else "🌕"; logger.info(f"  {status_emoji} Criterion: {self.name} on {self.primary_timeframe} - '{criterion_name}': {is_ok}. Reason: {reason}")
        
    def _log_indicator_trace(self, indicator_name: str, value: Any, status: str = "OK", reason: str = ""):
        self.log_details["indicator_trace"].append({"indicator": indicator_name, "value": str(value), "status": status, "reason": reason});
        logger.debug(f"    [Trace] Indicator: {indicator_name} -> Value: {value}, Status: {status}, Reason: {reason}")

    def _log_final_decision(self, signal: str, reason: str = ""):
        self.log_details["final_signal"], self.log_details["final_reason"] = signal, reason
        focus_symbol = self.main_config.get("general", {}).get("logging_focus_symbol")
        is_focus_symbol = (self.symbol == focus_symbol)
        is_actionable_signal = (signal in ["BUY", "SELL"])
        signal_emoji = "🟩" if signal == "BUY" else "🟥" if signal == "SELL" else "⬜"
        log_message = (f"{signal_emoji} Final Decision: {self.name} on {self.symbol} {self.primary_timeframe} -> "
                       f"Signal: {signal}. Reason: {reason}")
        if is_actionable_signal or is_focus_symbol: logger.info(log_message)
        else: logger.debug(log_message)

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]: pass

    def get_indicator(self, name_or_alias: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        source = analysis_source if analysis_source is not None else self.analysis;
        if not source: return None
        indicator_map = source.get('_indicator_map', {}); indicator_data, unique_key = None, None
        if name_or_alias in self.indicator_configs:
            order = self.indicator_configs[name_or_alias]; unique_key = get_indicator_config_key(order['name'], order.get('params', {}))
        elif name_or_alias in indicator_map: unique_key = indicator_map.get(name_or_alias)
        if not unique_key: self._log_indicator_trace(name_or_alias, None, status="FAILED", reason="Indicator key could not be resolved."); return None
        indicator_data = source.get(unique_key)
        if not indicator_data or not isinstance(indicator_data, dict): self._log_indicator_trace(name_or_alias, None, status="FAILED", reason=f"Missing data object for key: {unique_key}."); return None
        status = indicator_data.get("status", "").lower()
        if "error" in status or "failed" in status: self._log_indicator_trace(name_or_alias, status, status="FAILED", reason=f"Indicator reported failure status: {status}"); return None
        self._log_indicator_trace(name_or_alias, "OK"); return indicator_data
    
    # ... [Universal Toolkit Helpers like _safe_get, etc., remain unchanged] ...
    def _safe_get(self, data: Dict, keys: List[str], default: Any = None) -> Any:
        for key in keys:
            if not isinstance(data, dict): return default
            data = data.get(key)
        return data if data is not None else default

    def _is_valid_number(self, x: Any) -> bool:
        return x is not None and isinstance(x, (int, float))

    def _validate_blueprint(self, blueprint: Dict[str, Any]) -> bool:
        required_keys = ["direction", "entry_price", "sl_logic", "tp_logic"]
        for key in required_keys:
            if key not in blueprint:
                logger.error(f"Blueprint validation failed: Missing key '{key}'.")
                return False
        if not isinstance(blueprint.get('sl_logic'), dict) or not isinstance(blueprint.get('tp_logic'), dict):
            logger.error("Blueprint validation failed: sl_logic or tp_logic is not a dictionary.")
            return False
        return True

    # ... [Other helpers like _get_market_regime, etc., remain unchanged] ...
    def _get_market_regime(self, adx_threshold: float = 25.0) -> Tuple[str, float]:
        adx_data = self.get_indicator('adx')
        if not adx_data or 'values' not in adx_data or not self._is_valid_number((adx_data.get('values') or {}).get('adx')):
            logger.warning(f"Could not determine market regime due to missing/invalid ADX."); return "UNKNOWN", 0.0
        adx_val = (adx_data.get('values') or {}).get('adx', 0.0)
        if adx_val >= adx_threshold: return "TRENDING", adx_val
        else: return "RANGING", adx_val

    # ... [The entire risk management section is presented for context, with the upgrade highlighted] ...

    def _calculate_sl_from_blueprint(self, entry_price: float, direction: str, sl_params: Dict[str, Any]) -> Optional[float]:
        # ... [This method remains unchanged] ...
        sl_type = sl_params.get('type')
        atr_data = self.get_indicator('atr')
        atr_value = (atr_data.get('values') or {}).get('atr') if atr_data else None
        calculated_sl = None
        if sl_type == 'band':
            band_name = sl_params.get('band_name')
            multiplier = sl_params.get('buffer_atr_multiplier', 1.0)
            indicator_data = self.get_indicator('bollinger') # Assuming bollinger for now
            band_value = self._safe_get(indicator_data, ['values', band_name])
            if None in [band_name, band_value, atr_value]: return None
            buffer = atr_value * multiplier
            calculated_sl = band_value - buffer if direction == 'BUY' else band_value + buffer
        # ... [other sl_types] ...
        elif sl_type == 'atr_based':
            multiplier = sl_params.get('atr_multiplier', 1.5)
            if atr_value is None: return None
            calculated_sl = entry_price - (atr_value * multiplier) if direction == 'BUY' else entry_price + (atr_value * multiplier)
        if calculated_sl is not None:
            if (direction == 'BUY' and calculated_sl >= entry_price) or (direction == 'SELL' and calculated_sl <= entry_price):
                logger.error(f"INVERTED STOP-LOSS DETECTED AND BLOCKED! Entry: {entry_price}, Calculated SL: {calculated_sl}, Direction: {direction}.")
                return None
        return calculated_sl

    def _calculate_tp_from_blueprint(self, entry_price: float, stop_loss: float, direction: str, tp_logic: Dict[str, Any]) -> List[float]:
        targets = []
        tp_type = tp_logic.get('type')
        risk_per_unit = abs(entry_price - stop_loss)
        
        if tp_type == 'atr_multiple':
            multiples = tp_logic.get('multiples', [1.5, 3.0, 5.0])
            atr_data = self.get_indicator('atr')
            atr_value = (atr_data.get('values') or {}).get('atr') if atr_data else None
            if not atr_value: return []
            for m in multiples:
                target = entry_price + (atr_value * m) if direction == 'BUY' else entry_price - (atr_value * m)
                targets.append(target)
        
        # --- QUANTUM UPGRADE v15.0: ADX-ADAPTIVE TARGETING ENGINE ---
        elif tp_type == 'atr_multiple_by_trend_strength':
            self._log_indicator_trace("TP_Logic", tp_type, reason="Activating ADX-Adaptive Targeting Engine.")
            
            # 1. Fetch ADX data for trend strength context
            adx_data = self.get_indicator('adx')
            if not adx_data:
                logger.warning(f"ADX-Adaptive TP failed: ADX indicator not available. Defaulting to empty targets.")
                return []
            
            adx_val = self._safe_get(adx_data, ['values', 'adx'], 0.0)
            
            # 2. Safely parse the adaptive configuration from the blueprint
            adx_thresholds = tp_logic.get('adx_thresholds', {})
            strong_thresh = adx_thresholds.get('strong', 40)
            normal_thresh = adx_thresholds.get('normal', 23)
            multiples_map = tp_logic.get('multiples_map', {})
            
            # 3. Determine trend strength category
            if adx_val >= strong_thresh:
                strength_category = 'strong'
            elif adx_val >= normal_thresh:
                strength_category = 'normal'
            else:
                strength_category = 'weak'
            
            self._log_criteria("Adaptive TP Strength", True, f"ADX={adx_val:.2f} -> Strength='{strength_category}'")

            # 4. Select the appropriate multipliers
            multiples = multiples_map.get(strength_category)
            if not multiples:
                logger.warning(f"ADX-Adaptive TP failed: No multipliers found for strength '{strength_category}'.")
                return []

            # 5. Calculate targets using the selected multipliers (re-using standard ATR logic)
            atr_data = self.get_indicator('atr')
            atr_value = self._safe_get(atr_data, ['values', 'atr'])
            if not atr_value:
                logger.warning(f"ADX-Adaptive TP failed: ATR value not available.")
                return []
            
            for m in multiples:
                target = entry_price + (atr_value * m) if direction == 'BUY' else entry_price - (atr_value * m)
                targets.append(target)
        # --- END OF QUANTUM UPGRADE ---
        
        elif tp_type == 'range_targets':
            # ... [unchanged] ...
            target_names = tp_logic.get('targets', [])
            bb_values = (self.get_indicator('bollinger').get('values') or {})
            for name in target_names:
                if name == 'opposite_band':
                    target_band_name = 'bb_upper' if direction == 'BUY' else 'bb_lower'
                    target_price = bb_values.get(target_band_name)
                else:
                    target_price = bb_values.get(name)
                if target_price: targets.append(target_price)
        # ... [other tp_types remain unchanged] ...
        elif tp_type == 'fibonacci_extension':
            levels = tp_logic.get('levels', [1.618, 2.618])
            for level in levels:
                target = entry_price + (risk_per_unit * level) if direction == 'BUY' else entry_price - (risk_per_unit * level)
                targets.append(target)
                
        return sorted(targets) if direction == 'BUY' else sorted(targets, reverse=True)

    def _finalize_risk_parameters(self, entry_price: float, stop_loss: float, targets: List[float], direction: str) -> Dict[str, Any]:
        # ... [This method remains unchanged] ...
        if not targets or entry_price == stop_loss: return {}
        fees_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001)
        slippage_pct = self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        risk_per_unit = abs(entry_price - stop_loss)
        total_risk_per_unit = risk_per_unit + (entry_price * slippage_pct) + (entry_price * fees_pct)
        if total_risk_per_unit < 1e-9: return {}
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct)
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2)
        return {"stop_loss": stop_loss, "targets": targets, "risk_reward_ratio": actual_rr}

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, 
                                         stop_loss: Optional[float] = None, 
                                         sl_params: Optional[Dict[str, Any]] = None, 
                                         tp_logic: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> Dict[str, Any]:
        # ... [This method remains unchanged] ...
        final_sl, final_targets = None, []
        if sl_params and tp_logic:
            final_sl = self._calculate_sl_from_blueprint(entry_price, direction, sl_params)
            if final_sl is None: return {}
            final_targets = self._calculate_tp_from_blueprint(entry_price, final_sl, direction, tp_logic)
        elif stop_loss is not None:
            final_sl = stop_loss
            structure_data = self.get_indicator('structure'); key_levels = (structure_data.get('key_levels') if structure_data else {}) or {}
            if direction.upper() == 'BUY': final_targets = [r['price'] for r in sorted((key_levels.get('resistances') or []), key=lambda x: x['price']) if r['price'] > entry_price][:3]
            else: final_targets = [s['price'] for s in sorted((key_levels.get('supports') or []), key=lambda x: x['price'], reverse=True) if s['price'] < entry_price][:3]
        else:
            return {}
        if not final_targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            risk_dist = abs(entry_price - final_sl)
            final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -risk_dist * r) for r in reward_ratios]
        return self._finalize_risk_parameters(entry_price, final_sl, final_targets, direction)

