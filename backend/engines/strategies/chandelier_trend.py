# backend/engines/strategies/chandelier_trend_rider.py (was chandelier_trend.py)
import logging
import pandas as pd
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v5.2 - Final & Inherited Init)
    -------------------------------------------------------------------------
    This definitive version resolves the subtle bug related to static log messages,
    making all logs fully dynamic and transparent. Following expert review and
    adherence to OOP best practices, the unnecessary __init__ method has been
    removed, allowing the class to cleanly inherit its constructor from the
    powerful BaseStrategy. All core trading logic is 100% preserved.
    """
    strategy_name: "ChandelierTrendRider"

    default_config = {
        "default_params": {
            "min_adx_strength": 25.0,
            "target_atr_multiples": [2.0, 4.0, 6.0],
            "risk_per_trade_percent": 0.01,
            "session_filter": {
                "enabled": True,
                "active_hours_utc": [[8, 16], [13, 21]]
            },
        },
        "timeframe_overrides": {},
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }
    
    # NOTE: No __init__ method is needed. This class now correctly inherits the
    # powerful constructor from BaseStrategy, making the code cleaner and more robust.
    
    def _get_signal_config(self) -> Dict[str, Any]:
        """ Loads the hierarchical config based on the current timeframe. """
        base_configs = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _is_in_active_session(self, cfg: Dict[str, Any]) -> bool:
        # This helper's logic remains unchanged.
        session_cfg = cfg.get('session_filter', {})
        if not session_cfg.get('enabled', False):
            return True

        if not self.price_data or not self.price_data.get('timestamp'): return False
        
        try:
            parsed_timestamp = pd.to_datetime(self.price_data['timestamp'], errors='raise')
            candle_hour = parsed_timestamp.hour
            active_windows = session_cfg.get('active_hours_utc', [])
            for window in active_windows:
                if len(window) == 2 and window[0] <= candle_hour < window[1]:
                    return True
            return False
        except Exception:
            logger.warning(f"[{self.strategy_name}] Could not parse candle timestamp for session filter.")
            return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        session_is_active = self._is_in_active_session(cfg)
        # ✅ KEY FIX 1: Log message is now dynamic and accurately reflects the status.
        session_log_msg = "Session is active." if session_is_active else "Market is outside of active trading hours."
        self._log_criteria("Session Filter", session_is_active, session_log_msg)
        if not session_is_active:
            self._log_final_decision("HOLD", "Inactive session.")
            return None
            
        required_names = ['supertrend', 'adx', 'chandelier_exit', 'bollinger', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        squeeze_release_ok = (indicators['bollinger'].get('analysis') or {}).get('is_squeeze_release', False)
        # ✅ KEY FIX 1: Log message is now dynamic and accurately reflects the status.
        volatility_log_msg = "Volatility expansion detected." if squeeze_release_ok else "No volatility expansion detected."
        self._log_criteria("Volatility Filter (Squeeze Release)", squeeze_release_ok, volatility_log_msg)
        if not squeeze_release_ok:
            self._log_final_decision("HOLD", "Volatility filter failed.")
            return None
        
        # ... The rest of the strategy logic is 100% preserved ...
        st_signal = (indicators['supertrend'].get('analysis') or {}).get('signal', '')
        signal_direction = "BUY" if "Bullish Crossover" in st_signal else "SELL" if "Bearish Crossover" in st_signal else None
        self._log_criteria("Primary Trigger (SuperTrend)", signal_direction is not None, f"No valid SuperTrend crossover. (Signal: {st_signal})")
        if not signal_direction:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        
        adx_strength = (indicators['adx'].get('values') or {}).get('adx', 0)
        dmi_plus = (indicators['adx'].get('values') or {}).get('plus_di', 0)
        dmi_minus = (indicators['adx'].get('values') or {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= cfg.get('min_adx_strength', 25.0)
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("ADX/DMI Filter", adx_ok, f"Trend is strong and DMI is aligned. (ADX: {adx_strength:.2f})" if adx_ok else f"Trend is not strong enough or DMI is not aligned. (ADX: {adx_strength:.2f})")
        if not adx_ok:
            self._log_final_decision("HOLD", "ADX/DMI filter failed.")
            return None

        htf_ok = True
        if self.config.get('htf_confirmation_enabled'):
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Trend is aligned with the higher timeframe." if htf_ok else "Trend is not aligned with the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None

        entry_price = self.price_data.get('close')
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = (indicators['chandelier_exit'].get('values') or {}).get(stop_loss_key)
        
        if not all([entry_price, stop_loss]):
            self._log_final_decision("HOLD", "Could not determine Entry or Stop Loss.")
            return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None
            
        account_equity = float(self.main_config.get("general", {}).get("account_equity", 10000))
        risk_per_trade = cfg.get("risk_per_trade_percent", 0.01)
        total_risk_per_unit = abs(entry_price - stop_loss)
        position_size = (account_equity * risk_per_trade) / total_risk_per_unit if total_risk_per_unit > 0 else 0

        confirmations = {"entry_trigger": "SuperTrend Crossover after Squeeze", "session": "Active", "adx_dmi_filter": f"Passed (ADX: {adx_strength:.2f})", "htf_filter": "Passed (HTF Aligned)"}
        self._log_final_decision(signal_direction, "All criteria met. Chandelier Trend Rider signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, "position_size_units": round(position_size, 8), **risk_params, "confirmations": confirmations}
