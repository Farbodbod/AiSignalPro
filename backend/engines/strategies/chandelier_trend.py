# backend/engines/strategies/chandelier_trend.py (v5.0 - Defensive Logging Edition)

import logging
import pandas as pd
from typing import Dict, Any, Optional

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v5.0 - Defensive Logging Edition)
    -------------------------------------------------------------------------
    This version integrates the new professional logging system for full
    transparency. It also makes the configuration loading more robust and
    preserves all unique session filtering and position sizing logic.
    """
    strategy_name: str = "ChandelierTrendRider"

    default_config = {
        # Added default_params structure for consistency and robustness
        "default_params": {
            "min_adx_strength": 25.0,
            "target_atr_multiples": [2.0, 4.0, 6.0],
            "risk_per_trade_percent": 0.01,
            "session_filter": {
                "enabled": True,
                "active_hours_utc": [[8, 16], [13, 21]]
            },
        },
        "timeframe_overrides": {}, # Placeholder for future adaptability
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }
    
    def _get_signal_config(self) -> Dict[str, Any]:
        """ Loads the hierarchical config based on the current timeframe. """
        # ✅ FIX: Made this logic robust and consistent with other strategies
        base_configs = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        return {**base_configs, **tf_overrides}

    def _is_in_active_session(self, cfg: Dict[str, Any]) -> bool:
        # This helper's logic remains unchanged.
        session_cfg = cfg.get('session_filter', {})
        if not session_cfg.get('enabled', False):
            return True

        if not self.price_data: return False
        candle_timestamp = self.price_data.get('timestamp')
        if not candle_timestamp: return False
        
        try:
            parsed_timestamp = pd.to_datetime(candle_timestamp, errors='raise')
            candle_hour = parsed_timestamp.hour
            active_windows = session_cfg.get('active_hours_utc', [])
            for window in active_windows:
                if len(window) == 2 and window[0] <= candle_hour < window[1]:
                    return True
            return False
        except Exception:
            logger.warning(f"[{self.strategy_name}] Could not parse candle timestamp '{candle_timestamp}' for session filter.")
            return False

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        
        # --- 1. Initial Sanity Checks ---
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        session_is_active = self._is_in_active_session(cfg)
        self._log_criteria("Session Filter", session_is_active, "Market is outside of active trading hours.")
        if not session_is_active:
            self._log_final_decision("HOLD", "Inactive session.")
            return None
            
        # --- 2. Data Availability Check ---
        required_names = ['supertrend', 'adx', 'chandelier_exit', 'bollinger', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 3. Confirmation Funnel ---
        squeeze_release_ok = indicators['bollinger']['analysis'].get('is_squeeze_release', False)
        self._log_criteria("Volatility Filter (Squeeze Release)", squeeze_release_ok, "No volatility expansion detected.")
        if not squeeze_release_ok:
            self._log_final_decision("HOLD", "Volatility filter failed.")
            return None
        
        st_signal = indicators['supertrend'].get('analysis', {}).get('signal')
        signal_direction = "BUY" if "Bullish Crossover" in st_signal else "SELL" if "Bearish Crossover" in st_signal else None
        self._log_criteria("Primary Trigger (SuperTrend)", signal_direction is not None, f"No valid SuperTrend crossover. (Signal: {st_signal})")
        if not signal_direction:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        
        adx_strength = indicators['adx'].get('values', {}).get('adx', 0)
        dmi_plus = indicators['adx'].get('values', {}).get('plus_di', 0)
        dmi_minus = indicators['adx'].get('values', {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= cfg.get('min_adx_strength', 25.0)
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or \
                           (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("ADX/DMI Filter", adx_ok, f"Trend is not strong enough or DMI is not aligned. (ADX: {adx_strength:.2f})")
        if not adx_ok:
            self._log_final_decision("HOLD", "ADX/DMI filter failed.")
            return None

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("HTF Filter", htf_ok, "Trend is not aligned with the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None

        # --- 4. Risk & Position Sizing ---
        entry_price = self.price_data.get('close')
        stop_loss_key = 'long_stop' if signal_direction == "BUY" else 'short_stop'
        stop_loss = indicators['chandelier_exit'].get('values', {}).get(stop_loss_key)
        
        if not all([entry_price, stop_loss]):
            self._log_final_decision("HOLD", "Could not determine Entry or Stop Loss.")
            return None

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        risk_calc_ok = risk_params and risk_params.get("targets")
        self._log_criteria("Risk Calculation", risk_calc_ok, "Could not calculate valid risk parameters (SL/TP).")
        if not risk_calc_ok:
            self._log_final_decision("HOLD", "Risk calculation failed.")
            return None
            
        account_equity = float(self.main_config.get("general", {}).get("account_equity", 10000))
        risk_per_trade = cfg.get("risk_per_trade_percent", 0.01)
        fees_pct = self.main_config.get("general", {}).get("assumed_fees_pct", 0.001)
        slippage_pct = self.main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        total_risk_per_unit = abs(entry_price - stop_loss) + (entry_price * fees_pct) + (entry_price * slippage_pct)
        position_size = (account_equity * risk_per_trade) / total_risk_per_unit if total_risk_per_unit > 0 else 0

        # --- 5. Final Decision ---
        confirmations = {
            "entry_trigger": "SuperTrend Crossover after Squeeze",
            "session": "Active",
            "adx_dmi_filter": f"Passed (ADX: {adx_strength:.2f})",
            "htf_filter": "Passed (HTF Aligned)"
        }
        self._log_final_decision(signal_direction, "All criteria met. Chandelier Trend Rider signal confirmed.")
        
        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            "position_size_units": round(position_size, 8),
            **risk_params,
            "confirmations": confirmations
        }
