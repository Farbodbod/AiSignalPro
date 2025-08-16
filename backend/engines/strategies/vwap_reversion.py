# backend/engines/strategies/vwap_reversion.py (v4.0 - Defensive Logging Edition)

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapMeanReversion(BaseStrategy):
    """
    VwapMeanReversion - (v4.0 - Defensive Logging Edition)
    --------------------------------------------------------------------------------------
    This version integrates the professional logging system for full transparency
    and hardens the strategy with a dynamic data availability check to prevent crashes.
    The advanced oscillator engine and VWAP-based targeting are fully preserved.
    """
    strategy_name: str = "VwapMeanReversion"

    default_config = {
        "max_adx_for_reversion": 25.0,
        "min_rr_ratio": 2.0,
        "oscillator_logic": "AND",
        "use_rsi": True, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
        "use_williams_r": True, "williams_r_oversold": -80.0, "williams_r_overbought": -20.0,
        "atr_sl_multiplier": 1.5,
        "require_candle_confirmation": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }
    
    def _get_signal_config(self) -> Dict[str, Any]:
        """ ✅ FIX: Simplified and robust config loader for flat configurations. """
        # This strategy uses a flat config structure, so we just return the merged config.
        return self.config

    def _get_oscillator_confirmation(self, direction: str, cfg: Dict, rsi_data: Optional[Dict], wr_data: Optional[Dict]) -> bool:
        # This helper's logic remains unchanged.
        rsi_confirm = False
        if cfg.get('use_rsi') and rsi_data:
            rsi_val = rsi_data.get('values', {}).get('rsi')
            if rsi_val is not None:
                if direction == "BUY" and rsi_val < cfg['rsi_oversold']: rsi_confirm = True
                elif direction == "SELL" and rsi_val > cfg['rsi_overbought']: rsi_confirm = True

        wr_confirm = False
        if cfg.get('use_williams_r') and wr_data:
            wr_val = wr_data.get('values', {}).get('wr')
            if wr_val is not None:
                if direction == "BUY" and wr_val < cfg['williams_r_oversold']: wr_confirm = True
                elif direction == "SELL" and wr_val > cfg['williams_r_overbought']: wr_confirm = True
        
        logic = cfg.get('oscillator_logic', "AND").upper()
        if logic == "AND":
            checks = []
            if cfg.get('use_rsi'): checks.append(rsi_confirm)
            if cfg.get('use_williams_r'): checks.append(wr_confirm)
            return all(checks) if checks else False
        elif logic == "OR":
            return rsi_confirm or wr_confirm
        return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Dynamic Data Availability Check ---
        required_names = ['vwap_bands', 'atr', 'adx']
        if cfg.get('use_rsi'): required_names.append('rsi')
        if cfg.get('use_williams_r'): required_names.append('williams_r')
        if cfg.get('require_candle_confirmation'): required_names.append('patterns')

        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Market Regime & Primary Trigger ---
        adx_strength = indicators['adx'].get('values', {}).get('adx', 100)
        adx_ok = adx_strength <= cfg.get('max_adx_for_reversion', 25.0)
        self._log_criteria("Market Regime (ADX)", adx_ok, f"Market is trending (ADX: {adx_strength:.2f}), not suitable for reversion.")
        if not adx_ok:
            self._log_final_decision("HOLD", "ADX filter failed.")
            return None

        vwap_data = indicators['vwap_bands']
        vwap_position = vwap_data.get('analysis', {}).get('position')
        signal_direction = "BUY" if "Below" in vwap_position else "SELL" if "Above" in vwap_position else None
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (VWAP Bands)", trigger_is_ok, f"Price is not in a reversion zone. (Position: {vwap_position})")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        confirmations = {"trigger": f"Price {vwap_position}", "market_regime": f"Ranging (ADX: {adx_strength:.2f})"}

        # --- 3. Confirmation Funnel ---
        osc_ok = self._get_oscillator_confirmation(signal_direction, cfg, indicators.get('rsi'), indicators.get('williams_r'))
        self._log_criteria("Oscillator Filter", osc_ok, f"Oscillators are not in agreement based on '{cfg.get('oscillator_logic')}' logic.")
        if not osc_ok:
            self._log_final_decision("HOLD", "Oscillator filter failed.")
            return None
        confirmations['oscillator_filter'] = f"Passed (Logic: {cfg.get('oscillator_logic')})"

        candle_ok = True
        if cfg.get('require_candle_confirmation'):
            candle_ok = self._get_candlestick_confirmation(signal_direction, min_reliability='Medium') is not None
        self._log_criteria("Candlestick Filter", candle_ok, "No confirming candlestick pattern found.")
        if not candle_ok:
            self._log_final_decision("HOLD", "Candlestick filter failed.")
            return None
        if cfg.get('require_candle_confirmation'): confirmations['candlestick_filter'] = "Passed"

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        if cfg.get('htf_confirmation_enabled'): confirmations['htf_filter'] = "Passed"

        # --- 4. Risk Management & Target Adjustment ---
        entry_price = self.price_data.get('close')
        vwap_values = vwap_data.get('values', {})
        atr_value = indicators['atr'].get('values', {}).get('atr')
        
        risk_data_ok = entry_price is not None and atr_value is not None
        self._log_criteria("Risk Data Availability", risk_data_ok, "Missing data for SL calculation (entry/atr).")
        if not risk_data_ok: self._log_final_decision("HOLD", "Risk data missing."); return None
        
        stop_loss, sl_source_band = (0, None)
        if signal_direction == "BUY":
            sl_source_band = vwap_values.get('lower_band')
            if sl_source_band: stop_loss = sl_source_band - (atr_value * cfg.get('atr_sl_multiplier', 1.5))
        else: # SELL
            sl_source_band = vwap_values.get('upper_band')
            if sl_source_band: stop_loss = sl_source_band + (atr_value * cfg.get('atr_sl_multiplier', 1.5))
        
        if not sl_source_band: self._log_final_decision("HOLD", "VWAP bands not available for SL calculation."); return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'] = [vwap_line] # Set VWAP as the only target
            risk_amount = abs(entry_price - stop_loss)
            if risk_amount > 1e-9:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - entry_price) / risk_amount, 2)
            self._log_criteria("Target Adjustment", True, "TP1 adjusted to VWAP line.")

        min_rr = cfg.get('min_rr_ratio', 1.8)
        rr_is_ok = risk_params and risk_params.get("risk_reward_ratio", 0) >= min_rr
        self._log_criteria("Final R/R Check", rr_is_ok, f"Failed R/R check. (Calculated: {risk_params.get('risk_reward_ratio', 0)}, Required: {min_rr})")
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Final R/R check failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R to VWAP: {risk_params.get('risk_reward_ratio')})"
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. VWAP Mean Reversion signal confirmed.")

        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
