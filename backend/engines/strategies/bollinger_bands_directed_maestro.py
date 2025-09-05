# backend/engines/strategies/bollinger_bands_directed_maestro.py (v13.0 - Dynamic RSI Integration)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v13.0 - Dynamic RSI Integration)
    -------------------------------------------------------------------------
    This version enhances the Mean Reversion engine by integrating the dynamic,
    percentile-based RSI exhaustion shield from the BaseStrategy. This replaces
    the static 30/70 RSI levels with an adaptive system that attunes itself
    to the specific volatility character of each market, increasing the
    strategy's intelligence and adaptability in ranging conditions.

    🚀 KEY EVOLUTIONS in v13.0:
    1.  **Dynamic RSI Logic:** The Ranging Front now uses the advanced
        `_is_trend_exhausted_dynamic` helper for more intelligent and adaptive
        entry signals.
    2.  **Enhanced Configurability:** New parameters have been added to the
        default_config to give full control over the new dynamic RSI logic.
    3.  **Backward Compatibility:** The new feature is switchable; if disabled,
        the strategy gracefully falls back to the classic static 30/70 levels.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0,
      
      # --- Regime Detection ---
      "max_adx_for_ranging": 22.0, "min_adx_for_trending": 23.0,
      
      # --- Risk Management ---
      "sl_atr_buffer_multipliers": {"squeeze": 0.6, "ranging": 1.1, "trending": 0.7},
      "max_sl_multiplier_cap": 2.5, "vol_ratio_cap": 0.1,
      
      # --- Squeeze Engine Calibration ---
      "min_squeeze_score": 4,
      "weights_squeeze": {
          "bollinger_breakout": {"strong": 3, "medium": 2},
          "momentum_confirmation": 3,
          "momentum_rsi_thresholds": {"buy": 52, "sell": 48},
          "volume_spike_confirmation": 2,
          "htf_alignment": 2
      },
      
      # --- Ranging Engine Calibration ---
      "min_ranging_score": 7,
      "ranging_proximity_atr_mult": 0.25,
      "weights_ranging": {
          "rsi_reversal": 3, "divergence_confirmation": 3, "volume_fade": 2,
          "candlestick": {"weak": 1, "medium": 2, "strong": 4}
      },
      # Ranging Engine - Dynamic RSI Configuration
      "ranging_rsi_dynamic_enabled": True,
      "ranging_rsi_lookback": 100,
      "ranging_rsi_buy_percentile": 15,
      "ranging_rsi_sell_percentile": 85,

      # --- Trending Engine Calibration ---
      "min_trending_score": 8,
      "trending_rsi_zones": {"buy_min": 45, "buy_max": 65, "sell_min": 35, "sell_max": 55},
      "weights_trending": {
          "htf_alignment": 4, "rsi_cooldown": 3, "adx_acceleration_confirmation": 2, "adx_strength": 1
      },
      "trending_tp_logic": {
          "type": "atr_multiple_by_trend_strength",
          "adx_thresholds": { "strong": 40, "normal": 23 },
          "multiples_map": {
            "strong": [3.0, 5.0, 7.0], "normal": [2.5, 4.0, 6.0], "weak": [1.8, 3.0, 4.0]
          }
      },

      "htf_confirmation_enabled": True,
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_strength": 22},"supertrend": {"weight": 1}},
      "allow_mixed_mode": False
    }

    def _calculate_dynamic_sl_multiplier(self, regime: str, current_price: float, atr_value: float) -> float:
        """Helper to calculate the volatility-adaptive SL multiplier."""
        cfg = self.config
        vol_ratio = atr_value / current_price if current_price > 0 else 0
        clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))
        base_multiplier = self._safe_get(cfg, ['sl_atr_buffer_multipliers', regime], 1.0)
        dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
        final_multiplier = min(dynamic_multiplier, cfg.get('max_sl_multiplier_cap', 2.5))
        return final_multiplier

    def check_signal(self) -> Optional[Dict[str, Any]]:
        if not self.price_data: return None
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price):
            self._log_final_decision("HOLD", f"Invalid current_price: {current_price}"); return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr', 'divergence']
        indicators = {name: self.get_indicator(name) for name in required}
        
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Required indicators missing: {', '.join(missing)}"); return None
        
        squeeze_signal = self._check_squeeze_front(current_price, indicators)
        if squeeze_signal: return squeeze_signal
        
        _, adx_value = self._get_market_regime(0)
        adx_display = f"{adx_value:.2f}" if adx_value is not None else "N/A"
        market_regime = "RANGING" if adx_value <= self.config['max_adx_for_ranging'] else \
                        "TRENDING" if adx_value >= self.config['min_adx_for_trending'] else "UNCERTAIN"
        self._log_criteria("Path Check: Market Regime", market_regime != "UNCERTAIN", f"ADX={adx_display} -> Regime: {market_regime}")

        if market_regime == "RANGING":
            return self._check_ranging_front(current_price, indicators)
        elif market_regime == "TRENDING":
            return self._check_trending_front(current_price, indicators, adx_value)
        
        self._log_final_decision("HOLD", f"Market regime is '{market_regime}', no actionable setup found.")
        return None

    def _check_squeeze_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], {})
        is_squeeze = self._safe_get(bollinger_analysis, ['is_squeeze_release'], False)
        self._log_criteria("Path Check: Squeeze", is_squeeze, f"Squeeze Release detected: {is_squeeze}")
        if not is_squeeze: return None
        
        trade_mode = "Squeeze Breakout"
        score, weights, min_score = 0, cfg['weights_squeeze'], cfg['min_squeeze_score']
        trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], '').lower()
        temp_direction = "BUY" if "bullish" in trade_signal else "SELL" if "bearish" in trade_signal else None
        
        if not temp_direction: self._log_final_decision("HOLD", "Squeeze detected but direction is unclear."); return None

        strength_value = self._safe_get(bollinger_analysis, ['strength'], '').lower()
        score += weights.get('bollinger_breakout', {}).get(strength_value, 0)
        
        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        rsi_thresholds = weights.get('momentum_rsi_thresholds', {"buy": 52, "sell": 48})
        if rsi_val and ((temp_direction == "BUY" and rsi_val > rsi_thresholds['buy']) or (temp_direction == "SELL" and rsi_val < rsi_thresholds['sell'])):
            score += weights.get('momentum_confirmation', 3)

        if self._safe_get(indicators, ['volume', 'analysis', 'is_climactic_volume'], False):
            score += weights.get('volume_spike_confirmation', 2)
        
        if self._get_trend_confirmation(temp_direction):
            score += weights.get('htf_alignment', 2)

        if score >= min_score:
            atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
            if not atr_value: self._log_final_decision("HOLD", "ATR value missing for SL calculation."); return None
            
            final_multiplier = self._calculate_dynamic_sl_multiplier('squeeze', current_price, atr_value)
            
            blueprint = { "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                "tp_logic": {"type": "atr_multiple", "multiples": [2.0, 3.5, 5.0]},
                "confirmations": {"final_score": score} }
            if self._validate_blueprint(blueprint):
                self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})"); return blueprint

        self._log_final_decision("HOLD", f"Squeeze conditions not fully met (Score: {score} < {min_score})."); return None

    def _check_ranging_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg, trade_mode = self.config, "Mean Reversion"
        lower_band = self._safe_get(indicators, ['bollinger', 'values', 'lower_band'])
        upper_band = self._safe_get(indicators, ['bollinger', 'values', 'upper_band'])
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if not all(self._is_valid_number(v) for v in [lower_band, upper_band, atr_value]):
             self._log_final_decision("HOLD", "Missing Bollinger or ATR values for Ranging check."); return None

        proximity_zone = atr_value * cfg.get('ranging_proximity_atr_mult', 0.25)
        temp_direction = "BUY" if current_price <= (lower_band + proximity_zone) else "SELL" if current_price >= (upper_band - proximity_zone) else None
        
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg['weights_ranging'], cfg['min_ranging_score']
            
            # --- DYNAMIC RSI LOGIC UPGRADE v13.0 ---
            rsi_ok = False
            if cfg.get('ranging_rsi_dynamic_enabled', True):
                rsi_ok = self._is_trend_exhausted_dynamic(
                    direction=temp_direction,
                    rsi_lookback=cfg.get('ranging_rsi_lookback', 100),
                    rsi_buy_percentile=cfg.get('ranging_rsi_buy_percentile', 15),
                    rsi_sell_percentile=cfg.get('ranging_rsi_sell_percentile', 85)
                )
                # _is_trend_exhausted_dynamic logs its own failure reason
            else: # Fallback to static logic
                rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
                rsi_ok = rsi_val and ((temp_direction == "BUY" and rsi_val < 30) or (temp_direction == "SELL" and rsi_val > 70))
                self._log_criteria("Ranging: RSI Reversal (Static)", rsi_ok, f"RSI={rsi_val:.2f} vs 30/70")
            
            if rsi_ok: score += weights.get('rsi_reversal', 3)
            # --- END OF UPGRADE ---
            
            divergence_analysis = self._safe_get(indicators, ['divergence', 'analysis'], {})
            if (temp_direction == "BUY" and divergence_analysis.get('has_bullish_divergence')) or (temp_direction == "SELL" and divergence_analysis.get('has_bearish_divergence')):
                score += weights.get('divergence_confirmation', 3)

            if self._safe_get(indicators, ['volume', 'analysis', 'is_below_average'], False):
                score += weights.get('volume_fade', 2)
            
            candle_info = self._get_candlestick_confirmation(temp_direction, min_reliability='Medium')
            if candle_info:
                strength = self._safe_get(candle_info, ['reliability'], 'weak').lower()
                score += weights.get('candlestick', {}).get(strength, 0)
            
            if score >= min_score:
                final_multiplier = self._calculate_dynamic_sl_multiplier('ranging', current_price, atr_value)
                blueprint = {
                    "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                    "sl_logic": {"type": "band", "band_name": "lower_band" if temp_direction == "BUY" else "upper_band", "buffer_atr_multiplier": final_multiplier},
                    "tp_logic": {"type": "range_targets", "targets": ["middle_band", "opposite_band"]},
                    "confirmations": {"final_score": score}
                }
                if self._validate_blueprint(blueprint):
                    self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})"); return blueprint
        
        self._log_final_decision("HOLD", "Ranging conditions not fully met."); return None

    def _check_trending_front(self, current_price: float, indicators: Dict, adx_value: float) -> Optional[Dict[str, Any]]:
        cfg, trade_mode = self.config, "Pullback"
        middle_band = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = None
        if middle_band:
            if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: temp_direction = "BUY"
            elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: temp_direction = "SELL"
        
        if temp_direction:
            score, weights, min_score = 0, cfg['weights_trending'], cfg['min_trending_score']
            score += weights.get('htf_alignment', 4)
            
            rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
            rsi_zones = cfg.get('trending_rsi_zones', {})
            if rsi_val and ((temp_direction == "BUY" and rsi_zones.get('buy_min', 45) < rsi_val < rsi_zones.get('buy_max', 65)) or (temp_direction == "SELL" and rsi_zones.get('sell_min', 35) < rsi_val < rsi_zones.get('sell_max', 55))):
                score += weights.get('rsi_cooldown', 3)
            
            adx_series = self._safe_get(indicators, ['adx', 'series'], [])
            if len(adx_series) >= 3 and adx_series[-1] > adx_series[-3]:
                score += weights.get('adx_acceleration_confirmation', 2)
            
            if adx_value >= cfg['min_adx_for_trending']:
                score += weights.get('adx_strength', 1)

            if score >= min_score:
                atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
                if not atr_value: self._log_final_decision("HOLD", "ATR value missing for SL calculation."); return None
                
                final_multiplier = self._calculate_dynamic_sl_multiplier('trending', current_price, atr_value)
                blueprint = {
                    "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                    "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                    "tp_logic": cfg.get("trending_tp_logic"),
                    "confirmations": {"final_score": score, "adx_strength": round(adx_value, 2)}
                }
                if self._validate_blueprint(blueprint):
                    self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})"); return blueprint

        self._log_final_decision("HOLD", "Trending conditions not fully met."); return None
