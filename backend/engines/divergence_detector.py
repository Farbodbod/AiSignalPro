# backend/engines/strategies/divergence_sniper.py (v6.0 - Scoring Engine Upgrade)

import logging
from typing import Dict, Any, Optional, List, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperPro(BaseStrategy):
    """
    DivergenceSniperPro - (v6.0 - Scoring Engine Upgrade)
    -----------------------------------------------------------------------
    This version marks a major architectural evolution, replacing the rigid,
    all-or-nothing filter funnel with a sophisticated weighted "Scoring Engine".
    Each piece of evidence (Fortress S/R, Volume, Candlestick, etc.) now
    contributes to a final score. This provides immense flexibility, allowing the
    strategy to act on high-probability signals that might have been discarded
    due to a single minor unmet condition, transforming it into a more adaptive
    and intelligent reversal hunter.
    """
    strategy_name: str = "DivergenceSniperPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # ✅ ARCHITECTURAL UPGRADE (v6.0): New Scoring Engine
        "min_score": 7,
        "weights": {
            "fortress_sr": 3,
            "climactic_volume": 3,
            "candlestick": 2,
            "williams_r_trigger": 2,
            "htf_filter": 1
        },
        
        # --- Component Settings ---
        "min_structure_strength": 3,
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5,
            "low_vol_sl_multiplier": 1.0,
            "high_vol_sl_multiplier": 1.5
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }
    
    def _confirm_fortress_sr(self, direction: str, structure_data: Dict) -> Optional[Dict[str, Any]]:
        # This helper is unchanged and correct.
        min_strength = self.config.get("min_structure_strength", 3)
        prox_data = (structure_data.get('analysis') or {}).get('proximity') or {}
        
        zone_details = None
        if direction == "BUY":
            if prox_data.get('is_testing_support'):
                zone_details = prox_data.get('nearest_support_details')
        elif direction == "SELL":
            if prox_data.get('is_testing_resistance'):
                zone_details = prox_data.get('nearest_resistance_details')
        
        if (zone_details or {}).get('strength', 0) >= min_strength:
            return zone_details
        return None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Data Availability Check (Unchanged) ---
        required_names = ['divergence', 'structure', 'williams_r', 'atr', 'whales', 'patterns']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        data_is_ok = not missing_indicators
        self._log_criteria("Data Availability", data_is_ok, "All required indicator data is valid." if data_is_ok else f"Invalid/Missing: {', '.join(missing_indicators)}")
        if not data_is_ok:
            self._log_final_decision("HOLD", "Indicators missing.")
            return None

        # --- 2. Primary Signal (Unchanged) ---
        divergence_data = indicators['divergence'] or {}
        potential_signals = [s for s in (divergence_data.get('analysis', {}).get('signals') or []) if "Regular" in s.get('type', '')]
        primary_signal_ok = bool(potential_signals)
        self._log_criteria("Primary Signal", primary_signal_ok, "No valid Regular Divergence found.")
        if not primary_signal_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
        divergence = potential_signals[0]
        signal_direction = "BUY" if "Bullish" in divergence['type'] else "SELL"
        
        # --- 3. ✅ NEW: Confirmation Scoring Engine ---
        score = 0
        confirmations: Dict[str, Any] = {"divergence_type": divergence['type']}
        weights = cfg.get('weights', {})

        # Pillar 1: Fortress S/R
        fortress_zone = self._confirm_fortress_sr(signal_direction, indicators['structure'])
        fortress_ok = bool(fortress_zone)
        fortress_strength = (fortress_zone or {}).get('strength', 0)
        self._log_criteria("Score Check: Fortress S/R", fortress_ok, f"Passed (Zone Strength: {fortress_strength})" if fortress_ok else "Divergence not at strong S/R.")
        if fortress_ok:
            score += weights.get('fortress_sr', 0)
            confirmations['fortress_sr'] = f"Passed (Strength: {fortress_strength})"

        # Pillar 2: Climactic Volume
        volume_ok = (indicators.get('whales') or {}).get('analysis', {}).get('is_climactic_volume', False)
        self._log_criteria("Score Check: Volume", volume_ok, "Climactic volume confirmed." if volume_ok else "Climactic volume not found.")
        if volume_ok:
            score += weights.get('climactic_volume', 0)
            confirmations['climactic_volume'] = "Passed"

        # Pillar 3: HTF Filter
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite)
        self._log_criteria("Score Check: HTF Filter", htf_ok, "No strong opposing trend on HTF." if htf_ok else "Strong opposing trend on HTF.")
        if htf_ok:
            score += weights.get('htf_filter', 0)
            confirmations['htf_filter'] = "Passed"

        # Pillar 4: Candlestick Confirmation
        confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
        candlestick_ok = confirming_pattern is not None
        pattern_name = (confirming_pattern or {}).get('name', 'N/A')
        self._log_criteria("Score Check: Candlestick", candlestick_ok, f"Pattern: {pattern_name}" if candlestick_ok else "No strong reversal candle.")
        if candlestick_ok:
            score += weights.get('candlestick', 0)
            confirmations['candlestick'] = f"Passed ({pattern_name})"

        # Pillar 5: Williams %R Momentum Trigger
        wr_signal = str((indicators.get('williams_r') or {}).get('analysis', {}).get('crossover_signal', 'hold')).lower()
        trigger_fired = (signal_direction == "BUY" and "buy" in wr_signal) or (signal_direction == "SELL" and "sell" in wr_signal)
        self._log_criteria("Score Check: Momentum Trigger", trigger_fired, f"Williams %R confirmed ({wr_signal})." if trigger_fired else "No crossover confirmation.")
        if trigger_fired:
            score += weights.get('williams_r_trigger', 0)
            confirmations['williams_r_trigger'] = f"Passed ({wr_signal})"
        
        # --- Final Score Check ---
        min_score = cfg.get('min_score', 7)
        score_is_ok = score >= min_score
        self._log_criteria("Final Score", score_is_ok, f"Total Score: {score} >= Minimum: {min_score}")
        if not score_is_ok:
            self._log_final_decision("HOLD", f"Confirmation score {score} is below required {min_score}.")
            return None
        confirmations['final_score'] = f"{score}/{sum(weights.values())}"

        # --- 4. Adaptive Risk (Unchanged) ---
        entry_price = self.price_data.get('close')
        atr_data = indicators['atr'] or {}
        atr_pct = (atr_data.get('values') or {}).get('atr_percent', 2.0)
        atr_value = (atr_data.get('values') or {}).get('atr')
        pivots = divergence.get('pivots') or []
        pivot_price = pivots[1].get('price') if len(pivots) > 1 else None
        
        risk_data_ok = all(v is not None for v in [entry_price, pivot_price, atr_value, atr_pct])
        self._log_criteria("Risk Data Availability", risk_data_ok, "All risk inputs are valid." if risk_data_ok else "Missing entry/pivot/ATR for SL calculation.")
        if not risk_data_ok:
            self._log_final_decision("HOLD", "Risk data missing.")
            return None
        
        vol_cfg = cfg.get('volatility_regimes', {})
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_mult = vol_cfg.get('low_vol_sl_multiplier', 1.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.5)
        
        stop_loss = pivot_price - (atr_value * atr_sl_mult) if signal_direction == "BUY" else pivot_price + (atr_value * atr_sl_mult)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None
        confirmations['risk_management'] = "Passed"
        
        # --- 5. Final Decision (Unchanged) ---
        self._log_final_decision(signal_direction, "All filters passed. Divergence Sniper confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
