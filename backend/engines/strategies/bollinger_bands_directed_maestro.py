# backend/engines/strategies/bollinger_bands_directed_maestro.py (v11.1 - Architecturally Pure)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

# ✅ ARCHITECTURAL FIX: Use standard __name__ for the logger.
logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v11.1 - Architecturally Pure)
    -------------------------------------------------------------------------
    This is the definitive, Gold Master version of the Trinity Hunter. It has
    been fully purified to align with the BaseStrategy v14.0+ architecture by:
    1.  Correcting the logger initialization to the standard '__name__'.
    2.  Removing redundant local helper methods (_safe_get, _validate_blueprint)
        and now relies on the centralized, inherited versions from the base class.
    This represents the pinnacle of our architectural standards for robustness,
    clarity, and code reuse.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0,
      "max_adx_for_ranging": 22.0, "min_adx_for_trending": 23.0,
      
      "sl_atr_buffer_multipliers": {"squeeze": 0.6, "ranging": 1.1, "trending": 0.7},
      "max_sl_multiplier_cap": 2.5, "vol_ratio_cap": 0.1,
      
      "min_squeeze_score": 5,
      "weights_squeeze": {
          "bollinger_breakout": 3,
          "momentum_confirmation": 3,
          "volume_spike_confirmation": 2,
          "htf_alignment": 2
      },
      
      "min_ranging_score": 6,
      "weights_ranging": {
          "rsi_reversal": 3,
          "divergence_confirmation": 4,
          "volume_fade": 2,
          "candlestick": {"weak": 1, "medium": 2, "strong": 3}
      },
      
      "min_trending_score": 7,
      "weights_trending": {
          "htf_alignment": 4,
          "rsi_cooldown": 3,
          "adx_acceleration_confirmation": 2,
          "adx_strength": 1
      },
      "trending_tp_logic": {"type": "atr_multiple", "multiples": [2.5, 4.0, 6.0]},

      "htf_confirmation_enabled": True,
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { "min_required_score": 1, "adx": {"weight": 1, "min_strength": 22}, "supertrend": {"weight": 1}},
      "allow_mixed_mode": False
    }

    # ✅ ARCHITECTURAL FIX: _safe_get and _validate_blueprint are now inherited from BaseStrategy v14.0
    # No need for local implementations.

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price) or current_price <= 0:
            self._log_final_decision("HOLD", f"Invalid current_price: {current_price}"); return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr', 'divergence']
        indicators = {name: self.get_indicator(name) for name in required}
        
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            self._log_final_decision("HOLD", f"Required indicators are missing: {', '.join(missing_indicators)}"); return None
        
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if atr_value is None: self._log_final_decision("HOLD", "ATR value is missing."); return None
        
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], default={})
        bollinger_values = self._safe_get(indicators, ['bollinger', 'values'], default={})
        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        volume_analysis = self._safe_get(indicators, ['volume', 'analysis'], default={})
        adx_series = self._safe_get(indicators, ['adx', 'series'], default=[])
        divergence_analysis = self._safe_get(indicators, ['divergence', 'analysis'], default={})
        _, adx_value = self._get_market_regime(0)
        adx_display = f"{adx_value:.2f}" if adx_value is not None else "N/A"
        
        # --- SQUEEZE FRONT ---
        is_squeeze = self._safe_get(bollinger_analysis, ['is_squeeze_release'], False)
        self._log_criteria("Path Check: Squeeze", is_squeeze, f"Squeeze Release detected: {is_squeeze}")
        if is_squeeze:
            trade_mode = "Squeeze Breakout"
            score, weights, min_score = 0, cfg['weights_squeeze'], cfg['min_squeeze_score']
            trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], default='')
            temp_direction = "BUY" if "Bullish" in trade_signal else "SELL" if "Bearish" in trade_signal else None
            
            if temp_direction:
                strength_ok = self._safe_get(bollinger_analysis, ['strength']) == 'Strong'
                self._log_criteria("Squeeze: Bollinger Breakout", strength_ok, "Breakout confirmed by BB strength.")
                if strength_ok: score += weights['bollinger_breakout']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and rsi_val > 55) or (temp_direction == "SELL" and rsi_val < 45))
                self._log_criteria("Squeeze: Momentum Confirmation", rsi_ok, f"RSI={rsi_val:.2f} confirms momentum.")
                if rsi_ok: score += weights['momentum_confirmation']

                volume_spike_ok = self._safe_get(volume_analysis, ['is_climactic_volume'], False)
                self._log_criteria("Squeeze: Volume Spike", volume_spike_ok, "Climactic volume confirms interest.")
                if volume_spike_ok: score += weights['volume_spike_confirmation']
                
                htf_ok = self._get_trend_confirmation(temp_direction)
                self._log_criteria("Squeeze: HTF Alignment", htf_ok, "HTF trend confirms breakout direction.")
                if htf_ok: score += weights['htf_alignment']

                if score >= min_score:
                    vol_ratio = atr_value / current_price
                    clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['squeeze']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "atr_multiple", "multiples": [2.0, 3.5, 5.0]},
                        "confirmations": {"final_score": score}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        return blueprint
            self._log_final_decision("HOLD", f"Squeeze conditions not fully met.")
            return None
        
        # --- RANGING / TRENDING FRONTS ---
        market_regime = "RANGING" if adx_value is not None and adx_value <= cfg['max_adx_for_ranging'] else "TRENDING" if adx_value is not None and adx_value >= cfg['min_adx_for_trending'] else "UNCERTAIN"
        self._log_criteria("Path Check: Market Regime", market_regime != "UNCERTAIN", f"ADX={adx_display} -> Regime: {market_regime}")
        
        if market_regime == "RANGING":
            trade_mode = "Mean Reversion"
            lower_band = self._safe_get(bollinger_values, ['lower_band'])
            upper_band = self._safe_get(bollinger_values, ['upper_band'])
            temp_direction = "BUY" if current_price <= lower_band else "SELL" if current_price >= upper_band else None
            
            if temp_direction and cfg['direction'] in [0, 1 if temp_direction == "BUY" else -1]:
                score, weights, min_score = 0, cfg['weights_ranging'], cfg['min_ranging_score']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and rsi_val < 30) or (temp_direction == "SELL" and rsi_val > 70))
                self._log_criteria("Ranging: RSI Reversal", rsi_ok, f"RSI={rsi_val:.2f} shows over-extension.")
                if rsi_ok: score += weights['rsi_reversal']
                
                divergence_ok = (temp_direction == "BUY" and self._safe_get(divergence_analysis, ['has_bullish_divergence'])) or \
                                (temp_direction == "SELL" and self._safe_get(divergence_analysis, ['has_bearish_divergence']))
                self._log_criteria("Ranging: Divergence Confirmation", divergence_ok, "RSI divergence confirms reversal potential.")
                if divergence_ok: score += weights['divergence_confirmation']

                volume_ok = self._safe_get(volume_analysis, ['is_below_average'], False)
                self._log_criteria("Ranging: Volume Fade", volume_ok, "Volume is below average, confirming exhaustion.")
                if volume_ok: score += weights['volume_fade']
                
                candle_info = self._get_candlestick_confirmation(temp_direction)
                if candle_info:
                    strength = self._safe_get(candle_info, ['strength'], default='weak').lower()
                    if strength in weights['candlestick']: score += weights['candlestick'][strength]
                
                if score >= min_score:
                    vol_ratio = atr_value / current_price
                    clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['ranging']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "sl_logic": {"type": "band", "band_name": "lower_band" if temp_direction == "BUY" else "upper_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "range_targets", "targets": ["middle_band", "opposite_band"]},
                        "confirmations": {"final_score": score}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        return blueprint
            self._log_final_decision("HOLD", f"Ranging conditions not fully met.")
            return None

        elif market_regime == "TRENDING":
            trade_mode = "Pullback"
            middle_band = self._safe_get(bollinger_values, ['middle_band'])
            price_low = self._safe_get(self.price_data, ['low'])
            price_high = self._safe_get(self.price_data, ['high'])
            temp_direction = None
            if middle_band and price_low and price_high:
                if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: temp_direction = "BUY"
                elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: temp_direction = "SELL"
            
            if temp_direction:
                score, weights, min_score = 0, cfg['weights_trending'], cfg['min_trending_score']
                
                score += weights['htf_alignment']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and 40 < rsi_val < 70) or (temp_direction == "SELL" and 30 < rsi_val < 60))
                self._log_criteria("Trending: RSI Cooldown", rsi_ok, f"RSI={rsi_val:.2f} is in healthy pullback zone.")
                if rsi_ok: score += weights['rsi_cooldown']
                
                adx_accel_ok = len(adx_series) >= 3 and adx_series[-1] > adx_series[-3]
                self._log_criteria("Trending: ADX Acceleration", adx_accel_ok, "ADX is rising, confirming trend strength.")
                if adx_accel_ok: score += weights['adx_acceleration_confirmation']
                
                adx_ok = adx_value is not None and adx_value >= cfg['min_adx_for_trending']
                if adx_ok: score += weights['adx_strength']

                if score >= min_score:
                    vol_ratio = atr_value / current_price
                    clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['trending']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": cfg.get("trending_tp_logic"),
                        "confirmations": {"final_score": score, "adx_strength": adx_value}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        return blueprint
            self._log_final_decision("HOLD", f"Trending conditions not fully met.")
            return None
        
        self._log_final_decision("HOLD", f"Market regime is '{market_regime}', no actionable setup found.")
        return None
