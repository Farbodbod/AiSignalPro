# backend/engines/strategies/fib_structure.py (v4.0 - Defensive Logging Edition)

import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ConfluenceSniper(BaseStrategy):
    """
    ConfluenceSniper - (v4.0 - Defensive Logging Edition)
    -------------------------------------------------------------------
    This version integrates the professional logging system for full transparency
    and hardens the strategy against incomplete data to prevent crashes, while
    preserving the advanced Confluence Score engine.
    """
    strategy_name: str = "ConfluenceSniper"
    
    default_config = {
        "fib_levels_to_watch": ["61.8%", "78.6%"],
        "confluence_proximity_percent": 0.3,
        "min_confluence_score": 5,
        "weights": {
            "dual_oscillator": 3,
            "single_oscillator": 1,
            "candlestick": 2,
            "climactic_volume": 3
        },
        "volatility_regimes": {
            "low_atr_pct_threshold": 1.5,
            "low_vol_sl_multiplier": 1.2,
            "high_vol_sl_multiplier": 1.8
        },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 1,
            "adx": {"weight": 1, "min_strength": 25}
        }
    }

    def _calculate_confluence_score(self, direction: str, rsi_data: Dict, stoch_data: Dict, whales_data: Dict) -> tuple[int, List[str]]:
        # This helper's logic remains unchanged.
        weights = self.config.get('weights', {})
        score = 0
        confirmations = []

        rsi_confirm, stoch_confirm = self._get_oscillator_confirmation(direction, rsi_data, stoch_data)
        if rsi_confirm and stoch_confirm:
            score += weights.get('dual_oscillator', 3)
            confirmations.append("Dual Oscillator Confirmation")
        elif rsi_confirm or stoch_confirm:
            score += weights.get('single_oscillator', 1)
            confirmations.append("Single Oscillator Confirmation")
        
        if self._get_candlestick_confirmation(direction, min_reliability='Strong'):
            score += weights.get('candlestick', 2)
            confirmations.append("Strong Candlestick Pattern")
        
        if whales_data.get('analysis', {}).get('is_climactic_volume', False):
            score += weights.get('climactic_volume', 3)
            confirmations.append("Climactic Volume")
            
        return score, confirmations

    def _get_oscillator_confirmation(self, direction: str, rsi_data: Dict, stoch_data: Dict) -> tuple[bool, bool]:
        # This helper's logic remains unchanged.
        rsi_confirm, stoch_confirm = False, False
        rsi_val = rsi_data.get('values', {}).get('rsi')
        stoch_pos = stoch_data.get('analysis', {}).get('position')
        
        if rsi_val is not None:
            rsi_os, rsi_ob = rsi_data.get('levels', {}).get('oversold', 30), rsi_data.get('levels', {}).get('overbought', 70)
            if direction == "BUY" and rsi_val < rsi_os: rsi_confirm = True
            elif direction == "SELL" and rsi_val > rsi_ob: rsi_confirm = True

        if stoch_pos is not None:
            if direction == "BUY" and stoch_pos == 'Oversold': stoch_confirm = True
            elif direction == "SELL" and stoch_pos == 'Overbought': stoch_confirm = True
            
        return rsi_confirm, stoch_confirm

    def _find_best_prz(self, cfg: Dict, fib_data: Dict, structure_data: Dict) -> Optional[Dict]:
        current_price = self.price_data.get('close')
        if not current_price: return None

        # ✅ SAFEGUARD: Use the robust 'or {}' pattern to prevent crashes
        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_data.get('levels', []) if 'Retracement' in lvl.get('type', '')}
        structure_analysis = structure_data.get('analysis') or {}
        key_levels = structure_analysis.get('key_levels') or {}
        swing_trend = fib_data.get('swing_trend')
        
        target_sr_zones = key_levels.get('supports' if swing_trend == "Up" else 'resistances', [])
        confluence_zones = []
        for fib_level_str in cfg.get('fib_levels_to_watch', []):
            fib_price = fib_levels.get(fib_level_str)
            if not fib_price: continue
            for sr_zone in target_sr_zones:
                sr_price = sr_zone.get('price')
                if sr_price and abs(fib_price - sr_price) / sr_price * 100 < cfg.get('confluence_proximity_percent', 0.3):
                    zone_price = (fib_price + sr_price) / 2.0
                    confluence_zones.append({ "price": zone_price, "fib_level": fib_level_str, "structure_zone": sr_zone, "distance_to_price": abs(zone_price - current_price) })
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Data Availability Check ---
        required_names = ['fibonacci', 'structure', 'rsi', 'stochastic', 'atr', 'patterns', 'whales']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing_indicators = [name for name, data in indicators.items() if data is None]
        
        data_is_ok = not missing_indicators
        reason = f"Invalid/Missing indicators: {', '.join(missing_indicators)}" if not data_is_ok else "All required indicator data is valid."
        self._log_criteria("Data Availability", data_is_ok, reason)
        if not data_is_ok:
            self._log_final_decision("HOLD", reason)
            return None

        # --- 2. Primary Signal & Location Filter ---
        swing_trend = indicators['fibonacci'].get('swing_trend')
        direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        self._log_criteria("Primary Signal (Swing Trend)", direction is not None, f"No valid Up/Down swing trend found. (Trend: {swing_trend})")
        if not direction:
            self._log_final_decision("HOLD", "No primary trigger.")
            return None

        best_prz = self._find_best_prz(cfg, indicators['fibonacci'], indicators['structure'])
        self._log_criteria("Location Filter (PRZ Found)", best_prz is not None, "No confluence zone (PRZ) between Fibonacci and Structure found.")
        if not best_prz:
            self._log_final_decision("HOLD", "Location filter failed.")
            return None

        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low and price_low <= best_prz['price']) or \
                     (direction == "SELL" and price_high and price_high >= best_prz['price'])
        self._log_criteria("Location Filter (Price Test)", is_testing, "Price has not yet tested the identified PRZ.")
        if not is_testing:
            self._log_final_decision("HOLD", "Price test failed.")
            return None

        # --- 3. Confirmation Funnel (Confluence Scoring) ---
        confluence_score, score_details = self._calculate_confluence_score(direction, indicators['rsi'], indicators['stochastic'], indicators['whales'])
        min_score = cfg.get('min_confluence_score', 5)
        score_is_ok = confluence_score >= min_score
        self._log_criteria("Confluence Score Check", score_is_ok, f"Score of {confluence_score} is below minimum of {min_score}.")
        if not score_is_ok:
            self._log_final_decision("HOLD", "Confluence score is too low.")
            return None
        confirmations = {"confluence_score": confluence_score, "score_details": ", ".join(score_details)}
        
        htf_ok = True
        if cfg.get('htf_confirmation_enabled'):
            opposite_direction = "SELL" if direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
        self._log_criteria("HTF Filter", htf_ok, "A strong opposing trend was found on the higher timeframe.")
        if not htf_ok:
            self._log_final_decision("HOLD", "HTF filter failed.")
            return None
        confirmations['htf_filter'] = "Passed"

        # --- 4. Adaptive Risk Management ---
        entry_price = self.price_data.get('close')
        atr_data = indicators['atr']
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = atr_data.get('values', {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 1.2) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.8)
        
        atr_value = atr_data.get('values', {}).get('atr')
        structure_level = (best_prz.get('structure_zone') or {}).get('price')

        risk_data_ok = entry_price is not None and atr_value is not None and structure_level is not None
        self._log_criteria("Risk Data Availability", risk_data_ok, "Missing data for SL/TP calculation (entry/atr/structure_level).")
        if not risk_data_ok:
            self._log_final_decision("HOLD", "Risk data missing.")
            return None
        
        stop_loss = structure_level - (atr_value * atr_sl_multiplier) if direction == "BUY" else structure_level + (atr_value * atr_sl_multiplier)
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        
        risk_calc_ok = risk_params and risk_params.get("targets")
        self._log_criteria("Risk Calculation", risk_calc_ok, "Smart R/R calculation failed to produce targets.")
        if not risk_calc_ok:
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None
        confirmations['rr_check'] = f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"

        # --- 5. Final Decision ---
        self._log_final_decision(direction, "All criteria met. Confluence Sniper signal confirmed.")
        
        return { "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
