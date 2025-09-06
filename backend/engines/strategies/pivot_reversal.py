# strategies/pivot_reversal.py (v4.2 - Flexible Oscillator Logic)

import logging
from typing import Dict, Any, Optional, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PivotConfluenceSniper(BaseStrategy):
    """
    PivotConfluenceSniper - (v4.2 - Flexible Oscillator Logic)
    ----------------------------------------------------------------------------
    This version introduces a significant architectural enhancement by making the
    oscillator confirmation logic configurable. A new 'oscillator_logic'
    parameter ('AND'/'OR') allows for flexible switching between requiring both
    Stochastic & CCI confirmation (stricter) or just one (more opportunities).
    This elevates the strategy's adaptability to match our best practices.
    """
    strategy_name: str = "PivotConfluenceSniper"

    default_config = {
        "default_params": {
            "pivot_levels_to_check": ["R2", "R1", "P", "S1", "S2"],
            "confluence_proximity_percent": 0.4,
            "stoch_oversold": 25.0, "stoch_overbought": 75.0,
            "cci_oversold": -100.0, "cci_overbought": 100.0,
            "atr_sl_multiplier": 1.3,
            "min_rr_ratio": 1.5,
            # ✅ UPGRADE (v4.2): Added new configurable parameter.
            "oscillator_logic": "OR" 
        },
        "timeframe_overrides": {
            "5m": { "confluence_proximity_percent": 0.2, "atr_sl_multiplier": 1.2 },
            "1d": { "confluence_proximity_percent": 0.5, "min_rr_ratio": 2.5 }
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        # This method is unchanged and correct.
        code_defaults = self.default_config.get("default_params", {})
        json_defaults = self.config.get("default_params", {})
        base_configs = {**code_defaults, **json_defaults}
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_config = {**base_configs, **tf_overrides}
        logger.debug(f"Final config for {self.primary_timeframe}: {final_config}")
        return final_config

    def _find_best_confluence_zone(self, direction: str, cfg: Dict, pivots_data: Dict, structure_data: Dict) -> Optional[Dict]:
        # This method is unchanged and correct.
        current_price = self.price_data.get('close')
        if not current_price: return None
        pivot_levels = {lvl['level']: lvl['price'] for lvl in pivots_data.get('levels', [])}
        key_levels = structure_data.get('key_levels', {})
        target_pivot_names = [p for p in cfg['pivot_levels_to_check'] if (p.startswith('S') if direction == "BUY" else p.startswith('R'))]
        target_structures = key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        confluence_zones = []
        for pivot_name in target_pivot_names:
            pivot_price = pivot_levels.get(pivot_name)
            if not pivot_price: continue
            for struct_zone in target_structures:
                struct_price = struct_zone.get('price')
                if struct_price and abs(pivot_price - struct_price) / struct_price * 100 < cfg['confluence_proximity_percent']:
                    zone_price = (pivot_price + struct_price) / 2.0
                    confluence_zones.append({ "price": zone_price, "pivot_name": pivot_name, "structure_zone": struct_zone, "distance_to_price": abs(zone_price - current_price) })
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        required_names = ['pivots', 'structure', 'stochastic', 'cci', 'atr', 'patterns']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        buy_zone = self._find_best_confluence_zone("BUY", cfg, indicators['pivots'], indicators['structure'])
        sell_zone = self._find_best_confluence_zone("SELL", cfg, indicators['pivots'], indicators['structure'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        
        signal_direction, zone_info = None, None
        if buy_zone and price_low and price_low <= buy_zone['price']: signal_direction, zone_info = "BUY", buy_zone
        elif sell_zone and price_high and price_high >= sell_zone['price']: signal_direction, zone_info = "SELL", sell_zone
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Zone Test)", trigger_is_ok, "No confluence zone found or price did not test the zone.")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No valid entry trigger.")
            return None
        
        confirmations = {"confluence_zone": f"Pivot {zone_info['pivot_name']} & Structure (Str: {zone_info['structure_zone']['strength']})"}

        stoch_k = indicators['stochastic'].get('values', {}).get('k')
        cci_val = indicators['cci'].get('values', {}).get('value')
        
        # ✅ UPGRADE (v4.2): Re-engineered oscillator logic to be flexible.
        osc_confirmed = False
        logic = cfg.get('oscillator_logic', 'AND').upper()
        log_details = "Oscillator values missing."

        if stoch_k is not None and cci_val is not None:
            stoch_ok = (signal_direction == "BUY" and stoch_k < cfg['stoch_oversold']) or \
                       (signal_direction == "SELL" and stoch_k > cfg['stoch_overbought'])
            
            cci_ok = (signal_direction == "BUY" and cci_val < cfg['cci_oversold']) or \
                     (signal_direction == "SELL" and cci_val > cfg['cci_overbought'])
            
            if logic == 'OR':
                osc_confirmed = stoch_ok or cci_ok
            else:  # Default to AND for safety and original behavior
                osc_confirmed = stoch_ok and cci_ok
            
            log_details = f"Logic='{logic}', Stoch OK={stoch_ok}, CCI OK={cci_ok}"

        self._log_criteria("Oscillator Filter", osc_confirmed, "No oscillator confirmed the reversal." if not osc_confirmed else f"Confirmation passed. {log_details}")
        if not osc_confirmed:
            self._log_final_decision("HOLD", "Oscillator filter failed.")
            return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {logic})"

        candlestick_ok = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong') is not None
        self._log_criteria("Candlestick Filter", candlestick_ok, "No strong reversal candlestick pattern found.")
        if not candlestick_ok:
            self._log_final_decision("HOLD", "Candlestick filter failed.")
            return None
        confirmations['candlestick_filter'] = "Passed (Strong Pattern)"
        
        htf_ok = True
        if self.config.get('htf_confirmation_enabled', True): # Checking the raw config for the global switch
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        entry_price = self.price_data.get('close')
        atr_value = indicators['atr'].get('values', {}).get('atr', entry_price * 0.01)
        structure_level = zone_info['structure_zone']['price']
        stop_loss = structure_level - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else structure_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        pivots_data = indicators['pivots']
        pivot_p_level = next((lvl['price'] for lvl in pivots_data.get('levels', []) if lvl['level'] == 'P'), None)
        if pivot_p_level and risk_params and risk_params.get('targets'):
            risk_params['targets'][0] = pivot_p_level
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(pivot_p_level - entry_price) / risk_amount, 2)
            confirmations['target_adjustment'] = "TP1 set to Central Pivot"
            self._log_criteria("Target Adjustment", True, f"TP1 was adjusted to the Central Pivot level ({pivot_p_level:.5f}).")

        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= cfg['min_rr_ratio']
        self._log_criteria("Final R/R Check", rr_is_ok, f"Failed R/R check. (Calculated: {risk_params.get('risk_reward_ratio', 0)}, Required: {cfg['min_rr_ratio']})")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Final R/R check failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R to TP1: {risk_params.get('risk_reward_ratio')})"
        
        self._log_final_decision(signal_direction, "All criteria met. Pivot Sniper signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
