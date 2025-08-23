# strategies/base_strategy.py (v11.1 - The Boundary Aware Edition)

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, ClassVar, Tuple
import logging
import pandas as pd
import json
from copy import deepcopy

logger = logging.getLogger(__name__)

def get_indicator_config_key(name: str, params: Dict[str, Any]) -> str:
    # ... [This function is correct and unchanged] ...
    try:
        filtered_params = {k: v for k, v in params.items() if k not in ['enabled', 'dependencies', 'name']}
        if not filtered_params: return name
        param_str = json.dumps(filtered_params, sort_keys=True, separators=(',', ':'))
        return f"{name}_{param_str}"
    except TypeError:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()) if k not in ['enabled', 'dependencies', 'name'])
        return f"{name}_{param_str}" if param_str else name

def deep_merge(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    # ... [This function is correct and unchanged] ...
    result = deepcopy(dict1)
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict): result[k] = deep_merge(result[k], v)
        else: result[k] = v
    return result

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v11.1 - The Boundary Aware Edition)
    ---------------------------------------------------------------------------------------------
    This version includes a critical architectural fix to the HTF confirmation
    engine. It is now "boundary aware", meaning it automatically bypasses the HTF
    check on the highest configured timeframe (e.g., '1d'), solving the "missing
    HTF indicators" issue for all strategies with a single, central fix.
    """
    strategy_name: str = "BaseStrategy"
    default_config: ClassVar[Dict[str, Any]] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        # ... [This function is correct and unchanged] ...
        self.analysis, self.config, self.main_config, self.htf_analysis = primary_analysis, deep_merge(self.default_config, config or {}), main_config, htf_analysis or {}
        self.primary_timeframe, self.symbol, self.price_data, self.df = primary_timeframe, symbol, self.analysis.get('price_data'), self.analysis.get('final_df')
        self.indicator_configs, self.log_details, self.name = self.config.get('indicator_configs', {}), {"criteria_results": [], "indicator_trace": [], "risk_trace": []}, self.config.get('name', self.strategy_name)

    # ... [All logging functions and other helpers are correct and unchanged] ...
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
        signal_emoji = "🟩" if signal == "BUY" else "🟥" if signal == "SELL" else "⬜";
        logger.info(f"{signal_emoji} Final Decision: {self.name} on {self.symbol} {self.primary_timeframe} -> Signal: {signal}. Reason: {reason}")

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]: pass

    def get_indicator(self, name_or_alias: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        source = analysis_source if analysis_source is not None else self.analysis;
        if not source: return None
        indicator_map = source.get('_indicator_map', {})
        indicator_data, unique_key = None, None
        if name_or_alias in self.indicator_configs:
            order = self.indicator_configs[name_or_alias]; unique_key = get_indicator_config_key(order['name'], order.get('params', {}))
        elif name_or_alias in indicator_map:
            unique_key = indicator_map.get(name_or_alias)
        if not unique_key: self._log_indicator_trace(name_or_alias, None, status="FAILED", reason="Indicator key could not be resolved."); return None
        indicator_data = source.get(unique_key)
        if not indicator_data or not isinstance(indicator_data, dict):
            self._log_indicator_trace(name_or_alias, None, status="FAILED", reason=f"Missing data object for key: {unique_key}."); return None
        status = indicator_data.get("status", "").lower()
        if "error" in status or "failed" in status:
            self._log_indicator_trace(name_or_alias, status, status="FAILED", reason=f"Indicator reported failure status: {status}"); return None
        self._log_indicator_trace(name_or_alias, "OK"); return indicator_data

    def _is_outlier_candle(self, atr_multiplier: float = 5.0) -> bool:
        if not self.price_data: return True 
        atr_data = self.get_indicator('atr')
        if not atr_data or 'values' not in atr_data or not isinstance((atr_data.get('values') or {}).get('atr'), (int, float)):
            logger.warning(f"Outlier check skipped for {self.symbol}@{self.primary_timeframe}: ATR not available or invalid."); return False 
        atr_value = (atr_data['values']['atr'])
        candle_range = self.price_data['high'] - self.price_data['low']
        if candle_range > (atr_value * atr_multiplier):
            self._log_criteria("Outlier Candle Shield", False, f"Outlier candle detected! Range={candle_range:.2f} > {atr_multiplier}*ATR({atr_value:.2f})")
            return True
        return False
        
    def _get_market_regime(self, adx_threshold: float = 25.0) -> Tuple[str, float]:
        adx_data = self.get_indicator('adx')
        if not adx_data or 'values' not in adx_data or not isinstance((adx_data.get('values') or {}).get('adx'), (int, float)):
            logger.warning(f"Could not determine market regime for {self.symbol}@{self.primary_timeframe} due to missing/invalid ADX.")
            return "UNKNOWN", 0.0
        adx_val = (adx_data.get('values') or {}).get('adx', 0.0)
        if adx_val >= adx_threshold: return "TRENDING", adx_val
        else: return "RANGING", adx_val
    
    def _is_trend_exhausted(self, direction: str, buy_exhaustion_threshold: float = 80.0, sell_exhaustion_threshold: float = 20.0) -> bool:
        rsi_data = self.get_indicator('rsi')
        if not rsi_data or 'values' not in rsi_data or not isinstance((rsi_data.get('values') or {}).get('rsi'), (int, float)):
            logger.warning(f"Exhaustion check skipped for {self.symbol}@{self.primary_timeframe}: RSI not available or invalid."); return False
        rsi_value = (rsi_data['values']['rsi'])
        is_exhausted = False; reason = ""
        if direction == "BUY" and rsi_value >= buy_exhaustion_threshold:
            is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) > {buy_exhaustion_threshold}."
        elif direction == "SELL" and rsi_value <= sell_exhaustion_threshold:
            is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) < {sell_exhaustion_threshold}."
        if is_exhausted: self._log_criteria("Trend Exhaustion Shield", False, reason); return True
        return False

    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        pattern_analysis = self.get_indicator('patterns');
        if not pattern_analysis or 'analysis' not in pattern_analysis: return None
        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}; min_reliability_score = reliability_map.get(min_reliability, 1)
        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = (pattern_analysis.get('analysis') or {}).get(target_pattern_list, [])
        for pattern in found_patterns:
            if reliability_map.get(pattern.get('reliability'), 0) >= min_reliability_score: return pattern
        return None

    def _get_volume_confirmation(self) -> bool:
        whale_analysis = self.get_indicator('whales');
        if not whale_analysis: return False
        min_spike_score, analysis = self.config.get('min_whale_spike_score', 1.5), whale_analysis.get('analysis') or {}
        is_whale_activity, spike_score = analysis.get('is_whale_activity', False), analysis.get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score

    def _get_trend_confirmation(self, direction: str) -> bool:
        # ✅ THE BOUNDARY AWARE FIX (v11.1):
        # This function is now the single source of truth for all HTF logic.
        htf_map = self.config.get('htf_map', {}); target_htf = htf_map.get(self.primary_timeframe)
        if not target_htf:
            # If we are at the highest timeframe, the check automatically passes.
            return True
        
        if not self.htf_analysis or not self.htf_analysis.get('final_df'):
            logger.warning(f"HTF confirmation for {self.symbol}@{self.primary_timeframe} failed: HTF data package for '{target_htf}' is missing or invalid.")
            return False

        htf_rules = self.config.get('htf_confirmations', {}); current_score = 0; min_required_score = htf_rules.get('min_required_score', 1)
        for rule_name, rule_params in htf_rules.items():
            if rule_name == "min_required_score": continue
            indicator_analysis = self.get_indicator(rule_name, analysis_source=self.htf_analysis)
            if not indicator_analysis:
                logger.warning(f"HTF confirmation for {self.symbol}@{self.primary_timeframe} failed: Required indicator '{rule_name}' was not found in HTF data.")
                return False # Fail confirmation if a required HTF indicator is missing
            
            weight = rule_params.get('weight', 1)
            if rule_name.lower() == "adx":
                adx_strength = (indicator_analysis.get('values') or {}).get('adx', 0)
                adx_dir = (indicator_analysis.get('analysis') or {}).get('direction', 'Neutral')
                is_aligned = (direction.upper() == "BUY" and "BULLISH" in adx_dir.upper()) or \
                             (direction.upper() == "SELL" and "BEARISH" in adx_dir.upper())
                if adx_strength >= rule_params.get('min_strength', 20) and is_aligned: current_score += weight
            elif rule_name.lower() == "supertrend":
                st_trend = (indicator_analysis.get('analysis') or {}).get('trend', 'Neutral')
                if (direction.upper() == "BUY" and "UP" in st_trend.upper()) or \
                   (direction.upper() == "SELL" and "DOWN" in st_trend.upper()): current_score += weight
            else:
                ind_dir = (indicator_analysis.get('analysis') or {}).get('direction')
                if ind_dir and direction.upper() in ind_dir.upper(): current_score += weight
        
        self._log_indicator_trace(f"HTF_Score", current_score, reason=f"Required: {min_required_score}")
        return current_score >= min_required_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if not isinstance(entry_price, (int, float)) or not isinstance(stop_loss, (int, float)):
            logger.debug(f"Risk calc skipped for invalid inputs. Entry: {entry_price}, SL: {stop_loss}"); return {}
        if entry_price == stop_loss: return {}
        fees_pct, slippage_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001), self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit < 1e-9: return {}
        total_risk_per_unit = risk_per_unit + (entry_price * slippage_pct) + (entry_price * fees_pct)
        structure_data = self.get_indicator('structure'); key_levels = (structure_data.get('key_levels') if structure_data else {}) or {}
        targets, resistances, supports = [], (key_levels.get('resistances') or []), (key_levels.get('supports') or [])
        resistances_prices, supports_prices = [r['price'] for r in resistances], [s['price'] for s in supports]
        if direction.upper() == 'BUY': targets = [r for r in sorted(resistances_prices) if r > entry_price][:3]
        elif direction.upper() == 'SELL': targets = [s for s in sorted(supports_prices, reverse=True) if s < entry_price][:3]
        if not targets:
            logger.info(f"No key level targets found. Using reward ratios fallback.")
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (total_risk_per_unit * r if direction.upper() == 'BUY' else -total_risk_per_unit * r) for r in reward_ratios]
        if not targets: return {}
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct)
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2) if total_risk_per_unit > 0 else 0
        final_params = {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
        self.log_details["risk_trace"].append(final_params)
        return final_params

