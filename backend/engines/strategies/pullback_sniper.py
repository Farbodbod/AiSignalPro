# backend/engines/strategies/pullback_sniper.py (v2.1 - The Legendary Ghost)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PullbackSniperPro(BaseStrategy):
    """
    PullbackSniperPro - (v2.1 - The Legendary Ghost)
    -------------------------------------------------------------------------
    This version applies the "Grandmaster's Final Polish" to the v2.0 engine,
    elevating the commando to a legendary phantom of the battlefield.

    🚀 FINAL POLISHES in v2.1:
    1.  **Expanded Ambush Zone:** The PRZ engine now includes the 38.2% Fibonacci
        level, enabling the sniper to engage in the strongest of trends.
    2.  **Adaptive Standards:** The minimum confirmation score is now dynamic,
        demanding a higher level of evidence for higher timeframe signals.
    3.  **Optimized Reward Profile:** The minimum R/R ratio has been increased,
        aligning the strategy's behavior with its "sniper" philosophy of
        taking only high-quality, high-reward shots.
    """
    strategy_name: str = "PullbackSniperPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # --- Macro Trend Filters ---
        "trend_filter_enabled": True,
        "master_ma_indicator": "fast_ma",
        "htf_confirmation_enabled": True,

        # --- G.1: PRZ Engine Config (✅ POLISHED) ---
        "prz_config": {
            "use_fibonacci": True,
            "fib_levels": ["38.2%", "50.0%", "61.8%"], # Added 38.2% for strong trends
            "use_pivots": True,
            "use_structure": True,
            "min_structure_strength": 2,
            "proximity_percent": 0.5
        },
        
        # --- G.2: Scoring Engine Config (✅ POLISHED) ---
        "confirmation_scoring": {
            "min_score": {"low_tf": 8, "high_tf": 10}, # Made dynamic for different timeframes
            "weights": {
                "hidden_divergence": 4, "dual_oscillator": 3, "candlestick_strong": 3,
                "volume_spike": 2, "candlestick_medium": 2, "single_oscillator": 1
            }
        },

        # --- G.3: Risk Harmonization (✅ POLISHED) ---
        "min_rr_ratio": 1.8, # Increased for higher quality sniper setups
        
        # --- Standard HTF Config (✅ POLISHED) ---
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2,
            "adx": {"weight": 1, "min_percentile": 65.0}, # Sniper Asymmetric Philosophy
            "supertrend": {"weight": 1}
        }
    }
    
    # --- Helper methods _find_pullback_prz and _calculate_confirmation_score are unchanged from v2.0 ---
    def _find_pullback_prz(self, direction: str, cfg: Dict, indicators: Dict) -> Optional[Dict]:
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
        proximity_pct = cfg.get('proximity_percent', 0.5)
        all_levels = {}
        if cfg.get('use_fibonacci'):
            for lvl_str in cfg.get('fib_levels', []):
                if lvl_str in fib_levels: all_levels[f"Fib {lvl_str}"] = fib_levels[lvl_str]
        if cfg.get('use_pivots'):
            pivot_list = pivot_values.get('levels', [])
            for p_level in pivot_list:
                lvl_str = p_level['level']
                if (direction == "BUY" and lvl_str.startswith("S")) or (direction == "SELL" and lvl_str.startswith("R")):
                     all_levels[f"Pivot {lvl_str}"] = p_level['price']
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
        
        # --- 1. Define Macro Trend (The Hunting Ground) ---
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

        # --- 2. Identify Pullback Zone (The Ambush Point) ---
        signal_direction = "BUY" if macro_trend == "UP" else "SELL"
        prz_cfg = cfg.get('prz_config', {})
        best_prz = self._find_pullback_prz(signal_direction, prz_cfg, indicators)
        self._log_criteria("Pullback PRZ Search", best_prz is not None, f"PRZ Components: {best_prz['components']}" if best_prz else "No high-probability PRZ found.")
        if not best_prz: self._log_final_decision("HOLD", "No PRZ to monitor."); return None
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        is_testing = (signal_direction == "BUY" and price_low <= best_prz['price']) or (signal_direction == "SELL" and price_high >= best_prz['price'])
        self._log_criteria("Price Test on PRZ", is_testing, f"Price is testing the PRZ at {best_prz['price']:.5f}.")
        if not is_testing: self._log_final_decision("HOLD", "Price has not entered the PRZ."); return None
        
        # --- 3. Find Entry Trigger (The Fire Command) ---
        scoring_cfg = cfg.get('confirmation_scoring', {})
        # ✅ POLISH: Use the base helper to get the correct min_score for the timeframe
        min_score = self._get_min_score_for_tf(scoring_cfg.get('min_score', {}))
        score, details = self._calculate_confirmation_score(signal_direction, scoring_cfg, indicators)
        score_is_ok = score >= min_score
        self._log_criteria("Confirmation Score", score_is_ok, f"Score={score} vs min={min_score}. Details: {', '.join(details)}")
        if not score_is_ok: self._log_final_decision("HOLD", "Confirmation score is too low."); return None

        # --- 4. Engineer the Trade (OHRE v3.0) ---
        entry_price = self.price_data.get('close')
        # ✅ POLISH: Use the strategy-specific min_rr_ratio for the OHRE check
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 1.5)
        
        risk_params = self._orchestrate_static_risk(
            direction=signal_direction, 
            entry_price=entry_price
        )
        self.config.pop('override_min_rr_ratio', None)
        if not risk_params:
            self._log_final_decision("HOLD", "OHRE v3.0 failed to generate a valid risk plan."); return None
        
        # --- 5. Final Signal ---
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
