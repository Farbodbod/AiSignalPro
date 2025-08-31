# backend/engines/strategies/keltner_breakout.py (v11.1 - Robust Logging Edition)

import logging
from typing import Dict, Any, Optional, List, Tuple, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerMomentumBreakout(BaseStrategy):
    """
    KeltnerMomentumBreakout - (v11.1 - Robust Logging Edition)
    -------------------------------------------------------------------------
    This version integrates a comprehensive and transparent logging protocol,
    mirroring the best practices from benchmark strategies like Maestro and
    IchimokuHybridPro. Every decision point, filter, score component, and exit
    path is now explicitly logged using the framework's _log_criteria and
    _log_final_decision methods. This eliminates silent failures and provides
    a clear, step-by-step trace of the strategy's execution logic for enhanced
    debugging and operational transparency.
    """
    strategy_name: str = "KeltnerMomentumBreakout"

    default_config: ClassVar[Dict[str, Any]] = {
        # Core Filters & Shields
        "market_regime_filter_enabled": True, "required_regime": "TRENDING", "regime_adx_threshold": 21.0,
        "outlier_candle_shield_enabled": True, "outlier_atr_multiplier": 3.5,
        "exhaustion_shield_enabled": True, "rsi_exhaustion_lookback": 200, "rsi_buy_percentile": 90, "rsi_sell_percentile": 10,
        "cooldown_bars": 3,
        
        # Quantum Scoring Engine Weights
        "min_momentum_score": {"low_tf": 8, "high_tf": 10},
        "weights": { 
            "momentum_acceleration": 4, "volume_catalyst": 3, "volatility_expansion": 2,
            "adx_strength": 1, "htf_alignment": 2, "candlestick": 1
        },
        "volume_z_score_threshold": 1.75,
        
        # Blueprint Generation Parameters
        "late_entry_atr_mult": 1.2,
        "max_structural_sl_atr_mult": 2.5,
        "atr_sl_multiplier": 1.5,
        "target_atr_multiples": [1.5, 3.0, 4.5],

        # HTF Configuration (Self-Contained)
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { 
            "min_required_score": 2, 
            "adx": {"weight": 1, "min_strength": 25}, 
            "supertrend": {"weight": 1} 
        }
    }
    
    def _calculate_momentum_score(self, direction: str, indicators: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        
        def check(name: str, weight_key: str, condition: bool, reason: str = ""):
            # Add granular logging for each score component
            self._log_criteria(f"ScoreComponent: {name}", condition, reason)
            nonlocal score
            if condition:
                points = weights.get(weight_key, 0)
                score += points
                confirmations.append(name)

        cci_analysis = (indicators.get('cci', {}).get('analysis') or {})
        volume_values = (indicators.get('volume', {}).get('values') or {})
        keltner_analysis = (indicators.get('keltner_channel', {}).get('analysis') or {})
        adx_values = (indicators.get('adx', {}).get('values') or {})

        mom_state = cci_analysis.get('momentum_state', '')
        is_accel = (direction == "BUY" and mom_state == 'Accelerating Bullish') or \
                   (direction == "SELL" and mom_state == 'Accelerating Bearish')
        check("Momentum Acceleration", "momentum_acceleration", is_accel, f"CCI Momentum State: {mom_state}")

        z_score_thresh = self.config.get('volume_z_score_threshold', 1.75)
        current_z_score = volume_values.get('z_score', 0) or 0
        is_vol_catalyst = current_z_score > z_score_thresh
        check("Volume Catalyst", "volume_catalyst", is_vol_catalyst, f"Volume Z-Score: {current_z_score:.2f} vs Threshold: {z_score_thresh}")

        volatility_state = keltner_analysis.get('volatility_state', 'Normal')
        is_vol_expansion = volatility_state == 'Expansion'
        check("Volatility Expansion", "volatility_expansion", is_vol_expansion, f"Keltner Volatility State: {volatility_state}")
        
        adx_strength = adx_values.get('adx', 0.0) or 0.0
        is_adx_strong = adx_strength >= 25.0
        check("ADX Strength", "adx_strength", is_adx_strong, f"ADX Value: {adx_strength:.2f}")

        if self.config.get('htf_confirmation_enabled', True):
            htf_aligned = self._get_trend_confirmation(direction)
            check("HTF Aligned", "htf_alignment", htf_aligned, "Higher timeframe trend confirmation check.")

        candlestick_confirmed = self._get_candlestick_confirmation(direction, min_reliability='Medium')
        check("Candlestick Confirmed", "candlestick", candlestick_confirmed is not None, f"Pattern: {candlestick_confirmed['name'] if candlestick_confirmed else 'None'}")
        
        return score, confirmations

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # --- 1. Initial Sanity Checks ---
        if self.df is None or self.df.empty:
            self._log_final_decision("HOLD", "DataFrame is missing or empty.")
            return None
        
        current_bar = len(self.df) - 1
        last_signal_bar = getattr(self, "last_signal_bar", -9999)
        cooldown = cfg.get('cooldown_bars', 3)
        if (current_bar - last_signal_bar) < cooldown:
            self._log_final_decision("HOLD", f"In cooldown period ({current_bar - last_signal_bar} < {cooldown} bars).")
            return None
        
        if not self.price_data:
            self._log_final_decision("HOLD", "Price data is not available.")
            return None

        # --- 2. Indicator Availability Check ---
        required = ['keltner_channel', 'cci', 'volume', 'adx', 'atr', 'rsi', 'patterns', 'supertrend']
        indicators = {name: self.get_indicator(name) for name in required}
        
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            self._log_final_decision("HOLD", f"Required indicators are missing: {', '.join(missing_indicators)}")
            return None

        # --- 3. Primary Trigger Condition ---
        keltner_analysis = (indicators['keltner_channel'].get('analysis') or {})
        position_text = str(keltner_analysis.get('position',''))
        signal_direction = "BUY" if "breakout above" in position_text else "SELL" if "breakdown below" in position_text else None
        
        if not signal_direction:
            self._log_final_decision("HOLD", f"No primary trigger from Keltner Channel. Position: '{position_text}'")
            return None
        self._log_criteria("Primary Trigger", True, f"Position: {position_text}")

        # --- 4. Core Filters & Shields ---
        if cfg.get('outlier_candle_shield_enabled') and self._is_outlier_candle(atr_multiplier=cfg.get('outlier_atr_multiplier', 3.5)):
            # _is_outlier_candle logs its own criteria, so we just need the final decision
            self._log_final_decision("HOLD", "Outlier Candle Shield activated.")
            return None
        
        market_regime, adx_val = self._get_market_regime(adx_threshold=cfg.get('regime_adx_threshold', 21.0))
        required_regime = cfg.get('required_regime', 'TRENDING')
        regime_ok = market_regime == required_regime
        self._log_criteria("Market Regime Filter", regime_ok, f"Market is '{market_regime}' (ADX={adx_val:.2f}), Required: '{required_regime}'")
        if cfg.get('market_regime_filter_enabled') and not regime_ok:
            self._log_final_decision("HOLD", f"Market regime '{market_regime}' does not match required '{required_regime}'.")
            return None

        entry_price = self.price_data.get('close')
        atr_val = (indicators['atr'].get('values') or {}).get('atr')
        breakout_level = keltner_analysis.get('breakout_level')
        if self._is_valid_number(entry_price) and self._is_valid_number(atr_val) and self._is_valid_number(breakout_level):
            max_dist = cfg.get('late_entry_atr_mult', 1.2) * atr_val
            current_dist = abs(entry_price - breakout_level)
            entry_ok = current_dist <= max_dist
            self._log_criteria("Late-Entry Guard", entry_ok, f"Distance from breakout: {current_dist:.5f} vs Max allowed: {max_dist:.5f}")
            if not entry_ok:
                self._log_final_decision("HOLD", "Late-Entry Guard: Price is too far from the breakout level.")
                return None
        else:
             self._log_criteria("Late-Entry Guard", False, "Could not validate entry price against breakout level (missing values).")

        if cfg.get('exhaustion_shield_enabled'):
            is_exhausted = self._is_trend_exhausted_dynamic(
                direction=signal_direction,
                rsi_lookback=cfg.get('rsi_exhaustion_lookback', 200),
                rsi_buy_percentile=cfg.get('rsi_buy_percentile', 90),
                rsi_sell_percentile=cfg.get('rsi_sell_percentile', 10)
            )
            # _is_trend_exhausted_dynamic logs its own criteria on failure
            if is_exhausted:
                self._log_final_decision("HOLD", "Adaptive Trend Exhaustion Shield activated.")
                return None
            self._log_criteria("Exhaustion Shield", True, "Trend is not exhausted.")
        
        # --- 5. Quantum Scoring Engine ---
        min_score = self._get_min_score_for_tf(cfg.get('min_momentum_score', {}))
        momentum_score, score_details = self._calculate_momentum_score(signal_direction, indicators)
        score_ok = momentum_score >= min_score
        self._log_criteria("Momentum Score Check", score_ok, f"Score={momentum_score} vs min={min_score} ({', '.join(score_details)})")
        if not score_ok:
            self._log_final_decision("HOLD", f"Momentum score {momentum_score} is below minimum required {min_score}.")
            return None

        # --- 6. Blueprint Generation (SL & TP Logic) ---
        keltner_values = (indicators['keltner_channel'].get('values') or {})
        structural_sl_level = keltner_values.get('middle_band')
        
        sl_logic = {}
        if self._is_valid_number(structural_sl_level) and self._is_valid_number(atr_val) and self._is_valid_number(entry_price):
            sl_dist = abs(entry_price - structural_sl_level)
            max_sl_dist = cfg.get('max_structural_sl_atr_mult', 2.5) * atr_val
            if sl_dist > max_sl_dist:
                sl_logic = {'type': 'atr_based', 'atr_multiplier': cfg.get('atr_sl_multiplier', 1.5)}
                self._log_criteria("SL Logic Selection", True, f"Structural SL too far ({sl_dist:.5f} > {max_sl_dist:.5f}). Using ATR-based SL.")
            else:
                sl_logic = {'type': 'structural', 'level_name': 'middle_band', 'indicator': 'keltner_channel'}
                self._log_criteria("SL Logic Selection", True, "Using Keltner middle band as structural SL.")
        else:
            self._log_final_decision("HOLD", "Could not calculate valid SL logic due to missing price/indicator values.")
            return None
        
        tp_logic = {'type': 'atr_multiple', 'multiples': cfg.get('target_atr_multiples', [1.5, 3.0, 4.5])}

        # --- 7. Finalize and Validate ---
        self.last_signal_bar = current_bar
        
        blueprint = { 
            "direction": signal_direction, 
            "entry_price": entry_price, 
            "trade_mode": "Early Strike Breakout",
            "sl_logic": sl_logic,
            "tp_logic": tp_logic,
            "confirmations": {"power_score": momentum_score, "details": ", ".join(score_details)}
        }
        
        if self._validate_blueprint(blueprint):
            self._log_final_decision(signal_direction, "All criteria met. Keltner Early Strike blueprint generated.")
            return blueprint

        # This case should be rare as _validate_blueprint logs errors, but serves as a final catch-all.
        self._log_final_decision("HOLD", "Generated blueprint failed final validation check.")
        return None
