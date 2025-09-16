# backend/engines/strategies/BollingerBandsDirectedMaestro.py (v16.3 - The Final Architecture Harmonization)

import logging
from typing import Dict, Any, Optional, ClassVar

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v16.3 - The Final Architecture Harmonization)
    ---------------------------------------------------------------------------------
    This definitive version achieves flawless harmonization with the project's
    established architecture. Based on a final expert review, the 'indicator_configs'
    structure has been corrected to a flat format, removing the unnecessary 'params'
    key to ensure perfect compatibility and performance with the main engine. All
    strategic and logical upgrades from v16.1 are preserved. This version is now
    considered architecturally perfect and complete.
    """
    strategy_name: "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0,
      
      "ranging_trigger_proximity_atr_mult": 0.75,

      "indicator_configs": {
        "ranging_divergence": {
            "name": "divergence",
            "dependencies": {
                "zigzag": { "deviation": 1.0 }
            }
        }
      },

      "max_adx_percentile_for_ranging": 45.0,
      "min_adx_percentile_for_trending": 70.0,
      "min_squeeze_score": 6,
      "weights_squeeze": {
          "bollinger_breakout": {"strong": 3, "medium": 2}, "momentum_confirmation": 3,
          "volume_spike_confirmation": 2, "htf_alignment": 2, "macd_aligned": 2
      },
      "min_ranging_score": 7,
      "weights_ranging": {
          "rsi_reversal": 4, "divergence_confirmation": 3, "volume_fade": 2,
          "candlestick": {"weak": 1, "medium": 2, "strong": 4}, "macd_aligned": 2
      },
      "ranging_rsi_oversold": 35.0, "ranging_rsi_overbought": 65.0,
      "min_trending_score": 10,
      "weights_trending": {
          "htf_alignment": 4, "rsi_cooldown": 3, "adx_acceleration_confirmation": 2,
          "adx_strength": 1, "macd_aligned": 2
      },
      "trending_rsi_zones": {"buy_min": 45, "buy_max": 65, "sell_min": 35, "sell_max": 55},
      "htf_confirmation_enabled": True,
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_percentile": 70.0},"supertrend": {"weight": 1}},
      "allow_mixed_mode": False
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        if not self.price_data: return None
        current_price = self.price_data.get('close')
        if not self._is_valid_number(current_price) or current_price <= 0:
            self._log_final_decision("HOLD", f"Invalid current_price: {current_price}"); return None
        
        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr', 'divergence', 'macd', 'pivots', 'structure', 'supertrend', 'ranging_divergence']

        indicators = {name: self.get_indicator(name) for name in set(required)}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Required indicators missing: {', '.join(missing)}"); return None
        
        squeeze_signal = self._check_squeeze_front(current_price, indicators)
        if squeeze_signal: return squeeze_signal
        
        adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
        max_pct_ranging = self.config.get('max_adx_percentile_for_ranging', 45.0)
        min_pct_trending = self.config.get('min_adx_percentile_for_trending', 70.0)
        
        market_regime = "RANGING" if adx_percentile <= max_pct_ranging else "TRENDING" if adx_percentile >= min_pct_trending else "UNCERTAIN"
        self._log_criteria("Path Check: Market Regime (Adaptive)", market_regime != "UNCERTAIN", f"ADX Percentile={adx_percentile:.2f}% -> Regime: {market_regime}")
        
        if market_regime == "RANGING":
            return self._check_ranging_front(current_price, indicators)
        elif market_regime == "TRENDING":
            return self._check_trending_front(current_price, indicators)
        
        self._log_final_decision("HOLD", f"Market regime is '{market_regime}', no actionable setup found."); return None

    def _check_squeeze_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config; is_squeeze = self._safe_get(indicators, ['bollinger', 'analysis', 'is_squeeze_release'], False)
        self._log_criteria("Path Check: Squeeze", is_squeeze, f"Squeeze Release detected: {is_squeeze}")
        if not is_squeeze: return None
        
        score, weights, min_score = 0, cfg.get('weights_squeeze',{}), cfg.get('min_squeeze_score', 6)
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], {})
        trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], '').lower()
        temp_direction = "BUY" if "bullish" in trade_signal else "SELL" if "bearish" in trade_signal else None
        if not temp_direction: self._log_final_decision("HOLD", "Squeeze release detected but direction unclear."); return None

        score += weights.get('bollinger_breakout', {}).get(self._safe_get(bollinger_analysis, ['strength'], '').lower(), 0)
        
        rsi_analysis = self._safe_get(indicators, ['rsi', 'analysis'], {})
        crossover_signal = rsi_analysis.get('crossover_signal')
        if (temp_direction == "BUY" and crossover_signal == "Bullish Crossover") or (temp_direction == "SELL" and crossover_signal == "Bearish Crossover"):
            score += weights.get('momentum_confirmation', 0)

        if self._safe_get(indicators, ['volume', 'analysis', 'is_climactic_volume'], False):
            score += weights.get('volume_spike_confirmation', 0)
            
        if self._get_trend_confirmation(temp_direction): score += weights.get('htf_alignment', 0)
        
        macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
        hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
        if (temp_direction == "BUY" and hist_state == "Green") or (temp_direction == "SELL" and hist_state == "Red"):
            score += weights.get('macd_aligned', 0)

        if score >= min_score:
            risk_params = self._orchestrate_static_risk(temp_direction, current_price)
            if risk_params:
                self._log_final_decision(temp_direction, f"Squeeze Breakout triggered (Score: {score})")
                risk_params["confirmations"] = {"final_score": score, "trade_mode": "Squeeze Breakout"}
                return { "direction": temp_direction, "entry_price": current_price, **risk_params }
                
        self._log_final_decision("HOLD", f"Squeeze conditions not met (Score: {score} < {min_score})."); return None

    def _check_ranging_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config
        lower_band, upper_band, atr_value = (self._safe_get(indicators, ['bollinger', 'values', 'lower_band']), self._safe_get(indicators, ['bollinger', 'values', 'upper_band']), self._safe_get(indicators, ['atr', 'values', 'atr']))
        
        if not all(self._is_valid_number(v) for v in [lower_band, upper_band, atr_value]):
             self._log_final_decision("HOLD", "Missing values for Ranging check."); return None
        
        proximity = atr_value * cfg.get('ranging_trigger_proximity_atr_mult', 0.75)
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = "BUY" if price_low <= (lower_band + proximity) else "SELL" if price_high >= (upper_band - proximity) else None
        
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg.get('weights_ranging',{}), cfg.get('min_ranging_score', 7)
            
            rsi_val, rsi_analysis = self._safe_get(indicators, ['rsi', 'values', 'rsi']), self._safe_get(indicators, ['rsi', 'analysis'], {})
            crossover_signal = rsi_analysis.get('crossover_signal')
            oversold_thresh, overbought_thresh = cfg.get('ranging_rsi_oversold', 35.0), cfg.get('ranging_rsi_overbought', 65.0)
            if self._is_valid_number(rsi_val):
                if (temp_direction == "BUY" and crossover_signal == "Bullish Crossover" and rsi_val <= oversold_thresh) or \
                   (temp_direction == "SELL" and crossover_signal == "Bearish Crossover" and rsi_val >= overbought_thresh):
                    score += weights.get('rsi_reversal', 4)

            div_analysis = self._safe_get(indicators, ['ranging_divergence', 'analysis'], {})
            if (temp_direction == "BUY" and div_analysis.get('has_regular_bullish_divergence')) or (temp_direction == "SELL" and div_analysis.get('has_regular_bearish_divergence')):
                score += weights.get('divergence_confirmation', 0)

            if self._safe_get(indicators, ['volume', 'analysis', 'is_below_average'], False):
                score += weights.get('volume_fade', 0)
                
            candle_info = self._get_candlestick_confirmation(temp_direction, min_reliability='Medium')
            if candle_info: score += weights.get('candlestick', {}).get(self._safe_get(candle_info, ['reliability'], 'weak').lower(), 0)
            
            macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
            hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
            if (temp_direction == "BUY" and hist_state == "White_Up") or (temp_direction == "SELL" and hist_state == "White_Down"):
                score += weights.get('macd_aligned', 0)

            if score >= min_score:
                risk_params = self._orchestrate_static_risk(temp_direction, current_price)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Mean Reversion triggered (Score: {score})")
                    risk_params["confirmations"] = {"final_score": score, "trade_mode": "Mean Reversion"}
                    return { "direction": temp_direction, "entry_price": current_price, **risk_params }
                    
        self._log_final_decision("HOLD", "Ranging conditions not fully met."); return None

    def _check_trending_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        cfg = self.config; middle_band = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = None
        if middle_band:
            if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: temp_direction = "BUY"
            elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: temp_direction = "SELL"
        
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg.get('weights_trending',{}), cfg.get('min_trending_score', 10)
            score += weights.get('htf_alignment', 0)
            
            rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
            rsi_zones = cfg.get('trending_rsi_zones', {})
            if rsi_val and ((temp_direction == "BUY" and rsi_zones.get('buy_min', 45) < rsi_val < rsi_zones.get('buy_max', 65)) or \
               (temp_direction == "SELL" and rsi_zones.get('sell_min', 35) < rsi_val < rsi_zones.get('sell_max', 55))):
                score += weights.get('rsi_cooldown', 0)

            adx_series = self._safe_get(indicators, ['adx', 'series'], [])
            if len(adx_series) >= 3 and adx_series[-1] > adx_series[-3]:
                score += weights.get('adx_acceleration_confirmation', 0)
                
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            if adx_percentile >= cfg.get('min_adx_percentile_for_trending', 70.0):
                score += weights.get('adx_strength', 0)
            
            macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
            hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
            if (temp_direction == "BUY" and hist_state == "Green") or (temp_direction == "SELL" and hist_state == "Red"):
                score += weights.get('macd_aligned', 0)

            if score >= min_score:
                risk_params = self._orchestrate_static_risk(temp_direction, current_price)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Pullback triggered (Score: {score})")
                    risk_params["confirmations"] = {"final_score": score, "trade_mode": "Pullback"}
                    return { "direction": temp_direction, "entry_price": current_price, **risk_params }

        self._log_final_decision("HOLD", "Trending conditions not fully met."); return None

