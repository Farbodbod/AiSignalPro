# backend/engines/strategies/trend_rider.py (v5.0 - Defensive Logging Edition)

import logging
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v5.0 - Defensive Logging Edition)
    -----------------------------------------------------------------------------------------
    This version fixes a critical KeyError by implementing a robust hierarchical
    config loader. It also integrates the new professional logging system for
    full transparency into its advanced, adaptive trend-following logic.
    """
    strategy_name: str = "TrendRiderPro"

    default_config = {
        "default_params": {
            "entry_trigger_type": "supertrend",
            "min_adx_strength": 25.0,
            "st_multiplier": 3.0,
            "ch_atr_multiplier": 3.0,
            "tactical_tp_rr_ratio": 2.0,
        },
        "timeframe_overrides": {
            "5m": { "min_adx_strength": 22.0, "st_multiplier": 2.5, "ch_atr_multiplier": 2.5 },
            "15m": { "min_adx_strength": 23.0 },
            "1d": { "min_adx_strength": 28.0, "ch_atr_multiplier": 3.5, "tactical_tp_rr_ratio": 2.5 }
        },
        "htf_confirmation_enabled": True, # This key was causing the KeyError
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        """ ✅ CRITICAL FIX: Robustly loads and merges hierarchical configs. """
        # Start with a copy of all top-level configurations (like htf_confirmation_enabled)
        final_cfg = self.config.copy()
        
        # Get base parameters and timeframe-specific overrides
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        
        # Merge parameters together, with overrides taking precedence
        final_params = {**base_params, **tf_overrides}
        
        # Update the main config dictionary with the final, merged parameters
        final_cfg.update(final_params)
        
        return final_cfg

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> tuple[Optional[str], str]:
        # This helper's logic remains unchanged.
        if cfg.get('entry_trigger_type') == 'ema_cross':
            trigger_name = "EMA Cross"
            ema_cross_data = self.get_indicator('ema_cross')
            if ema_cross_data:
                signal = ema_cross_data.get('analysis', {}).get('signal')
                if signal in ['Buy', 'Sell']: return signal.upper(), trigger_name
        else: # Default to supertrend
            trigger_name = "SuperTrend Crossover"
            supertrend_data = self.get_indicator('supertrend')
            if supertrend_data:
                signal = supertrend_data.get('analysis', {}).get('signal')
                if "Bullish Crossover" in signal: return "BUY", trigger_name
                if "Bearish Crossover" in signal: return "SELL", trigger_name
        return None, ""

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Data Availability Check ---
        required_indicators = ['adx', 'chandelier_exit', 'fast_ma']
        if cfg.get('entry_trigger_type') == 'ema_cross':
            required_indicators.append('ema_cross')
        else:
            required_indicators.append('supertrend')
            
        indicators = {name: self.get_indicator(name) for name in required_indicators}
        missing_indicators = [name for name, data in indicators.items() if data is None]

        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Confirmation Funnel ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        self._log_criteria("Primary Trigger", signal_direction is not None, f"No valid entry signal from {cfg.get('entry_trigger_type')}.")
        if not signal_direction:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None

        adx_data = indicators['adx']
        adx_strength = adx_data.get('values', {}).get('adx', 0)
        dmi_plus = adx_data.get('values', {}).get('plus_di', 0)
        dmi_minus = adx_data.get('values', {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= cfg['min_adx_strength']
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                           (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("ADX/DMI Filter", adx_ok, f"Trend not strong or aligned. (ADX: {adx_strength:.2f})")
        if not adx_ok:
            self._log_final_decision("HOLD", "ADX/DMI filter failed.")
            return None
        
        ma_filter_data = indicators['fast_ma']
        ma_value = ma_filter_data.get('values', {}).get('ma_value', 0)
        current_price = self.price_data.get('close', 0)
        ma_filter_ok = not ((signal_direction == "BUY" and current_price < ma_value) or \
                            (signal_direction == "SELL" and current_price > ma_value))
        self._log_criteria("Master Trend Filter", ma_filter_ok, f"Price is on the wrong side of the master MA.")
        if not ma_filter_ok:
            self._log_final_decision("HOLD", "Master Trend filter failed.")
            return None
        
        htf_ok = True
        if cfg['htf_confirmation_enabled']:
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Trend is not aligned with the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        
        # --- 3. Risk Management & Final Checks ---
        entry_price = self.price_data.get('close')
        chandelier_data = indicators['chandelier_exit']
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        trailing_stop_loss = chandelier_data.get('values', {}).get(stop_loss_key)

        risk_data_ok = entry_price is not None and trailing_stop_loss is not None
        self._log_criteria("Risk Data Availability", risk_data_ok, "Could not determine Entry or Chandelier Stop Loss.")
        if not risk_data_ok:
            self._log_final_decision("HOLD", "Missing data for risk calculation.")
            return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, trailing_stop_loss)
        risk_amount = abs(entry_price - trailing_stop_loss)
        tactical_tp1 = entry_price + (risk_amount * cfg['tactical_tp_rr_ratio']) if signal_direction == "BUY" else entry_price - (risk_amount * cfg['tactical_tp_rr_ratio'])
        
        risk_params['targets'] = [round(tactical_tp1, 5)]
        if risk_amount > 1e-9:
             risk_params['risk_reward_ratio'] = round(abs(tactical_tp1 - entry_price) / risk_amount, 2)
        else:
             risk_params['risk_reward_ratio'] = 0
        
        # --- 4. Final Decision ---
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX > {cfg['min_adx_strength']:.1f} (Value: {adx_strength:.2f})",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine" if cfg['htf_confirmation_enabled'] else "Disabled",
            "exit_management": f"Tactical TP1 + Chandelier Trailing SL at {trailing_stop_loss:.5f}"
        }
        self._log_final_decision(signal_direction, "All criteria met. Adaptive Trend Rider signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
