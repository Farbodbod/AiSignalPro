#BollingerBandsDirectedMaestro - (v14.0 - The Quantum Conductor)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v14.0 - The Quantum Conductor)
    -------------------------------------------------------------------------
    This definitive version completes the Quantum Roadmap, transforming the Maestro
    from a talented soloist into a true Quantum Conductor of the market orchestra.

    🚀 KEY EVOLUTIONS in v14.0:
    1.  **Quantum Risk Engine Integration:** The legacy Blueprint system is fully
        excised. All three fronts (Squeeze, Ranging, Trending) are now directly
        wired into the `_orchestrate_static_risk` engine, enabling elite,
        structurally-aware risk management with anti-stop-hunt/anti-front-running logic.
    2.  **Adaptive Regime Gatekeeper:** Static ADX thresholds are replaced with
        adaptive percentile-based logic, ensuring the strategy operates only
        in statistically validated market regimes.
    3.  **Reinforced Confirmation Squads:** MACD is now integrated as a momentum
        specialist across all three scoring engines, adding a critical layer of
        confirmation to every signal.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0,
      
      # ✅ UPGRADED: Regime Detection now uses adaptive percentiles
      "max_adx_percentile_for_ranging": 45.0,
      "min_adx_percentile_for_trending": 70.0,
      
      # --- Risk Management (Now handled by Quantum Grid Engine) ---
      # NOTE: These multipliers are no longer used for SL but kept for potential future analytics.
      "sl_atr_buffer_multipliers": {"squeeze": 0.6, "ranging": 1.1, "trending": 0.7},
      
      # --- Squeeze Engine Calibration (✅ UPGRADED) ---
      "min_squeeze_score": 6, # Recalibrated
      "weights_squeeze": {
          "bollinger_breakout": {"strong": 3, "medium": 2},
          "momentum_confirmation": 3,
          "momentum_rsi_thresholds": {"buy": 52, "sell": 48},
          "volume_spike_confirmation": 2,
          "htf_alignment": 2,
          "macd_aligned": 2 # New Specialist
      },
      
      # --- Ranging Engine Calibration (✅ UPGRADED) ---
      "min_ranging_score": 9, # Recalibrated
      "ranging_proximity_atr_mult": 0.25,
      "weights_ranging": {
          "rsi_reversal": 3, "divergence_confirmation": 3, "volume_fade": 2,
          "candlestick": {"weak": 1, "medium": 2, "strong": 4},
          "macd_aligned": 2 # New Specialist
      },
      "ranging_rsi_dynamic_enabled": True, "ranging_rsi_lookback": 100,
      "ranging_rsi_buy_percentile": 15, "ranging_rsi_sell_percentile": 85,

      # --- Trending Engine Calibration (✅ UPGRADED) ---
      "min_trending_score": 10, # Recalibrated
      "trending_rsi_zones": {"buy_min": 45, "buy_max": 65, "sell_min": 35, "sell_max": 55},
      "weights_trending": {
          "htf_alignment": 4, "rsi_cooldown": 3, "adx_acceleration_confirmation": 2, "adx_strength": 1,
          "macd_aligned": 2 # New Specialist
      },

      # ✅ UPGRADED: HTF now uses adaptive percentiles
      "htf_confirmation_enabled": True,
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_percentile": 70.0},"supertrend": {"weight": 1}},
      "allow_mixed_mode": False
    }

    # NOTE: This helper is now deprecated as SL is handled by the Quantum Grid Engine.
    # Kept for reference.
    def _calculate_dynamic_sl_multiplier(self, regime: str, current_price: float, atr_value: float) -> float:
        return self._safe_get(self.config, ['sl_atr_buffer_multipliers', regime], 1.0)

    def check_signal(self) -> Optional[Dict[str, Any]]:
        if not self.price_data: return None
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price):
            self._log_final_decision("HOLD", f"Invalid current_price: {current_price}"); return None

        # ✅ UPGRADED: Added dependencies for new engine integrations
        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr', 'divergence', 
                    'macd', 'pivots', 'structure', 'fibonacci', 'supertrend']
        indicators = {name: self.get_indicator(name) for name in set(required)}
        
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Required indicators missing: {', '.join(missing)}"); return None
        
        squeeze_signal = self._check_squeeze_front(current_price, indicators)
        if squeeze_signal: return squeeze_signal
        
        # ✅ UPGRADED: Adaptive Regime Detection
        adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
        max_pct_ranging = self.config.get('max_adx_percentile_for_ranging', 45.0)
        min_pct_trending = self.config.get('min_adx_percentile_for_trending', 70.0)

        market_regime = "RANGING" if adx_percentile <= max_pct_ranging else \
                        "TRENDING" if adx_percentile >= min_pct_trending else "UNCERTAIN"
        self._log_criteria("Path Check: Market Regime (Adaptive)", market_regime != "UNCERTAIN", f"ADX Percentile={adx_percentile:.2f}% -> Regime: {market_regime}")

        if market_regime == "RANGING":
            return self._check_ranging_front(current_price, indicators)
        elif market_regime == "TRENDING":
            return self._check_trending_front(current_price, indicators)
        
        self._log_final_decision("HOLD", f"Market regime is '{market_regime}', no actionable setup found.")
        return None

    def _check_squeeze_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config; is_squeeze = self._safe_get(indicators, ['bollinger', 'analysis', 'is_squeeze_release'], False)
        self._log_criteria("Path Check: Squeeze", is_squeeze, f"Squeeze Release detected: {is_squeeze}")
        if not is_squeeze: return None
        
        score, weights, min_score = 0, cfg['weights_squeeze'], cfg['min_squeeze_score']
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], {})
        trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], '').lower()
        temp_direction = "BUY" if "bullish" in trade_signal else "SELL" if "bearish" in trade_signal else None
        if not temp_direction: self._log_final_decision("HOLD", "Squeeze detected but direction unclear."); return None

        score += weights.get('bollinger_breakout', {}).get(self._safe_get(bollinger_analysis, ['strength'], '').lower(), 0)
        
        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        rsi_thresholds = weights.get('momentum_rsi_thresholds', {"buy": 52, "sell": 48})
        if rsi_val and ((temp_direction == "BUY" and rsi_val > rsi_thresholds['buy']) or (temp_direction == "SELL" and rsi_val < rsi_thresholds['sell'])):
            score += weights.get('momentum_confirmation', 0)

        if self._safe_get(indicators, ['volume', 'analysis', 'is_climactic_volume'], False):
            score += weights.get('volume_spike_confirmation', 0)
        
        if self._get_trend_confirmation(temp_direction): score += weights.get('htf_alignment', 0)
        
        # ✅ New Specialist: MACD
        histo = self._safe_get(indicators, ['macd', 'values', 'histogram'], 0)
        if (temp_direction == "BUY" and histo > 0) or (temp_direction == "SELL" and histo < 0):
            score += weights.get('macd_aligned', 0)

        if score >= min_score:
            middle_band_anchor = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
            risk_params = self._orchestrate_static_risk(temp_direction, current_price, middle_band_anchor)
            if risk_params:
                self._log_final_decision(temp_direction, f"Squeeze Breakout triggered (Score: {score})"); 
                risk_params["confirmations"] = {"final_score": score, "trade_mode": "Squeeze Breakout"}; return risk_params

        self._log_final_decision("HOLD", f"Squeeze conditions not met (Score: {score} < {min_score})."); return None

    def _check_ranging_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config; lower_band, upper_band, atr_value = (self._safe_get(indicators, ['bollinger', 'values', 'lower_band']), 
                                                               self._safe_get(indicators, ['bollinger', 'values', 'upper_band']),
                                                               self._safe_get(indicators, ['atr', 'values', 'atr']))
        if not all(self._is_valid_number(v) for v in [lower_band, upper_band, atr_value]):
             self._log_final_decision("HOLD", "Missing values for Ranging check."); return None

        proximity = atr_value * cfg.get('ranging_proximity_atr_mult', 0.25)
        temp_direction = "BUY" if current_price <= (lower_band + proximity) else "SELL" if current_price >= (upper_band - proximity) else None
        
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg['weights_ranging'], cfg['min_ranging_score']
            
            if cfg.get('ranging_rsi_dynamic_enabled', True):
                if self._is_trend_exhausted_dynamic(temp_direction, cfg.get('ranging_rsi_lookback',100), cfg.get('ranging_rsi_buy_percentile',15), cfg.get('ranging_rsi_sell_percentile',85)):
                    score += weights.get('rsi_reversal', 0)
            
            div_analysis = self._safe_get(indicators, ['divergence', 'analysis'], {})
            if (temp_direction == "BUY" and div_analysis.get('has_regular_bullish_divergence')) or (temp_direction == "SELL" and div_analysis.get('has_regular_bearish_divergence')):
                score += weights.get('divergence_confirmation', 0)

            if self._safe_get(indicators, ['volume', 'analysis', 'is_below_average'], False):
                score += weights.get('volume_fade', 0)
            
            candle_info = self._get_candlestick_confirmation(temp_direction, min_reliability='Medium')
            if candle_info: score += weights.get('candlestick', {}).get(self._safe_get(candle_info, ['reliability'], 'weak').lower(), 0)

            # ✅ New Specialist: MACD
            histo = self._safe_get(indicators, ['macd', 'values', 'histogram'], 0)
            if (temp_direction == "BUY" and histo > 0) or (temp_direction == "SELL" and histo < 0):
                score += weights.get('macd_aligned', 0)

            if score >= min_score:
                sl_anchor = lower_band if temp_direction == "BUY" else upper_band
                risk_params = self._orchestrate_static_risk(temp_direction, current_price, sl_anchor)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Mean Reversion triggered (Score: {score})");
                    risk_params["confirmations"] = {"final_score": score, "trade_mode": "Mean Reversion"}; return risk_params
        
        self._log_final_decision("HOLD", "Ranging conditions not fully met."); return None

    def _check_trending_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config; middle_band = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = None
        if middle_band:
            if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: temp_direction = "BUY"
            elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: temp_direction = "SELL"
        
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg['weights_trending'], cfg['min_trending_score']
            score += weights.get('htf_alignment', 0)
            
            rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
            rsi_zones = cfg.get('trending_rsi_zones', {})
            if rsi_val and ((temp_direction == "BUY" and rsi_zones.get('buy_min', 45) < rsi_val < rsi_zones.get('buy_max', 65)) or (temp_direction == "SELL" and rsi_zones.get('sell_min', 35) < rsi_val < rsi_zones.get('sell_max', 55))):
                score += weights.get('rsi_cooldown', 0)
            
            adx_series = self._safe_get(indicators, ['adx', 'series'], [])
            if len(adx_series) >= 3 and adx_series[-1] > adx_series[-3]:
                score += weights.get('adx_acceleration_confirmation', 0)
            
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            if adx_percentile >= cfg.get('min_adx_percentile_for_trending', 70.0):
                score += weights.get('adx_strength', 0)

            # ✅ New Specialist: MACD
            histo = self._safe_get(indicators, ['macd', 'values', 'histogram'], 0)
            if (temp_direction == "BUY" and histo > 0) or (temp_direction == "SELL" and histo < 0):
                score += weights.get('macd_aligned', 0)

            if score >= min_score:
                risk_params = self._orchestrate_static_risk(temp_direction, current_price, middle_band)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Pullback triggered (Score: {score})"); 
                    risk_params["confirmations"] = {"final_score": score, "trade_mode": "Pullback"}; return risk_params

        self._log_final_decision("HOLD", "Trending conditions not fully met."); return None

