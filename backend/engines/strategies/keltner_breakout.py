# backend/engines/strategies/KeltnerMomentumBreakout.py - (v14.1 - Strategic MACD Alignment)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v14.1 - Strategic MACD Alignment)
    -------------------------------------------------------------------------
    This version refines the "Gold Standard" logic by strategically adjusting
    the MACD confirmation. It shifts from a strict "acceleration-only"
    check ('Green'/'Red' states) to a more robust and responsive "alignment"
    check (histogram > 0 or < 0). This change is designed to reduce signal
    lag and capture valid breakouts earlier without sacrificing the core
    strength of the strategy's other filters.

    🚀 KEY EVOLUTIONS in v14.1:
    1.  **Optimized MACD Logic:** The MACD confirmation is specialized to confirm
        short-term momentum alignment, allowing for faster entries. The role of
        verifying trend *strength* is now delegated entirely to more suitable
        indicators like ADX and Volume, creating a more efficient system.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        "market_regime_filter_enabled": True, "required_regime": "TRENDING", "adx_percentile_threshold": 80.0,
        "outlier_candle_shield_enabled": True, "outlier_atr_multiplier": 3.5,
        "exhaustion_shield_enabled": True, "rsi_exhaustion_lookback": 200, "rsi_buy_percentile": 90, "rsi_sell_percentile": 10,
        "cooldown_bars": 3,
        
        "min_momentum_score": {"low_tf": 13, "high_tf": 13},
        "weights": { 
            "momentum_acceleration": 4, "volume_catalyst": 3, "volatility_expansion": 2,
            "adx_strength": 1, "htf_alignment": 2, "candlestick": 1, "macd_aligned": 4
        },
        "volume_z_score_threshold": 1.75,
        "late_entry_atr_mult": 1.2,
        
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { 
            "min_required_score": 2, 
            "adx": {"weight": 1, "min_percentile": 80.0}, 
            "supertrend": {"weight": 1} 
        }
    }
    
    def _calculate_momentum_score(self, direction: str, indicators: Dict) -> Tuple[int, List[Dict]]:
        weights, score = self.config.get('weights', {}), 0
        confirmation_details = [] # This will hold the rich confirmation data.
        
        # Helper function for cleaner code
        def check_and_log(name: str, weight_key: str, condition: bool, reason: str):
            nonlocal score
            self._log_criteria(f"Score: {name}", condition, reason)
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmation_details.append({'criterion': name, 'value': reason})

        # --- Indicator Analysis ---
        cci_analysis = self._safe_get(indicators, ['cci', 'analysis'], {})
        volume_values = self._safe_get(indicators, ['volume', 'values'], {})
        keltner_analysis = self._safe_get(indicators, ['keltner_channel', 'analysis'], {})
        adx_analysis = self._safe_get(indicators, ['adx', 'analysis'], {})
        # macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {}) # No longer needed for logic, but can be kept for logging if desired

        # --- Scoring Criteria ---
        mom_state = cci_analysis.get('momentum_state', '')
        is_cci_accel = (direction == "BUY" and mom_state == 'Accelerating Bullish') or \
                       (direction == "SELL" and mom_state == 'Accelerating Bearish')
        check_and_log("Momentum Acceleration (CCI)", "momentum_acceleration", is_cci_accel, f"State: {mom_state}")

        # ✅ SURGICAL PATCH v14.1: Shift from "Acceleration" to "Alignment" for earlier entries.
        macd_values = self._safe_get(indicators, ['macd', 'values'], {})
        last_hist = macd_values.get('histogram', 0.0)

        is_macd_aligned = (direction == "BUY" and last_hist > 0) or \
                          (direction == "SELL" and last_hist < 0)
        check_and_log("MACD Aligned", "macd_aligned", is_macd_aligned, f"Histogram: {last_hist:.5f}")

        z_score_thresh = self.config.get('volume_z_score_threshold', 1.75)
        current_z_score = volume_values.get('z_score', 0.0)
        is_vol_catalyst = self._is_valid_number(current_z_score) and current_z_score > z_score_thresh
        check_and_log("Volume Catalyst", "volume_catalyst", is_vol_catalyst, f"Z-Score: {current_z_score:.2f}")

        volatility_state = keltner_analysis.get('volatility_state', 'Normal')
        is_vol_expansion = volatility_state == 'Expansion'
        check_and_log("Volatility Expansion", "volatility_expansion", is_vol_expansion, f"State: {volatility_state}")
        
        adx_percentile = adx_analysis.get('adx_percentile', 0.0)
        is_adx_strong = adx_percentile >= self.config.get('adx_percentile_threshold', 80.0)
        check_and_log("ADX Strength (Adaptive)", "adx_strength", is_adx_strong, f"Percentile: {adx_percentile:.2f}%")

        if self.config.get('htf_confirmation_enabled', True):
            htf_aligned = self._get_trend_confirmation(direction)
            check_and_log("HTF Aligned", "htf_alignment", htf_aligned, f"HTF OK: {htf_aligned}")

        candlestick_confirmed = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        pattern_name = candlestick_confirmed['name'] if candlestick_confirmed else 'None'
        check_and_log("Candlestick Confirmed", "candlestick", candlestick_confirmed is not None, f"Pattern: {pattern_name}")
        
        return score, confirmation_details

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # ... [The conductor logic remains unchanged] ...
        cfg = self.config
        
        if self.df is None or self.df.empty: self._log_final_decision("HOLD", "DataFrame missing."); return None
        current_bar, last_signal_bar = len(self.df) - 1, getattr(self, "last_signal_bar", -9999)
        cooldown = cfg.get('cooldown_bars', 3)
        if (current_bar - last_signal_bar) < cooldown: self._log_final_decision("HOLD", f"In cooldown."); return None
        if not self.price_data: self._log_final_decision("HOLD", "Price data missing."); return None

        required = ['keltner_channel', 'cci', 'volume', 'adx', 'atr', 'rsi', 'patterns', 'supertrend', 
                    'macd', 'pivots', 'structure', 'fibonacci']
        indicators = {name: self.get_indicator(name) for name in set(required)}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None

        keltner_analysis = self._safe_get(indicators, ['keltner_channel', 'analysis'], {})
        position_text = str(keltner_analysis.get('position','')).lower()
        signal_direction = "BUY" if "breakout above" in position_text else "SELL" if "breakdown below" in position_text else None
        if not signal_direction: self._log_final_decision("HOLD", f"No Keltner trigger."); return None
        self._log_criteria("Primary Trigger", True, f"Position: {position_text}")

        if cfg.get('outlier_candle_shield_enabled') and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_multiplier', 3.5)):
            self._log_final_decision("HOLD", "Outlier Candle Shield activated."); return None
        
        adx_percentile = self._safe_get(indicators, ['adx', 'analysis', 'adx_percentile'], 0.0)
        percentile_threshold = cfg.get('adx_percentile_threshold', 80.0)
        market_regime = "TRENDING" if adx_percentile >= percentile_threshold else "RANGING"
        required_regime = cfg.get('required_regime', 'TRENDING')
        regime_ok = market_regime == required_regime
        self._log_criteria("Market Regime Filter (Adaptive)", regime_ok, f"Market is '{market_regime}' (ADX Percentile={adx_percentile:.2f}%), Required: '{required_regime}'")
        if cfg.get('market_regime_filter_enabled') and not regime_ok:
            self._log_final_decision("HOLD", "Market regime not suitable."); return None

        entry_price, atr_val = self.price_data.get('close'), self._safe_get(indicators, ['atr', 'values', 'atr'])
        breakout_level = keltner_analysis.get('breakout_level')
        if self._is_valid_number(entry_price, atr_val, breakout_level):
            max_dist, current_dist = cfg.get('late_entry_atr_mult', 1.2) * atr_val, abs(entry_price - breakout_level)
            entry_ok = current_dist <= max_dist
            self._log_criteria("Late-Entry Guard", entry_ok, f"Distance from breakout: {current_dist:.5f} vs Max: {max_dist:.5f}")
            if not entry_ok: self._log_final_decision("HOLD", "Price too far from breakout."); return None
        
        if cfg.get('exhaustion_shield_enabled'):
            if self._is_trend_exhausted_dynamic(direction=signal_direction, rsi_lookback=cfg.get('rsi_exhaustion_lookback', 200),
                                                rsi_buy_percentile=cfg.get('rsi_buy_percentile', 90), rsi_sell_percentile=cfg.get('rsi_sell_percentile', 10)):
                self._log_final_decision("HOLD", "Adaptive Trend Exhaustion Shield activated."); return None
            self._log_criteria("Exhaustion Shield", True, "Trend not exhausted.")
        
        min_score = self._get_min_score_for_tf(cfg.get('min_momentum_score', {}))
        momentum_score, confirmation_details = self._calculate_momentum_score(signal_direction, indicators)
        score_ok = momentum_score >= min_score
        self._log_criteria("Momentum Score Check", score_ok, f"Score={momentum_score} vs min={min_score}")
        if not score_ok:
            self._log_final_decision("HOLD", f"Momentum score {momentum_score} below minimum."); return None

        risk_params = self._orchestrate_static_risk(
            direction=signal_direction, 
            entry_price=entry_price
        )

        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "OHRE v3.0 failed to generate a valid risk plan."); return None
            
        self.last_signal_bar = current_bar
        
        confirmations_dict = {
            "final_score": momentum_score, 
            "details": confirmation_details,
            "risk_engine_source": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward_ratio": risk_params.get('risk_reward_ratio')
        }
        self._log_final_decision(signal_direction, f"Keltner Momentum Breakout confirmed. Score: {momentum_score}.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations_dict }
