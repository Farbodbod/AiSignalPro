# backend/engines/strategies/divergence_sniper.py (v4.0 - Defensive Logging Edition)

import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperPro(BaseStrategy):
    """
    DivergenceSniperPro - (v4.0 - Defensive Logging Edition)
    -----------------------------------------------------------------------
    This version integrates the professional logging system for full transparency
    into its three-pillar confirmation engine. It is also hardened against
    incomplete data to prevent crashes.
    """
    strategy_name: str = "DivergenceSniperPro"

    default_config = {
        "volume_confirmation_enabled": True,
        "candlestick_confirmation_enabled": True,
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
        """ Confirms the divergence is at a high-strength, tested S/R zone. """
        min_strength = self.config.get("min_structure_strength", 3)
        
        # ✅ SAFEGUARD: Use the robust 'or {}' pattern to prevent crashes
        analysis_block = structure_data.get('analysis') or {}
        prox_data = analysis_block.get('proximity') or {}
        
        zone_details = None
        if direction == "BUY":
            if prox_data.get('is_testing_support'):
                zone_details = prox_data.get('nearest_support_details')
        elif direction == "SELL":
            if prox_data.get('is_testing_resistance'):
                zone_details = prox_data.get('nearest_resistance_details')
        
        if zone_details and zone_details.get('strength', 0) >= min_strength:
            return zone_details
        return None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None
        
        # --- 1. Data Availability Check ---
        required_names = ['divergence', 'structure', 'williams_r', 'atr', 'whales', 'patterns']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Primary Signal (Find a Valid Divergence) ---
        divergence_data = indicators['divergence']
        potential_signals = [s for s in divergence_data.get('analysis', {}).get('signals', []) if "Regular" in s.get('type', '')]
        
        primary_signal_ok = bool(potential_signals)
        self._log_criteria("Primary Signal (Divergence)", primary_signal_ok, "No valid Regular Divergence found.")
        if not primary_signal_ok:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None
            
        divergence = potential_signals[0]
        signal_direction = "BUY" if "Bullish" in divergence['type'] else "SELL"
        confirmations = {"divergence_type": divergence['type']}

        # --- 3. Confirmation Funnel ---
        fortress_zone = self._confirm_fortress_sr(signal_direction, indicators['structure'])
        self._log_criteria("Pillar 1: Fortress S/R", fortress_zone is not None, "Divergence is not at a strong, tested S/R zone.")
        if not fortress_zone:
            self._log_final_decision("HOLD", "Fortress S/R filter failed.")
            return None
        confirmations['structure_filter'] = f"Passed (Zone Strength: {fortress_zone.get('strength')})"
        
        volume_ok = True
        if cfg.get('volume_confirmation_enabled'):
            volume_ok = indicators['whales']['analysis'].get('is_climactic_volume', False)
        self._log_criteria("Pillar 2: Climactic Volume", volume_ok, "Trend exhaustion not confirmed by climactic volume.")
        if not volume_ok:
            self._log_final_decision("HOLD", "Volume filter failed.")
            return None
        confirmations['volume_filter'] = "Passed"

        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed"

        candlestick_ok = True
        if cfg.get('candlestick_confirmation_enabled'):
            confirming_pattern = self._get_candlestick_confirmation(signal_direction, min_reliability='Strong')
            candlestick_ok = confirming_pattern is not None
            if candlestick_ok: confirmations['candlestick_filter'] = f"Passed (Pattern: {confirming_pattern.get('name')})"
        self._log_criteria("Candlestick Filter", candlestick_ok, "No strong reversal candlestick pattern found.")
        if not candlestick_ok:
            self._log_final_decision("HOLD", "Candlestick filter failed.")
            return None
        
        wr_signal = indicators['williams_r'].get('analysis', {}).get('crossover_signal', 'Hold')
        trigger_fired = (signal_direction == "BUY" and "Buy" in wr_signal) or (signal_direction == "SELL" and "Sell" in wr_signal)
        self._log_criteria("Momentum Trigger (Williams %R)", trigger_fired, "Williams %R did not confirm with a crossover.")
        if not trigger_fired:
            self._log_final_decision("HOLD", "Final momentum trigger failed.")
            return None
        confirmations['momentum_trigger'] = "Passed"
        
        # --- 4. Adaptive Risk Management ---
        entry_price = self.price_data.get('close')
        atr_data = indicators['atr']
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = atr_data.get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 1.0) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.5)
        confirmations['volatility_context'] = f"Adaptive SL Multiplier: x{atr_sl_multiplier} ({'Low' if is_low_vol else 'High'} Vol)"
        
        pivot_price = divergence.get('pivots', [{}, {}])[1].get('price')
        atr_value = atr_data.get('values', {}).get('atr')

        risk_data_ok = entry_price is not None and pivot_price is not None and atr_value is not None
        self._log_criteria("Risk Data Availability", risk_data_ok, "Missing data for SL/TP calculation (entry/pivot/atr).")
        if not risk_data_ok:
            self._log_final_decision("HOLD", "Risk calculation data missing.")
            return None
        
        stop_loss = pivot_price - (atr_value * atr_sl_multiplier) if signal_direction == "BUY" else pivot_price + (atr_value * atr_sl_multiplier)
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        
        risk_calc_ok = risk_params and risk_params.get("targets")
        self._log_criteria("Risk Calculation", risk_calc_ok, "Smart R/R calculation failed to produce targets.")
        if not risk_calc_ok:
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None
        
        # --- 5. Final Decision ---
        self._log_final_decision(signal_direction, "All criteria met. Divergence Sniper signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

