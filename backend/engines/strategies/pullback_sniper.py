# backend/engines/strategies/pullback_sniper.py (v2.2 - The Ghost Protocol)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PullbackSniperPro(BaseStrategy):
    """
    PullbackSniperPro - (v2.2 - The Ghost Protocol)
    -------------------------------------------------------------------------
    This version integrates the final Oracle-X calibrations and logical upgrades.
    It introduces a fully adaptive, configurable, and intelligent PRZ engine
    that understands the dynamic nature of support and resistance (S/R Flips),
    elevating the strategy to its ultimate, legendary form.
    """
    strategy_name: str = "PullbackSniperPro"

    # --- [ORACLE-X CALIBRATION v2.2] ---
    # Final calibrations applied for The Ghost Protocol doctrine.
    default_config: ClassVar[Dict[str, Any]] = {
        "trend_filter_enabled": True,
        "master_ma_indicator": "fast_ma",
        "htf_confirmation_enabled": True,

        "prz_config": {
            "use_fibonacci": True,
            "fib_levels": ["38.2%", "50.0%", "61.8%"]
            "use_pivots": True,
            # ✅ UPGRADE: Pivot levels are now fully configurable.
            "pivot_levels": ["R3", "R2", "R1", "P", "S1", "S2", "S3"],
            "use_structure": True,
            "min_structure_strength": 2,
            "proximity_percent": 0.75 # Using the more balanced "Sniper Protocol"
        },
        
        "confirmation_scoring": {
            "min_score": {"low_tf": 9, "high_tf": 11},
            "weights": {
                "hidden_divergence": 5,
                "dual_oscillator": 3,
                "candlestick_strong": 3,
                "volume_spike": 2,
                "candlestick_medium": 2,
                "single_oscillator": 1
            }
        },

        "min_rr_ratio": 2.2,
        
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_percentile": 70.0},
            "supertrend": {"weight": 1}
        }
    }
    
    def _find_pullback_prz(self, direction: str, cfg: Dict, indicators: Dict) -> Optional[Dict]:
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price): return None
        
        fib_values = self._safe_get(indicators, ['fibonacci', 'values'], {})
        pivot_values = self._safe_get(indicators, ['pivots', 'values'], {})
        structure_values = self._safe_get(indicators, ['structure', 'values'], {})
        
        fib_levels = {lvl['level']: lvl['price'] for lvl in fib_values.get('levels', [])} if cfg.get('use_fibonacci') else {}
        structure_key_levels = structure_values.get('key_levels', {}) if cfg.get('use_structure') else {}
        target_sr_zones = structure_key_levels.get('supports' if direction == "BUY" else 'resistances', [])
        
        confluence_zones = []
        proximity_pct = cfg.get('proximity_percent', 0.5)
        all_levels = {}

        if cfg.get('use_fibonacci'):
            for lvl_str in cfg.get('fib_levels', []):
                if lvl_str in fib_levels: all_levels[f"Fib {lvl_str}"] = fib_levels[lvl_str]

        # --- [ORACLE-X UPGRADE v2.2: Intelligent, Configurable Pivot Logic] ---
        # This section now reads the pivot levels from the config and applies
        # the advanced S/R flip logic we developed.
        if cfg.get('use_pivots'):
            target_pivots = cfg.get('pivot_levels', [])
            calculated_pivots = {lvl['level']: lvl['price'] for lvl in pivot_values.get('levels', [])}

            for lvl_str in target_pivots:
                if lvl_str not in calculated_pivots:
                    continue
                
                lvl_price = calculated_pivots[lvl_str]
                if not self._is_valid_number(lvl_price): continue

                if direction == "BUY":
                    # A level is support if it's a classic Support (S), a broken Resistance (R),
                    # or the central Pivot (P) that the price is currently above.
                    if lvl_str.startswith("S") or \
                       (lvl_str.startswith("R") and current_price > lvl_price) or \
                       (lvl_str == "P" and current_price > lvl_price):
                        all_levels[f"Pivot {lvl_str} (as Support)"] = lvl_price
                
                elif direction == "SELL":
                    # A level is resistance if it's a classic Resistance (R), a broken Support (S),
                    # or the central Pivot (P) that the price is currently below.
                    if lvl_str.startswith("R") or \
                       (lvl_str.startswith("S") and current_price < lvl_price) or \
                       (lvl_str == "P" and current_price < lvl_price):
                        all_levels[f"Pivot {lvl_str} (as Resistance)"] = lvl_price
        # --- End of Upgrade ---

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
                        "distance_to_price": abs(zone_price - current_price)
                    })
        return min(confluence_zones, key=lambda x: x['distance_to_price']) if confluence_zones else None

    def _calculate_confirmation_score(self, direction: str, cfg: Dict, indicators: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = cfg.get('weights', {}), 0, []
        rsi_pos = self._safe_get(indicators, ['rsi', 'analysis', 'position'])
        stoch_pos = self._safe_get(indicators, ['stochastic', 'analysis', 'position'])
        rsi_ok = (direction == "BUY" and "Oversold" in str(rsi_pos)) or (direction == "SELL" and "Overbought" in str(rsi_pos))
        stoch_ok = (direction == "BUY" and "Oversold" in str(stoch_pos)) or (direction == "SELL" and "Overbought" in str(stoch_pos))
        if rsi_ok and stoch_ok:
            score += weights.get('dual_oscillator', 3); confirmations.append("Dual Oscillator Confirmation")
        elif rsi_ok or stoch_ok:
            score += weights.get('single_oscillator', 1); confirmations.append("Single Oscillator Confirmation")
        confirming_pattern = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        if confirming_pattern:
            reliability = (confirming_pattern.get('reliability') or '').capitalize()
            pattern_name = confirming_pattern.get('name', 'Unknown Pattern')
            if reliability == 'Strong':
                score += weights.get('candlestick_strong', 3); confirmations.append(f"Strong Candlestick ({pattern_name})")
            elif reliability == 'Medium':
                score += weights.get('candlestick_medium', 2); confirmations.append(f"Medium Candlestick ({pattern_name})")
        if self._get_volume_confirmation():
            score += weights.get('volume_spike', 2); confirmations.append("Volume Spike")
        div_analysis = self._safe_get(indicators, ['divergence', 'analysis'], {})
        if (direction == "BUY" and div_analysis.get('has_hidden_bullish_divergence')) or \
           (direction == "SELL" and div_analysis.get('has_hidden_bearish_divergence')):
            score += weights.get('hidden_divergence', 4); confirmations.append("Hidden Divergence")
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        required_names = ['fast_ma', 'supertrend', 'fibonacci', 'divergence', 'patterns', 'atr', 
                          'structure', 'pivots', 'rsi', 'stochastic', 'volume', 'adx']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            self._log_criteria("Data Availability", False, "One or more required indicators are missing."); return None
        
        current_price = self.price_data.get('close')
        master_ma_val = self._safe_get(indicators, ['fast_ma', 'values', 'ma_value'])
        if not self._is_valid_number(current_price, master_ma_val):
            self._log_final_decision("HOLD", "Missing critical price or MA value for trend definition."); return None
        st_trend = self._safe_get(indicators, ['supertrend', 'analysis', 'trend'], '').lower()
        htf_is_aligned_up = self._get_trend_confirmation("BUY") if cfg.get("htf_confirmation_enabled") else True
        htf_is_aligned_down = self._get_trend_confirmation("SELL") if cfg.get("htf_confirmation_enabled") else True
        macro_trend = "NEUTRAL"
        if cfg.get('trend_filter_enabled'):
            if current_price > master_ma_val and "up" in st_trend and htf_is_aligned_up: macro_trend = "UP"
            elif current_price < master_ma_val and "down" in st_trend and htf_is_aligned_down: macro_trend = "DOWN"
        else:
            if "up" in st_trend and htf_is_aligned_up: macro_trend = "UP"
            elif "down" in st_trend and htf_is_aligned_down: macro_trend = "DOWN"
        self._log_criteria("Macro Trend Defined", macro_trend != "NEUTRAL", f"Macro trend identified as {macro_trend}.")
        if macro_trend == "NEUTRAL": self._log_final_decision("HOLD", "No clear macro trend."); return None

        signal_direction = "BUY" if macro_trend == "UP" else "SELL"
        prz_cfg = cfg.get('prz_config', {})
        best_prz = self._find_pullback_prz(signal_direction, prz_cfg, indicators)
        self._log_criteria("Pullback PRZ Search", best_prz is not None, f"PRZ Components: {best_prz['components']}" if best_prz else "No high-probability PRZ found.")
        if not best_prz: self._log_final_decision("HOLD", "No PRZ to monitor."); return None
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (signal_direction == "BUY" and price_low <= best_prz['price']) or (signal_direction == "SELL" and price_high >= best_prz['price'])
        self._log_criteria("Price Test on PRZ", is_testing, f"Price is testing the PRZ at {best_prz['price']:.5f}.")
        if not is_testing: self._log_final_decision("HOLD", "Price has not entered the PRZ."); return None
        
        scoring_cfg = cfg.get('confirmation_scoring', {})
        min_score = self._get_min_score_for_tf(scoring_cfg.get('min_score', {}))
        score, details = self._calculate_confirmation_score(signal_direction, scoring_cfg, indicators)
        score_is_ok = score >= min_score
        self._log_criteria("Confirmation Score", score_is_ok, f"Score={score} vs min={min_score}. Details: {', '.join(details)}")
        if not score_is_ok: self._log_final_decision("HOLD", "Confirmation score is too low."); return None

        entry_price = self.price_data.get('close')
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 1.5)
        
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction, 
            entry_price=entry_price
        )
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE v3.0 failed to generate a valid risk plan."); return None
        
        confirmations = {
            "macro_trend": macro_trend,
            "prz_components": best_prz['components'],
            "final_score": score,
            "entry_triggers": ", ".join(details),
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "rr_check": f"Passed (R/R: {risk_params.get('risk_reward_ratio')})"
        }
        self._log_final_decision(signal_direction, "All criteria met. Pullback Sniper signal confirmed.")
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }

