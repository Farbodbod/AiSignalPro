# strategies/breakout_hunter.py (v4.1 - Enhanced Logging Edition)

import logging
from typing import Dict, Any, Optional, List, Tuple

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutHunter(BaseStrategy):
    """
    BreakoutHunter - (v4.1 - Enhanced Logging Edition)
    ----------------------------------------------------------------
    This version integrates the new logging mechanism from BaseStrategy for
    transparent, step-by-step decision tracking.
    """
    strategy_name: str = "BreakoutHunter"

    default_config = {
        "min_breakout_score": 6,
        "rr_requirements": { "low_score_threshold": 7, "high_rr": 2.5, "default_rr": 1.5 },
        "weights": {
            "squeeze_release": 3,
            "volume_catalyst": 3,
            "momentum_thrust": 2,
            "htf_alignment": 2
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_strength": 25},
            "supertrend": {"weight": 1}
        }
    }

    def _calculate_breakout_score(self, signal_direction: str, bollinger_data: Dict, whales_data: Dict, cci_data: Dict) -> Tuple[int, List[str]]:
        """
        The Breakout Power Score Engine. (This internal calculation logic remains unchanged).
        """
        cfg = self.config
        weights = cfg.get('weights', {})
        score = 0
        confirmations = []

        if bollinger_data['analysis'].get('is_squeeze_release'):
            score += weights.get('squeeze_release', 3)
            confirmations.append("Volatility Squeeze Release")
        
        if whales_data['analysis'].get('is_whale_activity'):
            whale_pressure = whales_data['analysis'].get('pressure', '')
            if (signal_direction == "BUY" and "Buying" in whale_pressure) or \
               (signal_direction == "SELL" and "Selling" in whale_pressure):
                score += weights.get('volume_catalyst', 3)
                confirmations.append("Whale Volume Catalyst")

        cci_threshold = cfg.get('cci_threshold', 100.0)
        cci_value = cci_data.get('values', {}).get('value', 0)
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
        
        # --- 1. Data Gathering & Availability Check ---
        donchian_data = self.get_indicator('donchian_channel')
        bollinger_data = self.get_indicator('bollinger')
        whales_data = self.get_indicator('whales')
        cci_data = self.get_indicator('cci')
        atr_data = self.get_indicator('atr')

        # Log data availability checks for critical indicators
        self._log_criteria("Data Availability", all([donchian_data, bollinger_data, whales_data, cci_data, atr_data]), 
                           "One or more required indicators are missing.")
        
        if not all([donchian_data, bollinger_data, whales_data, cci_data, atr_data]):
            self._log_final_decision("HOLD", "Required indicator data is missing.")
            return None

        # --- 2. Primary Trigger (Donchian Channel Breakout) ---
        donchian_signal = donchian_data.get('analysis', {}).get('signal')
        signal_direction = "BUY" if "Buy" in donchian_signal else "SELL" if "Sell" in donchian_signal else None
        
        self._log_criteria("Primary Trigger (Donchian)", signal_direction is not None, 
                           f"No valid breakout signal from Donchian Channel. (Signal: {donchian_signal})")

        if not signal_direction:
            self._log_final_decision("HOLD", "No Donchian breakout trigger found.")
            return None
        
        # --- 3. Breakout Quality Scoring ---
        breakout_score, score_details = self._calculate_breakout_score(signal_direction, bollinger_data, whales_data, cci_data)
        min_score = cfg.get('min_breakout_score', 6)
        score_is_ok = breakout_score >= min_score

        self._log_criteria("Breakout Score Check", score_is_ok, 
                           f"Score of {breakout_score} is below minimum of {min_score}.")
        
        if not score_is_ok:
            self._log_final_decision("HOLD", "Breakout power score is too low.")
            return None
            
        confirmations = {"power_score": breakout_score, "score_details": ", ".join(score_details)}
        
        # --- 4. Risk Management & R/R Validation ---
        entry_price = self.price_data.get('close')
        if not entry_price:
            self._log_final_decision("HOLD", "Could not determine entry price.")
            return None
        
        stop_loss = donchian_data.get('values', {}).get('middle_band')
        sl_source = "Donchian Middle Band"
        if not stop_loss:
            atr_value = atr_data.get('values', {}).get('atr', entry_price * 0.02)
            stop_loss = entry_price - (atr_value * 2) if signal_direction == "BUY" else entry_price + (atr_value * 2)
            sl_source = "ATR Fallback"

        self._log_criteria("Stop Loss Calculation", stop_loss is not None, f"SL determined via {sl_source} at {stop_loss:.5f}")

        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        rr_reqs = cfg.get('rr_requirements', {})
        # Dynamic R/R requirement based on score quality
        min_rr_ratio = rr_reqs.get('high_rr', 2.5) if breakout_score < rr_reqs.get('low_score_threshold', 7) else rr_reqs.get('default_rr', 1.5)
        
        calculated_rr = risk_params.get("risk_reward_ratio", 0) if risk_params else 0
        rr_is_ok = calculated_rr >= min_rr_ratio

        self._log_criteria("Risk/Reward Check", rr_is_ok, 
                           f"Failed R/R check. (Calculated: {calculated_rr}, Required: {min_rr_ratio})")
        
        if not rr_is_ok:
            self._log_final_decision("HOLD", "Risk/Reward ratio is too low.")
            return None

        confirmations['rr_check'] = f"Passed (R/R: {calculated_rr}, Required: {min_rr_ratio})"
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. Breakout Hunter signal confirmed.")

        return {
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
