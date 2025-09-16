# backend/engines/strategies/range_hunter.py (v3.2 - The Squeeze Logic Patch)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class RangeHunterPro(BaseStrategy):
    """
    RangeHunterPro - (v3.2 - The Squeeze Logic Patch)
    -------------------------------------------------------------------------
    This version applies a critical hotfix to resolve a Data Contract Mismatch.
    The strategy no longer requests a non-existent 'bbw_quantile_value' from the
    Bollinger indicator. Instead, it now correctly uses the intelligent
    'is_in_squeeze' boolean provided by the indicator, perfectly aligning the
    strategy's logic with the indicator's actual capabilities and resolving
    the persistent "volatility too high" error.
    """
    strategy_name: str = "RangeHunterPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "regime_filter": {
            "enabled": True,
            "max_adx_percentile_for_range": 45.0,
            # ✅ FIX: bbw_quantile is removed as it's not used.
            "bbw_squeeze_enabled": True 
        },
        "confirmation_scoring": {
            "min_score": 5,
            "weights": {
                "rsi_reversal": 3,
                "stochastic_reversal": 2,
                "candlestick_strong": 3,
                "candlestick_medium": 2
            },
            "rsi_oversold_entry": 40.0,
            "rsi_overbought_entry": 60.0
        },
        "override_min_rr_ratio": 1.2
    }

    def _calculate_confirmation_score(self, direction: str, cfg: Dict, indicators: Dict) -> Tuple[int, List[str]]:
        # This function remains unchanged
        weights, score, confirmations = cfg.get('weights', {}), 0, []
        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        stoch_pos = self._safe_get(indicators, ['stochastic', 'analysis', 'position'], "")
        rsi_ok = (direction == "BUY" and rsi_val <= cfg.get('rsi_oversold_entry', 40.0)) or \
                 (direction == "SELL" and rsi_val >= cfg.get('rsi_overbought_entry', 60.0))
        if rsi_ok:
            score += weights.get('rsi_reversal', 3); confirmations.append("RSI Reversal")
        stoch_ok = (direction == "BUY" and "Oversold" in stoch_pos) or \
                   (direction == "SELL" and "Overbought" in stoch_pos)
        if stoch_ok:
            score += weights.get('stochastic_reversal', 2); confirmations.append("Stochastic Reversal")
        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        if confirming_pattern:
            reliability = (confirming_pattern.get('reliability') or '').capitalize()
            pattern_name = confirming_pattern.get('name', 'Unknown Pattern')
            if reliability == 'Strong':
                score += weights.get('candlestick_strong', 3); confirmations.append(f"Strong Candlestick ({pattern_name})")
            elif reliability == 'Medium':
                score += weights.get('candlestick_medium', 2); confirmations.append(f"Medium Candlestick ({pattern_name})")
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        required_names = ['bollinger', 'adx', 'rsi', 'atr', 'stochastic', 'patterns', 'structure', 'pivots']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None or not data.get('values') for data in indicators.values()):
            self._log_criteria("Data Availability", False, "One or more required indicators are missing/invalid.")
            return None

        # --- 1. Redefined Battlefield ---
        regime_cfg = cfg.get('regime_filter', {})
        if regime_cfg.get('enabled'):
            adx_percentile = self._safe_get(indicators, ['adx', 'analysis', 'adx_percentile'], 100.0)
            if adx_percentile > regime_cfg.get('max_adx_percentile_for_range', 45.0):
                self._log_final_decision("HOLD", f"Market is not ranging (ADX Percentile={adx_percentile:.2f}).")
                return None
            self._log_criteria("ADX Ranging Filter", True, f"ADX % is {adx_percentile:.2f}")

            # ✅ SURGICAL FIX: Use the 'is_in_squeeze' boolean that the indicator actually provides.
            if regime_cfg.get('bbw_squeeze_enabled'):
                is_in_squeeze = self._safe_get(indicators, ['bollinger', 'analysis', 'is_in_squeeze'], False)
                if not is_in_squeeze:
                    self._log_final_decision("HOLD", "Market volatility is too high (Bollinger Bands are not in a squeeze).")
                    return None
                self._log_criteria("Bollinger Squeeze Filter", True, "Market is in a low-volatility squeeze.")
        
        # --- 2. Primary Trigger (Price at Band) ---
        bollinger_values = indicators['bollinger']['values']
        upper_band, lower_band = bollinger_values.get('upper_band'), bollinger_values.get('lower_band')
        if not self._is_valid_number(upper_band, lower_band):
            self._log_final_decision("HOLD", "Bollinger Bands not available."); return None
        signal_direction = None
        if self.price_data.get('low') <= lower_band: signal_direction = "BUY"
        elif self.price_data.get('high') >= upper_band: signal_direction = "SELL"
        if not signal_direction: self._log_final_decision("HOLD", "Price is not at an extreme of the range."); return None
        self._log_criteria("Price at Band", True, f"Price touched {'LOWER' if signal_direction == 'BUY' else 'UPPER'} band.")

        # --- 3. Evolved Trigger Squad (Scoring Engine) ---
        scoring_cfg = cfg.get('confirmation_scoring', {})
        score, details = self._calculate_confirmation_score(signal_direction, scoring_cfg, indicators)
        min_score = scoring_cfg.get('min_score', 5)
        if score < min_score:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below minimum of {min_score}.")
            return None
        self._log_criteria("Confirmation Score", True, f"Score={score} vs min={min_score}. Details: {', '.join(details)}")

        # --- 4. Harmonized Arsenal (OHRE v3.0) ---
        entry_price = self.price_data.get('close')
        if not self._is_valid_number(entry_price) or entry_price <= 0:
            self._log_final_decision("HOLD", f"Invalid entry price: {entry_price}."); return None
        self.config['override_min_rr_ratio'] = cfg.get('override_min_rr_ratio', 1.2)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE v3.0 failed to generate a valid risk plan."); return None
        
        # --- 5. Final Decision ---
        confirmations = {
            "market_regime": "RANGING (ADX/BBW Squeeze Confirmed)",
            "final_score": score,
            "entry_triggers": ", ".join(details),
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Range Hunter Pro signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

