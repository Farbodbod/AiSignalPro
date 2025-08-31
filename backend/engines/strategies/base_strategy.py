# strategies/base_strategy.py (v13.0 - Advanced SL Blueprint Processor)

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
    World-Class Base Strategy Framework - (v13.0 - Advanced SL Blueprint Processor)
    ---------------------------------------------------------------------------------------------
    This major architectural upgrade enhances the Blueprint Processor to understand
    new, sophisticated SL logic types ('structural' and 'atr_based'). This allows
    advanced strategies like KeltnerMomentumBreakout to delegate their complex
    risk calculations to the core engine, ensuring system-wide consistency and
    enabling future extensibility.
    """
    strategy_name: str = "BaseStrategy"
    default_config: ClassVar[Dict[str, Any]] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], main_config: Dict[str, Any], primary_timeframe: str, symbol: str, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis, self.config, self.main_config, self.htf_analysis = primary_analysis, deep_merge(self.default_config, config or {}), main_config, htf_analysis or {}
        self.primary_timeframe, self.symbol, self.price_data, self.df = primary_timeframe, symbol, self.analysis.get('price_data'), self.analysis.get('final_df')
        self.indicator_configs, self.log_details, self.name = self.config.get('indicator_configs', {}), {"criteria_results": [], "indicator_trace": [], "risk_trace": []}, self.config.get('name', self.strategy_name)

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

    def _is_outlier_candle(self, atr_multiplier: float = 5.0) -> bool:
        if not self.price_data: return True 
        atr_data = self.get_indicator('atr')
        if not atr_data or 'values' not in atr_data or not isinstance((atr_data.get('values') or {}).get('atr'), (int, float)):
            logger.warning(f"Outlier check skipped: ATR not available."); return False 
        atr_value = (atr_data['values']['atr']); candle_range = self.price_data['high'] - self.price_data['low']
        if candle_range > (atr_value * atr_multiplier):
            self._log_criteria("Outlier Candle Shield", False, f"Outlier candle detected! Range={candle_range:.2f} > {atr_multiplier}*ATR({atr_value:.2f})"); return True
        return False
        
    def _get_market_regime(self, adx_threshold: float = 25.0) -> Tuple[str, float]:
        adx_data = self.get_indicator('adx')
        if not adx_data or 'values' not in adx_data or not isinstance((adx_data.get('values') or {}).get('adx'), (int, float)):
            logger.warning(f"Could not determine market regime due to missing/invalid ADX."); return "UNKNOWN", 0.0
        adx_val = (adx_data.get('values') or {}).get('adx', 0.0)
        if adx_val >= adx_threshold: return "TRENDING", adx_val
        else: return "RANGING", adx_val
    
    def _is_trend_exhausted(self, direction: str, buy_exhaustion_threshold: float = 80.0, sell_exhaustion_threshold: float = 20.0) -> bool:
        rsi_data = self.get_indicator('rsi')
        if not rsi_data or 'values' not in rsi_data or not isinstance((rsi_data.get('values') or {}).get('rsi'), (int, float)):
            logger.warning(f"Exhaustion check skipped: RSI not available."); return False
        rsi_value = (rsi_data['values']['rsi']); is_exhausted = False; reason = ""
        if direction == "BUY" and rsi_value >= buy_exhaustion_threshold: is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) > {buy_exhaustion_threshold}."
        elif direction == "SELL" and rsi_value <= sell_exhaustion_threshold: is_exhausted = True; reason = f"Trend Exhaustion! RSI ({rsi_value:.2f}) < {sell_exhaustion_threshold}."
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
        htf_map = self.config.get('htf_map', {}); target_htf = htf_map.get(self.primary_timeframe)
        if not target_htf: return True
        htf_df = self.htf_analysis.get('final_df')
        if not isinstance(htf_df, pd.DataFrame) or htf_df.empty: logger.warning(f"HTF confirmation failed: HTF data for '{target_htf}' is missing."); return False
        htf_rules = self.config.get('htf_confirmations', {}); current_score = 0; min_required_score = htf_rules.get('min_required_score', 1)
        for rule_name, rule_params in htf_rules.items():
            if rule_name == "min_required_score": continue
            indicator_analysis = self.get_indicator(rule_name, analysis_source=self.htf_analysis)
            if not indicator_analysis: logger.warning(f"HTF confirmation failed: Required indicator '{rule_name}' missing."); return False
            weight = rule_params.get('weight', 1)
            if rule_name.lower() == "adx":
                adx_strength = (indicator_analysis.get('values') or {}).get('adx', 0); adx_dir = (indicator_analysis.get('analysis') or {}).get('direction', 'Neutral')
                is_aligned = (direction.upper() == "BUY" and "BULLISH" in adx_dir.upper()) or (direction.upper() == "SELL" and "BEARISH" in adx_dir.upper())
                if adx_strength >= rule_params.get('min_strength', 20) and is_aligned: current_score += weight
            elif rule_name.lower() == "supertrend":
                st_trend = (indicator_analysis.get('analysis') or {}).get('trend', 'Neutral')
                if (direction.upper() == "BUY" and "UP" in st_trend.upper()) or (direction.upper() == "SELL" and "DOWN" in st_trend.upper()): current_score += weight
        self._log_indicator_trace(f"HTF_Score", current_score, reason=f"Required: {min_required_score}"); return current_score >= min_required_score

    def _calculate_sl_from_blueprint(self, entry_price: float, direction: str, sl_params: Dict[str, Any]) -> Optional[float]:
        sl_type = sl_params.get('type')
        atr_data = self.get_indicator('atr')
        atr_value = (atr_data.get('values') or {}).get('atr') if atr_data else None
        calculated_sl = None

        if sl_type == 'band':
            band_name = sl_params.get('band_name')
            multiplier = sl_params.get('buffer_atr_multiplier', 1.0)
            bollinger_data = self.get_indicator('bollinger')
            band_value = (bollinger_data.get('values') or {}).get(band_name)
            if None in [band_name, band_value, atr_value]:
                logger.warning(f"SL calculation failed for 'band' type: Missing required data.")
                return None
            buffer = atr_value * multiplier
            calculated_sl = band_value - buffer if direction == 'BUY' else band_value + buffer
        
        elif sl_type == 'structural':
            indicator_name = sl_params.get('indicator')
            level_name = sl_params.get('level_name')
            if not indicator_name or not level_name:
                logger.warning(f"SL calculation failed for 'structural' type: Missing 'indicator' or 'level_name'.")
                return None
            indicator_data = self.get_indicator(indicator_name)
            structural_level = (indicator_data.get('values') or {}).get(level_name) if indicator_data else None
            if structural_level is None:
                logger.warning(f"SL calculation failed for 'structural' type: Could not find level '{level_name}' in indicator '{indicator_name}'.")
                return None
            calculated_sl = structural_level

        elif sl_type == 'atr_based':
            multiplier = sl_params.get('atr_multiplier', 1.5)
            if atr_value is None:
                logger.warning(f"SL calculation failed for 'atr_based' type: Missing ATR value.")
                return None
            calculated_sl = entry_price - (atr_value * multiplier) if direction == 'BUY' else entry_price + (atr_value * multiplier)
        
        else:
            logger.warning(f"Unknown SL logic type received in blueprint: {sl_type}")
            return None

        if calculated_sl is not None:
            if (direction == 'BUY' and calculated_sl >= entry_price) or \
               (direction == 'SELL' and calculated_sl <= entry_price):
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

        elif tp_type == 'range_targets':
            target_names = tp_logic.get('targets', [])
            bb_values = (self.get_indicator('bollinger').get('values') or {})
            for name in target_names:
                if name == 'opposite_band':
                    target_band_name = 'bb_upper' if direction == 'BUY' else 'bb_lower'
                    target_price = bb_values.get(target_band_name)
                else:
                    target_price = bb_values.get(name)
                if target_price: targets.append(target_price)

        elif tp_type == 'band_target':
            band_name = tp_logic.get('band_name')
            bb_values = (self.get_indicator('bollinger').get('values') or {})
            target_price = bb_values.get(band_name)
            if target_price:
                middle_band = bb_values.get('middle_band')
                if direction == 'BUY' and middle_band and entry_price < middle_band < target_price:
                    targets.append(middle_band)
                elif direction == 'SELL' and middle_band and entry_price > middle_band > target_price:
                    targets.append(middle_band)
                targets.append(target_price)

        elif tp_type == 'fibonacci_extension':
            levels = tp_logic.get('levels', [1.618, 2.618])
            for level in levels:
                target = entry_price + (risk_per_unit * level) if direction == 'BUY' else entry_price - (risk_per_unit * level)
                targets.append(target)
        
        return sorted(targets) if direction == 'BUY' else sorted(targets, reverse=True)

    def _finalize_risk_parameters(self, entry_price: float, stop_loss: float, targets: List[float], direction: str) -> Dict[str, Any]:
        if not targets or entry_price == stop_loss: return {}
        
        fees_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001)
        slippage_pct = self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)

        risk_per_unit = abs(entry_price - stop_loss)
        total_risk_per_unit = risk_per_unit + (entry_price * slippage_pct) + (entry_price * fees_pct)
        if total_risk_per_unit < 1e-9: return {}
        
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct)
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2)
        
        final_params = {
            "stop_loss": round(stop_loss, 5), 
            "targets": [round(t, 5) for t in targets], 
            "risk_reward_ratio": actual_rr
        }
        self.log_details["risk_trace"].append(final_params)
        return final_params

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, 
                                         stop_loss: Optional[float] = None, 
                                         sl_params: Optional[Dict[str, Any]] = None, 
                                         tp_logic: Optional[Dict[str, Any]] = None,
                                         **kwargs) -> Dict[str, Any]:
        
        final_sl, final_targets = None, []

        if sl_params and tp_logic:
            logger.debug(f"Using Blueprint Processor for risk calculation.")
            final_sl = self._calculate_sl_from_blueprint(entry_price, direction, sl_params)
            if final_sl is None:
                logger.error(f"Blueprint SL calculation failed. Aborting risk management.")
                return {}
            final_targets = self._calculate_tp_from_blueprint(entry_price, final_sl, direction, tp_logic)

        elif stop_loss is not None:
            logger.debug(f"Using Legacy path for risk calculation.")
            final_sl = stop_loss
            structure_data = self.get_indicator('structure'); key_levels = (structure_data.get('key_levels') if structure_data else {}) or {}
            if direction.upper() == 'BUY': final_targets = [r['price'] for r in sorted((key_levels.get('resistances') or []), key=lambda x: x['price']) if r['price'] > entry_price][:3]
            elif direction.upper() == 'SELL': final_targets = [s['price'] for s in sorted((key_levels.get('supports') or []), key=lambda x: x['price'], reverse=True) if s['price'] < entry_price][:3]
        
        else:
            logger.error("Risk management called with neither a blueprint nor a stop_loss value.")
            return {}

        if not final_targets:
            logger.info(f"No targets found from primary logic. Using reward ratios fallback.")
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            risk_dist = abs(entry_price - final_sl)
            final_targets = [entry_price + (risk_dist * r if direction.upper() == 'BUY' else -risk_dist * r) for r in reward_ratios]

        return self._finalize_risk_parameters(entry_price, final_sl, final_targets, direction)
