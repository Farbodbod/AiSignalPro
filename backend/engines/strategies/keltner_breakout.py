# backend/engines/strategies/keltner_breakout.py (v4.3 - The Final Patch)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v4.3 - The Final Patch)
    -------------------------------------------------------------------------
    This definitive version provides critical fixes for both logic and logging.
    It resolves the regression bug in the HTF dependency check and corrects the
    misleading/buggy logging in the risk management section, ensuring all
    outputs are reliable, accurate, and trustworthy.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        "min_momentum_score": 4,
        "weights": {
            "adx_strength": 2,
            "cci_thrust": 3,
            "htf_alignment": 2,
            "candlestick": 1
        },
        "adx_threshold": 25.0,
        "cci_threshold": 100.0,
        "candlestick_confirmation_enabled": True,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }
    
    def _calculate_momentum_score(self, direction: str, adx_data: Dict, cci_data: Dict) -> Tuple[int, List[str]]:
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        adx_strength = (adx_data.get('values') or {}).get('adx', 0.0)
        if adx_strength >= cfg.get('adx_threshold', 25.0):
            score += weights.get('adx_strength', 2)
            confirmations.append(f"ADX Strength ({adx_strength:.2f})")

        # Proactive fix: Ensure we use the correct key 'cci' from the indicator output.
        cci_value = (cci_data.get('values') or {}).get('cci', 0.0)
        cci_threshold = cfg.get('cci_threshold', 100.0)
        if (direction == "BUY" and cci_value > cci_threshold) or \
           (direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('cci_thrust', 3)
            confirmations.append(f"CCI Thrust ({cci_value:.2f})")
        
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(direction):
                score += weights.get('htf_alignment', 2)
                confirmations.append("HTF Aligned")

        if cfg.get('candlestick_confirmation_enabled'):
            if self._get_candlestick_confirmation(direction, min_reliability='Medium'):
                score += weights.get('candlestick', 1)
                confirmations.append("Candlestick Confirmed")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        # --- 1. Dynamic Data Availability Check ---
        required_names = ['keltner_channel', 'adx', 'cci', 'atr']
        if cfg.get('candlestick_confirmation_enabled'):
            required_names.append('patterns')

        # ✅ REGRESSION HOTFIX: Reverted to the correct, explicit logic for collecting HTF dependencies.
        if cfg.get('htf_confirmation_enabled'):
            htf_rules = cfg.get('htf_confirmations', {})
            # Explicitly check for known indicator names within the htf_rules dictionary.
            if "supertrend" in htf_rules: required_names.append('supertrend')
            if "adx" in htf_rules: required_names.append('adx')
        
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        data_is_ok = not missing
        self._log_criteria("Data Availability", data_is_ok, f"Invalid/Missing: {', '.join(missing)}" if not data_is_ok else "All required data is valid.")
        if not data_is_ok:
            self._log_final_decision("HOLD", "Indicators missing.")
            return None

        # --- 2. Primary Trigger (Keltner Channel Breakout) ---
        keltner_data = indicators['keltner_channel']
        keltner_pos = str((keltner_data.get('analysis') or {}).get('position', '')).lower()
        signal_direction = "BUY" if "breakout above" in keltner_pos else "SELL" if "breakdown below" in keltner_pos else None
        
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Keltner Breakout)", trigger_is_ok, f"Position: {keltner_pos.title()}")
        if not trigger_is_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        
        # --- 3. Qualification (Momentum Score) ---
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators['adx'], indicators['cci'])
        min_score = cfg.get('min_momentum_score', 4)
        score_is_ok = momentum_score >= min_score
        self._log_criteria("Momentum Score Check", score_is_ok, f"Score={momentum_score} vs min={min_score}")
        if not score_is_ok:
            self._log_final_decision("HOLD", "Momentum score is too low.")
            return None
        confirmations = {"power_score": momentum_score, "score_details": ", ".join(score_details)}

        # --- 4. Risk Management ---
        entry_price = self.price_data.get('close')
        stop_loss = (keltner_data.get('values') or {}).get('middle_band')

        # ✅ LOGGING FIX 1: Dynamic and accurate reason string.
        risk_data_ok = entry_price is not None and stop_loss is not None
        risk_data_reason = "Entry price and Keltner middle band (for SL) are available." if risk_data_ok else "Missing entry price or Keltner middle band."
        self._log_criteria("Risk Data Availability", risk_data_ok, risk_data_reason)
        if not risk_data_ok:
            self._log_final_decision("HOLD", "Risk data missing.")
            return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        # ✅ LOGGING FIX 2: Correct boolean casting and dynamic, accurate reason string.
        risk_calc_ok = bool(risk_params and risk_params.get("targets"))
        risk_calc_reason = f"Smart R/R calculation successful. R/R: {risk_params.get('risk_reward_ratio', 'N/A')}" if risk_calc_ok else "Smart R/R engine did not return valid targets."
        self._log_criteria("Risk Calculation", risk_calc_ok, risk_calc_reason)
        if not risk_calc_ok:
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. Keltner Momentum signal confirmed.")

        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
