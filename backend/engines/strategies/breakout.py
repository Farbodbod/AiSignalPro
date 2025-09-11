# backend/engines/strategies/breakout_hunter.py (v5.0 - The OHRE v3.0 Harmonization)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutHunter(BaseStrategy):
    """
    BreakoutHunter - (v5.0 - The OHRE v3.0 Harmonization)
    ----------------------------------------------------------------
    This is a major architectural overhaul to fully align the strategy with the
    BaseStrategy v25.0 and its OHRE v3.0 engine.

    🚀 KEY EVOLUTIONS in v5.0:
    1.  **Full OHRE v3.0 Integration:** The complex, multi-step custom risk management
        logic has been completely replaced with a single, clean call to the new
        `_orchestrate_static_risk` engine.
    2.  **Dynamic R:R Preservation:** The strategy's unique intelligence of requiring a
        higher R:R for lower-quality signals has been preserved and integrated
        with the OHRE engine via the `override_min_rr_ratio` feature.
    3.  **Adaptive HTF Engine:** The HTF confirmation logic has been upgraded to use
        ADX percentiles, making it more robust and context-aware.
    """
    strategy_name: str = "BreakoutHunter"

    # --- Default config updated for new architecture ---
    default_config: ClassVar[Dict[str, Any]] = {
        "min_breakout_score": 6,
        # NOTE: rr_requirements is now deprecated. The logic is preserved in the code.
        "rr_config": { "low_score_threshold": 7, "high_rr": 2.5, "default_rr": 1.5 },
        "weights": {
            "squeeze_release": 3,
            "volume_catalyst": 3,
            "momentum_thrust": 2,
            "htf_alignment": 2
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        # ✅ UPGRADED: HTF ADX now uses percentiles
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_percentile": 75.0},
            "supertrend": {"weight": 1}
        }
    }

    def _calculate_breakout_score(self, signal_direction: str, indicators: Dict) -> Tuple[int, List[str]]:
        # This internal calculation logic remains unchanged.
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        if self._safe_get(indicators, ['Bollinger', 'analysis', 'is_squeeze_release']):
            score += weights.get('squeeze_release', 3)
            confirmations.append("Volatility Squeeze Release")
        
        whales_analysis = self._safe_get(indicators, ['Whales', 'analysis'], {})
        if whales_analysis.get('is_whale_activity'):
            whale_pressure = whales_analysis.get('pressure', '')
            if (signal_direction == "BUY" and "Buying" in whale_pressure) or \
               (signal_direction == "SELL" and "Selling" in whale_pressure):
                score += weights.get('volume_catalyst', 3)
                confirmations.append("Whale Volume Catalyst")

        cci_threshold = cfg.get('cci_threshold', 100.0)
        cci_value = self._safe_get(indicators, ['CCI', 'values', 'cci'], 0)
        if (signal_direction == "BUY" and cci_value > cci_threshold) or \
           (signal_direction == "SELL" and cci_value < -cci_threshold):
            score += weights.get('momentum_thrust', 2)
            confirmations.append(f"Momentum Thrust (CCI: {cci_value:.2f})")
            
        if cfg.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(signal_direction):
                score += weights.get('htf_alignment', 2)
                confirmations.append(f"HTF Trend Aligned")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        # --- 1. Data Gathering & Availability Check (Upgraded for OHRE v3.0) ---
        required_names = ['donchian_channel', 'bollinger', 'whales', 'cci', 'atr', 'structure', 'pivots', 'adx']
        
        indicators = {name: self.get_indicator(name) for name in required_names}
        
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            reason = f"Missing required indicators: {', '.join(missing_indicators)}"
            self._log_criteria("Data Availability", False, reason)
            self._log_final_decision("HOLD", reason)
            return None
        self._log_criteria("Data Availability", True, "All required indicator data is present.")

        # --- 2. Primary Trigger (Donchian Channel Breakout) ---
        donchian_signal = self._safe_get(indicators, ["donchian_channel", 'analysis', 'signal'])
        signal_direction = "BUY" if "Buy" in str(donchian_signal) else "SELL" if "Sell" in str(donchian_signal) else None
        
        self._log_criteria("Primary Trigger (Donchian)", signal_direction is not None, 
                           f"No valid breakout signal from Donchian Channel. (Signal: {donchian_signal})")

        if not signal_direction:
            self._log_final_decision("HOLD", "No Donchian breakout trigger found.")
            return None
        
        # --- 3. Breakout Quality Scoring ---
        breakout_score, score_details = self._calculate_breakout_score(signal_direction, indicators["bollinger"], indicators["whales"], indicators["cci"])
        min_score = cfg.get('min_breakout_score', 6)
        score_is_ok = breakout_score >= min_score

        self._log_criteria("Breakout Score Check", score_is_ok, 
                           f"Score of {breakout_score} is below minimum of {min_score}.")
        
        if not score_is_ok:
            self._log_final_decision("HOLD", "Breakout power score is too low.")
            return None
            
        # --- 4. Risk Management (✅ UPGRADED to OHRE v3.0) ---
        entry_price = self.price_data.get('close')
        if not self._is_valid_number(entry_price) or entry_price <= 0:
            self._log_final_decision("HOLD", f"Could not determine a valid entry price: {entry_price}.")
            return None
        
        # Preserve the strategy's unique dynamic R:R logic
        rr_reqs = cfg.get('rr_config', {})
        rr_needed = rr_reqs.get('high_rr', 2.5) if breakout_score < rr_reqs.get('low_score_threshold', 7) else rr_reqs.get('default_rr', 1.5)
        self.config['override_min_rr_ratio'] = rr_needed
        
        # Delegate fully to the OHRE v3.0
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction,
            entry_price=entry_price
        )
        
        # Clean up the temporary override
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params:
            self._log_final_decision("HOLD", f"OHRE v3.0 failed to generate a valid risk plan (min R:R needed: {rr_needed}).")
            return None

        # --- 5. Final Decision ---
        confirmations = {
            "power_score": breakout_score, 
            "score_details": ", ".join(score_details),
            "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')}, Required: {rr_needed})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0")
        }
        
        self._log_final_decision(signal_direction, "All criteria met. Breakout Hunter signal confirmed.")

        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
