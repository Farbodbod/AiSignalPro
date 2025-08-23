# backend/engines/strategies/trend_rider.py (v6.0 - The Hardened Engine)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v6.0 - The Hardened Engine)
    -----------------------------------------------------------------------------------------
    This version is a major hardening release based on a world-class peer review.
    It incorporates critical NaN-guards, a true HTF dependency check, zero-risk
    prevention, and other stability fixes, making it a truly robust and
    production-ready trend-following engine.
    """
    strategy_name: str = "TrendRiderPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "default_params": {
            "entry_trigger_type": "supertrend", "min_adx_strength": 25.0,
            "st_multiplier": 3.0, "ch_atr_multiplier": 3.0, "tactical_tp_rr_ratio": 2.0,
            "min_risk_pct": 0.1 # New: Minimum allowed risk as a percentage of price
        },
        "timeframe_overrides": {
            "5m": { "min_adx_strength": 22.0, "st_multiplier": 2.5, "ch_atr_multiplier": 2.5 },
            "15m": { "min_adx_strength": 23.0 },
            "1d": { "min_adx_strength": 28.0, "ch_atr_multiplier": 3.5, "tactical_tp_rr_ratio": 2.5 }
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2, "adx": {"weight": 1, "min_strength": 25}, "supertrend": {"weight": 1}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        final_cfg = self.config.copy()
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_params = {**base_params, **tf_overrides}
        final_cfg.update(final_params)
        return final_cfg

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> Tuple[Optional[str], str]:
        if cfg.get('entry_trigger_type') == 'ema_cross':
            trigger_name = "EMA Cross"; ema_cross_data = self.get_indicator('ema_cross')
            if ema_cross_data:
                signal = (ema_cross_data.get('analysis') or {}).get('signal')
                if signal in ['Buy', 'Sell']: return signal.upper(), trigger_name
        else: # Default to supertrend
            trigger_name = "SuperTrend Crossover"; supertrend_data = self.get_indicator('supertrend')
            if supertrend_data:
                signal = str((supertrend_data.get('analysis') or {}).get('signal', '')).lower()
                if "bullish crossover" in signal: return "BUY", trigger_name
                if "bearish crossover" in signal: return "SELL", trigger_name
        return None, ""

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # --- 1. Data Availability Check ---
        required_names = ['adx', 'chandelier_exit', 'fast_ma']
        if cfg.get('entry_trigger_type') == 'ema_cross': required_names.append('ema_cross')
        else: required_names.append('supertrend')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        if missing: self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        
        # ✅ TRUE HTF DEPENDENCY CHECK: Also check for HTF indicators if needed.
        if cfg.get('htf_confirmation_enabled'):
            htf_rules = cfg.get('htf_confirmations', {})
            htf_required = [name for name in htf_rules if name != 'min_required_score']
            htf_indicators = {name: self.get_indicator(name, analysis_source=self.htf_analysis) for name in htf_required}
            htf_missing = [name for name, data in htf_indicators.items() if data is None]
            if htf_missing: self._log_final_decision("HOLD", f"HTF indicators missing: {', '.join(htf_missing)}"); return None
        
        self._log_criteria("Data Availability", True, "All required primary and HTF data is valid.")

        # --- 2. Confirmation Funnel ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        self._log_criteria("Primary Trigger", signal_direction is not None, f"Signal from {cfg.get('entry_trigger_type')}: {'Found' if signal_direction else 'Not Found'}")
        if not signal_direction: self._log_final_decision("HOLD", "No primary trigger."); return None

        adx_strength = (indicators['adx'].get('values') or {}).get('adx', 0.0)
        dmi_plus = (indicators['adx'].get('values') or {}).get('plus_di', 0.0)
        dmi_minus = (indicators['adx'].get('values') or {}).get('minus_di', 0.0)
        is_trend_strong = adx_strength >= cfg['min_adx_strength']
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("ADX/DMI Filter", adx_ok, f"Trend strong/aligned check. (ADX: {adx_strength:.2f})")
        if not adx_ok: self._log_final_decision("HOLD", "ADX/DMI filter failed."); return None
        
        # ✅ NAN-GUARD: Ensure price and MA value are valid numbers.
        current_price = self.price_data.get('close')
        ma_value = (indicators['fast_ma'].get('values') or {}).get('ma_value')
        ma_filter_ok = True
        if pd.notna(current_price) and pd.notna(ma_value):
            ma_filter_ok = not ((signal_direction == "BUY" and current_price < ma_value) or (signal_direction == "SELL" and current_price > ma_value))
        else: ma_filter_ok = False # Fail if data is invalid
        self._log_criteria("Master Trend Filter", ma_filter_ok, "Price is on the wrong side of the master MA.")
        if not ma_filter_ok: self._log_final_decision("HOLD", "Master Trend filter failed."); return None
        
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'): htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Not aligned with HTF." if not htf_ok else "HTF is aligned.")
        if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
        
        # --- 3. Risk Management ---
        entry_price = self.price_data.get('close') # Already fetched and checked
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        trailing_stop_loss = (indicators['chandelier_exit'].get('values') or {}).get(stop_loss_key)

        # ✅ NAN-GUARD: Ensure stop loss is a valid number.
        if entry_price is None or trailing_stop_loss is None or not pd.notna(trailing_stop_loss):
            self._log_final_decision("HOLD", "Risk data missing or invalid (entry/SL)."); return None

        # ✅ ZERO-RISK SHIELD: Prevent signals with absurdly tight stops.
        risk_amount = abs(entry_price - trailing_stop_loss)
        min_risk_threshold = entry_price * (cfg.get('min_risk_pct', 0.1) / 100)
        if risk_amount < min_risk_threshold:
            self._log_final_decision("HOLD", f"Risk too tight ({risk_amount:.4f} < {min_risk_threshold:.4f}). Signal suppressed."); return None
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, trailing_stop_loss)
        tactical_tp1 = entry_price + (risk_amount * cfg['tactical_tp_rr_ratio']) if signal_direction == "BUY" else entry_price - (risk_amount * cfg['tactical_tp_rr_ratio'])
        risk_params['targets'] = [round(tactical_tp1, 5)]
        risk_params['risk_reward_ratio'] = round(abs(tactical_tp1 - entry_price) / risk_amount, 2) if risk_amount > 1e-9 else 0
        
        # --- 4. Final Decision ---
        def _fmt5(x): return f"{float(x):.5f}" if pd.notna(x) else "N/A"
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX > {cfg['min_adx_strength']:.1f} (Value: {adx_strength:.2f})",
            "trend_filter": "Price confirmed by Master MA",
            "htf_confirmation": "Confirmed by HTF Engine" if cfg.get('htf_confirmation_enabled') else "Disabled",
            "exit_management": f"Tactical TP1 + Chandelier Trailing SL at {_fmt5(trailing_stop_loss)}"
        }
        self._log_final_decision(signal_direction, "All criteria met. Adaptive Trend Rider signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
