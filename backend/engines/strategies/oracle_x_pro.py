# backend/engines/strategies/oracle_x_pro.py (v1.1 - The Apex Timeframe Hotfix)

import logging
from typing import Dict, Any, Optional, List, ClassVar, Tuple

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class OracleXPro(BaseStrategy):
    """
    Oracle-X Pro - (v1.1 - The Apex Timeframe Hotfix)
    -------------------------------------------------------------------
    This version incorporates a critical hotfix to the HTF context logic,
    making the strategy "Apex Timeframe Aware". It now intelligently bypasses
    the HTF check when running on the highest configured timeframe (e.g., '1d'),
    using its own primary trend as the strategic bias. This ensures flawless
    operation across all timeframes as per the system's architecture.
    """
    strategy_name: str = "OracleXPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # Phase 1: The Quantum Observatory
        "htf_context_config": {
            "enabled": True,
            "min_adx_strength": 25.0
        },
        # Phase 2: The Sniper's Hideout
        "prz_config": {
            "use_fibonacci": True,
            "fib_levels": ["38.2%", "50.0%", "61.8%"],
            "use_pivots": True,
            "pivot_levels": ["R2", "R1", "P", "S1", "S2"],
            "use_structure": True,
            "min_structure_strength": 2,
            "proximity_percent": 0.7
        },
        # Phase 3: The Firing Protocol
        "confirmation_scoring": {
            "min_score": 11, # Adjusted for new candlestick weights
            "weights": {
                "climactic_volume": 4,
                "candlestick_strong": 3,
                "candlestick_medium": 2,
                "dual_oscillator_confirm": 3,
                "single_oscillator_confirm": 1
            }
        },
        # Phase 4: The Exit Strategy
        "risk_config": {
            "sl_atr_buffer": 1.2,
            "adaptive_targeting": {
                "enabled": True,
                "atr_multiples": [1.5, 2.5, 4.0]
            }
        },
        # Standard HTF map for BaseStrategy compatibility
        "htf_confirmation_enabled": True, # Must be true for Phase 1 to work
        "htf_map": {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d"},
    }

    def _find_oracle_prz(self, direction: str, cfg: Dict, indicators: Dict) -> Optional[Dict]:
        """
        The heart of the Sniper's Hideout. Finds the best confluence zone
        between Fibonacci, Pivots, and high-strength Structure levels.
        """
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price): return None

        fib_values = self._safe_get(indicators, ['fibonacci', 'values'], {})
        pivot_values = self._safe_get(indicators, ['pivots', 'values'], {})
        structure_values = self._safe_get(indicators, ['structure', 'values'], {})

        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_values.get('levels', [])} if cfg.get('use_fibonacci') else {}
        pivot_levels = {lvl['level']: lvl['price'] for lvl in pivot_values.get('levels', [])} if cfg.get('use_pivots') else {}
        structure_key_levels = structure_values.get('key_levels', {}) if cfg.get('use_structure') else {}
        
        target_sr_zones = structure_key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        
        confluence_zones = []
        proximity_pct = cfg.get('proximity_percent', 0.7)

        all_levels = {}
        if cfg.get('use_fibonacci'):
            for lvl_str in cfg.get('fib_levels', []):
                if lvl_str in fib_levels: all_levels[f"Fib {lvl_str}"] = fib_levels[lvl_str]
        
        if cfg.get('use_pivots'):
            for lvl_str in cfg.get('pivot_levels', []):
                if (direction == "BUY" and (lvl_str.startswith("S") or lvl_str == "P")) or \
                   (direction == "SELL" and (lvl_str.startswith("R") or lvl_str == "P")):
                     if lvl_str in pivot_levels: all_levels[f"Pivot {lvl_str}"] = pivot_levels[lvl_str]

        for sr_zone in target_sr_zones:
            if sr_zone.get('strength', 0) < cfg.get('min_structure_strength', 2): continue
            sr_price = sr_zone.get('price')
            if not self._is_valid_number(sr_price): continue

            for level_name, level_price in all_levels.items():
                if abs(level_price - sr_price) / sr_price * 100 < proximity_pct:
                    zone_price = (level_price + sr_price) / 2.0
                    confluence_zones.append({
                        "price": zone_price,
                        "components": f"{level_name} + Structure (Strength: {sr_zone.get('strength')})",
                        "structure_level": sr_price,
                        "distance_to_price": abs(zone_price - current_price)
                    })
        
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def _calculate_confirmation_score(self, direction: str, cfg: Dict, indicators: Dict) -> Tuple[int, List[str]]:
        """
        The heart of the Firing Protocol. Scores the quality of the reversal
        based on Oscillators, Candlesticks, and Volume.
        """
        weights, score, confirmations = cfg.get('weights', {}), 0, []

        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        stoch_pos = self._safe_get(indicators, ['stochastic', 'analysis', 'position'])
        
        rsi_ok = (direction == "BUY" and rsi_val < 30) or (direction == "SELL" and rsi_val > 70) if self._is_valid_number(rsi_val) else False
        stoch_ok = (direction == "BUY" and "Oversold" in stoch_pos) or (direction == "SELL" and "Overbought" in stoch_pos) if stoch_pos else False
        
        if rsi_ok and stoch_ok:
            score += weights.get('dual_oscillator_confirm', 3); confirmations.append("Dual Oscillator")
        elif rsi_ok or stoch_ok:
            score += weights.get('single_oscillator_confirm', 1); confirmations.append("Single Oscillator")

        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        if confirming_pattern:
            reliability = (confirming_pattern.get('reliability') or '').capitalize()
            pattern_name = confirming_pattern.get('name', 'Unknown Pattern')
            if reliability == 'Strong':
                score += weights.get('candlestick_strong', 3); confirmations.append(f"Strong Candlestick ({pattern_name})")
            elif reliability == 'Medium':
                score += weights.get('candlestick_medium', 2); confirmations.append(f"Medium Candlestick ({pattern_name})")

        if self._safe_get(indicators, ['whales', 'analysis', 'is_climactic_volume'], False):
            score += weights.get('climactic_volume', 4); confirmations.append("Climactic Volume")
            
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # --- Phase 1: The Quantum Observatory (v1.1 - Apex Timeframe Hotfix) ---
        htf_cfg = cfg.get('htf_context_config', {})
        htf_bias = "NOT_CHECKED"
        direction = None

        if htf_cfg.get('enabled', True) and self.htf_analysis:
            htf_ichi = self.get_indicator('ichimoku', analysis_source=self.htf_analysis)
            htf_adx = self.get_indicator('adx', analysis_source=self.htf_analysis)
            
            htf_trend_score = self._safe_get(htf_ichi, ['analysis', 'trend_score'], 0)
            htf_adx_strength = self._safe_get(htf_adx, ['values', 'adx'], 0)
            
            htf_bias = "NEUTRAL"
            min_adx = htf_cfg.get('min_adx_strength', 25.0)
            if htf_trend_score >= 5 and self._is_valid_number(htf_adx_strength) and htf_adx_strength >= min_adx:
                htf_bias = "BULLISH"; direction = "BUY"
            elif htf_trend_score <= -5 and self._is_valid_number(htf_adx_strength) and htf_adx_strength >= min_adx:
                htf_bias = "BEARISH"; direction = "SELL"
            
            self._log_criteria("Phase 1: HTF Context", htf_bias not in ["NEUTRAL", "NOT_CHECKED"], f"HTF Bias is '{htf_bias}'. Ichi Score: {htf_trend_score}, ADX: {htf_adx_strength or 'N/A':.2f}")
            if htf_bias == "NEUTRAL":
                self._log_final_decision("HOLD", "HTF context is neutral. Standing by."); return None
        else:
            # This block handles the Apex Timeframe (e.g., '1d') where no HTF data exists.
            # We use the primary timeframe's swing trend as the bias.
            fib_swing_trend = self._safe_get(self.get_indicator('fibonacci'), ['values', 'swing_trend'])
            if fib_swing_trend == "Up": direction = "BUY"; htf_bias = "BULLISH (from Primary Swing)"
            elif fib_swing_trend == "Down": direction = "SELL"; htf_bias = "BEARISH (from Primary Swing)"
            
            self._log_criteria("Phase 1: HTF Context", direction is not None, f"HTF check bypassed. Using primary swing trend as bias: '{htf_bias}'")
            if direction is None:
                self._log_final_decision("HOLD", "Could not determine a primary trend bias on Apex Timeframe."); return None
        
        # --- Data Availability for Primary Timeframe ---
        required = ['fibonacci', 'pivots', 'structure', 'rsi', 'stochastic', 'whales', 'patterns', 'atr']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Missing essential indicators: {', '.join(missing)}."); return None

        # --- Phase 2: The Sniper's Hideout ---
        prz_cfg = cfg.get('prz_config', {})
        best_prz = self._find_oracle_prz(direction, prz_cfg, indicators)
        self._log_criteria("Phase 2: PRZ Found", best_prz is not None, f"PRZ Components: {best_prz['components']}" if best_prz else "No high-probability PRZ found.")
        if not best_prz: self._log_final_decision("HOLD", "No PRZ to monitor."); return None

        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (direction == "BUY" and price_low <= best_prz['price']) or (direction == "SELL" and price_high >= best_prz['price'])
        self._log_criteria("Phase 2: Price Test", is_testing, f"Price is testing the PRZ at {best_prz['price']:.5f}.")
        if not is_testing: self._log_final_decision("HOLD", "Price has not entered the PRZ."); return None
        
        # --- Phase 3: The Firing Protocol ---
        scoring_cfg = cfg.get('confirmation_scoring', {})
        score, details = self._calculate_confirmation_score(direction, scoring_cfg, indicators)
        min_score = scoring_cfg.get('min_score', 10)
        score_is_ok = score >= min_score
        self._log_criteria("Phase 3: Firing Protocol", score_is_ok, f"Score={score} vs min={min_score}. Details: {', '.join(details)}")
        if not score_is_ok: self._log_final_decision("HOLD", "Confirmation score is too low."); return None

        # --- Phase 4: The Exit Strategy ---
        risk_cfg = cfg.get('risk_config', {})
        entry_price = self.price_data.get('close')
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        structure_level = best_prz.get('structure_level')

        if not self._is_valid_number(entry_price, atr_value, structure_level):
            self._log_final_decision("HOLD", "Could not calculate SL due to missing data."); return None
            
        sl_buffer = atr_value * risk_cfg.get('sl_atr_buffer', 1.2)
        stop_loss = structure_level - sl_buffer if direction == "BUY" else structure_level + sl_buffer
        
        risk_params = self._calculate_smart_risk_management(entry_price, direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk parameter calculation failed."); return None

        # --- Final Blueprint Generation ---
        confirmations = { "final_score": score, "details": ", ".join(details), "prz_components": best_prz['components'], "htf_bias": htf_bias }
        self._log_final_decision(direction, f"Oracle-X Pro signal confirmed. Score: {score}. Firing.")

        return { "direction": direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
