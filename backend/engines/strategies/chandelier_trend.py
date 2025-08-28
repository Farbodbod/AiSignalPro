# backend/engines/strategies/chandelier_trend_rider.py (v6.0 - Scoring Engine Upgrade)

import logging
import pandas as pd
from typing import Dict, Any, Optional, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendRider(BaseStrategy):
    """
    ChandelierTrendRider - (v6.0 - Scoring Engine Upgrade)
    -------------------------------------------------------------------------
    This version marks a major architectural evolution, replacing the rigid,
    sequential checklist with a sophisticated weighted "Scoring Engine". Each
    flight condition (Session, Squeeze, SuperTrend, ADX, HTF) is now scored
    based on importance. This transforms the strategy into an intelligent pilot
    that can differentiate between "perfect" and "good enough" conditions,
    increasing its adaptability and opportunity-finding capabilities without
    sacrificing its core risk management principles.
    """
    strategy_name = "ChandelierTrendRider"

    default_config: ClassVar[Dict[str, Any]] = {
        # ✅ ARCHITECTURAL UPGRADE (v6.0): New Scoring Engine
        "min_score": 7,
        "weights": {
            "htf_alignment": 3,
            "adx_dmi": 3,
            "squeeze_release": 2,
            "supertrend_cross": 2,
            "active_session": 1
        },

        # --- Component Settings ---
        "session_filter_enabled": True,
        "active_hours_utc": [[8, 16], [13, 21]],
        "min_adx_strength": 25.0,
        "risk_per_trade_percent": 0.01,

        # --- Unchanged HTF Settings ---
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 22},
            "supertrend": {"weight": 1}
        }
    }
    
    # No __init__ is needed; it correctly inherits from BaseStrategy.
    
    def _get_signal_config(self) -> Dict[str, Any]:
        # This method is no longer needed as the config is flatter.
        # Kept for potential future use, but the main config is now used directly.
        return self.config.copy()

    def _is_in_active_session(self) -> bool:
        # This helper's logic is simplified to use the main config directly.
        session_cfg = self.config
        if not session_cfg.get('session_filter_enabled', False):
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
        cfg = self.config
        
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
            
        required_names = ['supertrend', 'adx', 'chandelier_exit', 'bollinger', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        data_is_ok = not missing_indicators
        self._log_criteria("Data Availability", data_is_ok, f"Invalid/Missing: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid.")
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 1. Primary Directional Trigger (SuperTrend Crossover) ---
        st_signal = (indicators['supertrend'].get('analysis') or {}).get('signal', '')
        signal_direction = "BUY" if "Bullish Crossover" in st_signal else "SELL" if "Bearish Crossover" in st_signal else None
        
        if not signal_direction:
            self._log_criteria("Primary Trigger", False, "No SuperTrend crossover found.")
            self._log_final_decision("HOLD", "No primary trigger to initiate scoring.")
            return None
        self._log_criteria("Primary Trigger", True, f"SuperTrend Crossover detected ({signal_direction}). Initiating scoring...")

        # --- 2. ✅ NEW: Confirmation Scoring Engine ---
        score = 0
        confirmations: Dict[str, Any] = {}
        weights = cfg.get('weights', {})

        # Add score for the trigger itself
        score += weights.get('supertrend_cross', 0)
        confirmations['supertrend_cross'] = "Passed"
        
        # Pillar 1: Active Session
        session_is_active = self._is_in_active_session()
        self._log_criteria("Score Check: Session Filter", session_is_active, "Session is active." if session_is_active else "Outside active hours.")
        if session_is_active:
            score += weights.get('active_session', 0)
            confirmations['active_session'] = "Passed"
        
        # Pillar 2: Volatility Filter (Squeeze Release)
        squeeze_release_ok = (indicators['bollinger'].get('analysis') or {}).get('is_squeeze_release', False)
        self._log_criteria("Score Check: Squeeze Release", squeeze_release_ok, "Volatility expansion detected." if squeeze_release_ok else "No volatility expansion.")
        if squeeze_release_ok:
            score += weights.get('squeeze_release', 0)
            confirmations['squeeze_release'] = "Passed"
        
        # Pillar 3: ADX/DMI Filter
        adx_strength = (indicators['adx'].get('values') or {}).get('adx', 0)
        dmi_plus = (indicators['adx'].get('values') or {}).get('plus_di', 0)
        dmi_minus = (indicators['adx'].get('values') or {}).get('minus_di', 0)
        is_trend_strong = adx_strength >= cfg.get('min_adx_strength', 25.0)
        is_dir_confirmed = (signal_direction == "BUY" and dmi_plus > dmi_minus) or (signal_direction == "SELL" and dmi_minus > dmi_plus)
        adx_ok = is_trend_strong and is_dir_confirmed
        self._log_criteria("Score Check: ADX/DMI", adx_ok, f"Trend strong and aligned (ADX: {adx_strength:.2f})." if adx_ok else f"Trend weak or DMI not aligned (ADX: {adx_strength:.2f}).")
        if adx_ok:
            score += weights.get('adx_dmi', 0)
            confirmations['adx_dmi'] = f"Passed (ADX: {adx_strength:.2f})"
        
        # Pillar 4: HTF Filter
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            htf_ok = self._get_trend_confirmation(signal_direction)
        self._log_criteria("Score Check: HTF Alignment", htf_ok, "Aligned with HTF." if htf_ok else "Not aligned with HTF.")
        if htf_ok:
            score += weights.get('htf_alignment', 0)
            confirmations['htf_alignment'] = "Passed"

        # --- Final Score Check ---
        min_score = cfg.get('min_score', 7)
        score_is_ok = score >= min_score
        self._log_criteria("Final Score", score_is_ok, f"Total Score: {score} >= Minimum: {min_score}")
        if not score_is_ok:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below required {min_score}.")
            return None
        confirmations['final_score'] = f"{score}/{sum(weights.values())}"

        # --- 3. Risk Management & Position Sizing (Unchanged) ---
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

        self._log_final_decision(signal_direction, "All criteria met. Chandelier Trend Rider signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, "position_size_units": round(position_size, 8), **risk_params, "confirmations": confirmations}
