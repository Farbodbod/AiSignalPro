# backend/engines/strategies/fib_structure.py (v4.2 - The Glass Box Edition)

import logging
from typing import Dict, Any, Optional, List, ClassVar, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ConfluenceSniper(BaseStrategy):
    """
    ConfluenceSniper - (v4.2 - The Glass Box Edition)
    -------------------------------------------------------------------
    This version transforms the strategy into a "glass box" by implementing
    high-fidelity logging for its core PRZ detection logic. It now provides
    detailed reasons for both successful and failed PRZ checks, offering
    unprecedented transparency for debugging and optimization, while preserving
    all original trading logic.
    """
    strategy_name: str = "ConfluenceSniper"
    
    default_config: ClassVar[Dict[str, Any]] = {
        "fib_levels_to_watch": ["61.8%", "78.6%"],
        "confluence_proximity_percent": 0.3,
        "min_confluence_score": 5,
        "weights": { "dual_oscillator": 3, "single_oscillator": 1, "candlestick": 2, "climactic_volume": 3 },
        "volatility_regimes": { "low_atr_pct_threshold": 1.5, "low_vol_sl_multiplier": 1.2, "high_vol_sl_multiplier": 1.8 },
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { "min_required_score": 1, "adx": {"weight": 1, "min_strength": 25} }
    }

    def _calculate_confluence_score(self, direction: str, rsi_data: Dict, stoch_data: Dict, whales_data: Dict) -> tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        rsi_confirm, stoch_confirm = self._get_oscillator_confirmation(direction, rsi_data, stoch_data)
        if rsi_confirm and stoch_confirm: score += weights.get('dual_oscillator', 3); confirmations.append("Dual Oscillator")
        elif rsi_confirm or stoch_confirm: score += weights.get('single_oscillator', 1); confirmations.append("Single Oscillator")
        if self._get_candlestick_confirmation(direction, min_reliability='Strong'): score += weights.get('candlestick', 2); confirmations.append("Strong Candlestick")
        if (whales_data.get('analysis') or {}).get('is_climactic_volume', False): score += weights.get('climactic_volume', 3); confirmations.append("Climactic Volume")
        return score, confirmations

    def _get_oscillator_confirmation(self, direction: str, rsi_data: Dict, stoch_data: Dict) -> tuple[bool, bool]:
        rsi_confirm, stoch_confirm = False, False
        rsi_val = (rsi_data.get('values') or {}).get('rsi')
        stoch_pos = (stoch_data.get('analysis') or {}).get('position')
        if rsi_val is not None:
            rsi_os, rsi_ob = 30, 70 # Standard defaults
            if direction == "BUY" and rsi_val < rsi_os: rsi_confirm = True
            elif direction == "SELL" and rsi_val > rsi_ob: rsi_confirm = True
        if stoch_pos is not None:
            if direction == "BUY" and stoch_pos == 'Oversold': stoch_confirm = True
            elif direction == "SELL" and stoch_pos == 'Overbought': stoch_confirm = True
        return rsi_confirm, stoch_confirm

    def _find_best_prz(self, cfg: Dict, fib_data: Dict, structure_data: Dict) -> Tuple[Optional[Dict], Dict]:
        debug_info = {"fib_levels_found": 0, "structure_levels_found": 0}
        current_price = self.price_data.get('close')
        if not current_price: return None, debug_info

        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_data.get('values', {}).get('levels', []) if 'Retracement' in lvl.get('type', '')}
        structure_levels = (structure_data.get('values', {}) or {}).get('key_levels', {})
        swing_trend = (fib_data.get('values') or {}).get('swing_trend')

        debug_info["fib_levels_found"] = len(fib_levels)
        if not swing_trend: return None, debug_info

        target_sr_zones = structure_levels.get('supports' if swing_trend == "Up" else 'resistances', [])
        debug_info["structure_levels_found"] = len(target_sr_zones)
        
        confluence_zones = []
        for fib_level_str in cfg.get('fib_levels_to_watch', []):
            fib_price = fib_levels.get(fib_level_str)
            if not fib_price: continue
            for sr_zone in target_sr_zones:
                sr_price = sr_zone.get('price')
                if sr_price and abs(fib_price - sr_price) / sr_price * 100 < cfg.get('confluence_proximity_percent', 0.3):
                    zone_price = (fib_price + sr_price) / 2.0
                    confluence_zones.append({ "price": zone_price, "fib_level": fib_level_str, "structure_zone": sr_zone, "distance_to_price": abs(zone_price - current_price) })
        
        best_zone = min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None
        return best_zone, debug_info

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # --- 1. Data Availability ---
        required_names = ['fibonacci', 'structure', 'rsi', 'stochastic', 'atr', 'patterns', 'whales', 'adx']
        indicators = {name: self.get_indicator(name) for name in list(set(required_names))}
        missing = [name for name, data in indicators.items() if data is None]
        if missing: self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        self._log_criteria("Data Availability", True, "All required data is valid.")

        # --- 2. Primary Signal & Location Filter ---
        swing_trend = (indicators['fibonacci'].get('values', {}) or {}).get('swing_trend')
        direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        self._log_criteria("Primary Signal (Swing Trend)", direction is not None, f"Trend: {swing_trend}")
        if not direction: self._log_final_decision("HOLD", "No primary swing trend identified by Fibonacci."); return None

        # ✅ GLASS BOX LOGGING: The PRZ check now provides full context.
        best_prz, prz_debug_info = self._find_best_prz(cfg, indicators['fibonacci'], indicators['structure'])
        prz_found = best_prz is not None
        if prz_found:
            prz_reason = f"PRZ found at {best_prz['price']:.4f} (Fib: {best_prz['fib_level']}, Str. Strength: {best_prz['structure_zone'].get('strength', 'N/A')})"
        else:
            prz_reason = (f"No confluence found. Fib Levels Available: {prz_debug_info['fib_levels_found']}, "
                          f"Structure Levels Available: {prz_debug_info['structure_levels_found']}")
        self._log_criteria("Location Filter (PRZ Found)", prz_found, prz_reason)
        if not prz_found: self._log_final_decision("HOLD", "Location filter failed."); return None

        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low and price_low <= best_prz['price']) or \
                     (direction == "SELL" and price_high and price_high >= best_prz['price'])
        self._log_criteria("Location Filter (Price Test)", is_testing, "Price has not tested the PRZ.")
        if not is_testing: self._log_final_decision("HOLD", "Price test failed."); return None

        # --- 3. Confirmation Funnel ---
        confluence_score, score_details = self._calculate_confluence_score(direction, indicators['rsi'], indicators['stochastic'], indicators['whales'])
        min_score = cfg.get('min_confluence_score', 5)
        score_is_ok = confluence_score >= min_score
        self._log_criteria("Confluence Score Check", score_is_ok, f"Score={confluence_score} vs min={min_score}")
        if not score_is_ok: self._log_final_decision("HOLD", "Confluence score too low."); return None
        
        if cfg.get('htf_confirmation_enabled'):
            htf_ok = self._get_trend_confirmation(direction)
            self._log_criteria("HTF Filter", htf_ok, "Not aligned with HTF." if not htf_ok else "HTF is aligned.")
            if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
        
        # --- 4. Adaptive Risk Management ---
        entry_price = self.price_data.get('close')
        atr_value = (indicators['atr'].get('values') or {}).get('atr')
        structure_level = (best_prz.get('structure_zone') or {}).get('price')
        if not all(v is not None for v in [entry_price, atr_value, structure_level]):
            self._log_final_decision("HOLD", "Risk data missing for SL calculation."); return None
        
        vol_cfg = cfg.get('volatility_regimes', {})
        atr_pct = (indicators['atr'].get('values') or {}).get('atr_percent', 2.0)
        is_low_vol = atr_pct < vol_cfg.get('low_atr_pct_threshold', 1.5)
        atr_sl_multiplier = vol_cfg.get('low_vol_sl_multiplier', 1.2) if is_low_vol else vol_cfg.get('high_vol_sl_multiplier', 1.8)
        
        stop_loss = structure_level - (atr_value * atr_sl_multiplier) if direction == "BUY" else structure_level + (atr_value * atr_sl_multiplier)
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        
        if not risk_params or not risk_params.get("targets"):
             self._log_final_decision("HOLD", "Risk parameter calculation failed."); return None
        
        confirmations = {
            "confluence_score": confluence_score,
            "score_details": ", ".join(score_details),
            "htf_filter": "Passed" if cfg.get('htf_confirmation_enabled') else "Disabled",
            "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        }
        self._log_final_decision(direction, "All criteria met. Confluence Sniper signal confirmed.")
        
        return { "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

