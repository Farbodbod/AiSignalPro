# backend/engines/strategies/BollingerBandsDirectedMaestro.py (v16.6 - The Signal Intelligence Edition)

import logging
from typing import Dict, Any, Optional, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v16.6 - The Signal Intelligence Edition)
    -------------------------------------------------------------------------
    This definitive version reintroduces and upgrades the detailed 'confirmations'
    dictionary in the final signal output, aligning it with the project's gold
    standard (e.g., IchimokuHybridPro). Each generated signal now includes a rich,
    transparent breakdown of all the criteria that were met, including indicator
    values and risk engine details. This completes the strategy's evolution into
    a fully intelligent, transparent, and production-ready system.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    # ... [default_config remains identical to v16.5] ...
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0,
      "ranging_trigger_proximity_atr_mult": 0.75,
      "indicator_configs": {
        "ranging_divergence": { "name": "divergence", "dependencies": { "zigzag": { "deviation": 1.0 } } }
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

    # The _check_and_score helper is removed to allow for dynamic confirmation list building.

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # ... [Unchanged and correct] ...
        if not self.price_data:
            self._log_final_decision("HOLD", "Price data is not available for this candle."); return None
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
        self._log_criteria("Path Check: Market Regime", market_regime != "UNCERTAIN", f"ADX Percentile={adx_percentile:.2f}% -> Regime: {market_regime}")
        
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
        confirmation_details = [] # ✅ UPGRADE: List to hold confirmation details.
        
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], {})
        trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], '').lower()
        temp_direction = "BUY" if "bullish" in trade_signal else "SELL" if "bearish" in trade_signal else None
        if not temp_direction: self._log_final_decision("HOLD", "Squeeze release detected but direction unclear."); return None

        bb_strength = bollinger_analysis.get('strength', 'N/A').lower()
        bb_points = weights.get('bollinger_breakout', {}).get(bb_strength, 0)
        score += bb_points
        confirmation_details.append(f"Bollinger Breakout (Strength: {bb_strength.capitalize()})")
        self._log_criteria("Score: Bollinger Breakout", True, f"Strength: {bb_strength.capitalize()}")

        rsi_analysis = self._safe_get(indicators, ['rsi', 'analysis'], {})
        crossover_signal = rsi_analysis.get('crossover_signal')
        rsi_cond = (temp_direction == "BUY" and crossover_signal == "Bullish Crossover") or (temp_direction == "SELL" and crossover_signal == "Bearish Crossover")
        self._log_criteria("Score: RSI Crossover", rsi_cond, f"Signal: {crossover_signal}")
        if rsi_cond:
            score += weights.get('momentum_confirmation', 0)
            confirmation_details.append(f"RSI Confirmed ({crossover_signal})")

        volume_cond = self._safe_get(indicators, ['volume', 'analysis', 'is_climactic_volume'], False)
        self._log_criteria("Score: Volume Spike", volume_cond, f"Climactic: {volume_cond}")
        if volume_cond:
            score += weights.get('volume_spike_confirmation', 0)
            confirmation_details.append("Volume Spike Confirmed")

        htf_cond = self._get_trend_confirmation(temp_direction)
        self._log_criteria("Score: HTF Alignment", htf_cond, f"Aligned: {htf_cond}")
        if htf_cond:
            score += weights.get('htf_alignment', 0)
            confirmation_details.append("HTF Trend Aligned")

        macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
        hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
        macd_cond = (temp_direction == "BUY" and hist_state == "Green") or (temp_direction == "SELL" and hist_state == "Red")
        self._log_criteria("Score: MACD Acceleration", macd_cond, f"State: {hist_state}")
        if macd_cond:
            score += weights.get('macd_aligned', 0)
            confirmation_details.append(f"MACD Acceleration ({hist_state})")

        if score >= min_score:
            risk_params = self._orchestrate_static_risk(temp_direction, current_price)
            if risk_params:
                self._log_final_decision(temp_direction, f"Squeeze Breakout triggered (Score: {score})")
                
                # ✅ UPGRADE: Build the rich confirmations dictionary.
                confirmations_dict = {
                    "final_score": score,
                    "trade_mode": "Squeeze Breakout",
                    "details": confirmation_details,
                    "risk_engine_source": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
                    "risk_reward_ratio": risk_params.get('risk_reward_ratio')
                }
                return { "direction": temp_direction, "entry_price": current_price, **risk_params, "confirmations": confirmations_dict }
        
        self._log_final_decision("HOLD", f"Squeeze conditions not met (Score: {score} < {min_score})."); return None

    def _check_ranging_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        # ... [Logic is identical, but refactored to build the confirmation list] ...
        cfg = self.config
        lower_band, upper_band, atr_value = (self._safe_get(indicators, ['bollinger', 'values', 'lower_band']), self._safe_get(indicators, ['bollinger', 'values', 'upper_band']), self._safe_get(indicators, ['atr', 'values', 'atr']))
        if not all(self._is_valid_number(v) for v in [lower_band, upper_band, atr_value]):
             self._log_final_decision("HOLD", "Missing values for Ranging check."); return None
        
        proximity = atr_value * cfg.get('ranging_trigger_proximity_atr_mult', 0.75)
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = "BUY" if price_low <= (lower_band + proximity) else "SELL" if price_high >= (upper_band - proximity) else None
        
        self._log_criteria("Path Check: Ranging Trigger", temp_direction is not None, f"Direction: {temp_direction}")
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg.get('weights_ranging',{}), cfg.get('min_ranging_score', 7)
            confirmation_details = []

            rsi_val, rsi_analysis = self._safe_get(indicators, ['rsi', 'values', 'rsi']), self._safe_get(indicators, ['rsi', 'analysis'], {})
            crossover_signal = rsi_analysis.get('crossover_signal')
            oversold_thresh, overbought_thresh = cfg.get('ranging_rsi_oversold', 35.0), cfg.get('ranging_rsi_overbought', 65.0)
            rsi_cond = self._is_valid_number(rsi_val) and ((temp_direction == "BUY" and crossover_signal == "Bullish Crossover" and rsi_val <= oversold_thresh) or \
                       (temp_direction == "SELL" and crossover_signal == "Bearish Crossover" and rsi_val >= overbought_thresh))
            self._log_criteria("Score: RSI Reversal", rsi_cond, f"Signal: {crossover_signal}, Value: {rsi_val:.2f}")
            if rsi_cond:
                score += weights.get('rsi_reversal', 0)
                confirmation_details.append(f"RSI Reversal (Signal: {crossover_signal}, Value: {rsi_val:.2f})")

            div_analysis = self._safe_get(indicators, ['ranging_divergence', 'analysis'], {})
            div_cond = (temp_direction == "BUY" and div_analysis.get('has_regular_bullish_divergence')) or (temp_direction == "SELL" and div_analysis.get('has_regular_bearish_divergence'))
            self._log_criteria("Score: Divergence", div_cond, f"Bull: {div_analysis.get('has_regular_bullish_divergence')}, Bear: {div_analysis.get('has_regular_bearish_divergence')}")
            if div_cond:
                score += weights.get('divergence_confirmation', 0)
                confirmation_details.append("Regular Divergence Confirmed")

            volume_cond = self._safe_get(indicators, ['volume', 'analysis', 'is_below_average'], False)
            self._log_criteria("Score: Volume Fade", volume_cond, f"Below Avg: {volume_cond}")
            if volume_cond:
                score += weights.get('volume_fade', 0)
                confirmation_details.append("Volume Fade Confirmed")
                
            candle_info = self._get_candlestick_confirmation(temp_direction, min_reliability='Medium')
            candle_name = candle_info['name'] if candle_info else 'None'
            self._log_criteria("Score: Candlestick", candle_info is not None, f"Pattern: {candle_name}")
            if candle_info:
                score += weights.get('candlestick', {}).get(candle_info['reliability'].lower(), 0)
                confirmation_details.append(f"Candlestick: {candle_name} ({candle_info['reliability']})")

            macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
            hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
            macd_cond = (temp_direction == "BUY" and hist_state == "White_Up") or (temp_direction == "SELL" and hist_state == "White_Down")
            self._log_criteria("Score: MACD Deceleration", macd_cond, f"State: {hist_state}")
            if macd_cond:
                score += weights.get('macd_aligned', 0)
                confirmation_details.append(f"MACD Deceleration ({hist_state})")

            if score >= min_score:
                risk_params = self._orchestrate_static_risk(temp_direction, current_price)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Mean Reversion triggered (Score: {score})")
                    confirmations_dict = {
                        "final_score": score,
                        "trade_mode": "Mean Reversion",
                        "details": confirmation_details,
                        "risk_engine_source": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
                        "risk_reward_ratio": risk_params.get('risk_reward_ratio')
                    }
                    return { "direction": temp_direction, "entry_price": current_price, **risk_params, "confirmations": confirmations_dict }
            
            self._log_final_decision("HOLD", f"Ranging conditions not met (Score: {score} < {min_score})."); return None
        
        self._log_final_decision("HOLD", "Ranging trigger conditions not met."); return None

    def _check_trending_front(self, current_price: float, indicators: Dict) -> Optional[Dict[str, Any]]:
        # ... [Logic is identical, but refactored to build the confirmation list] ...
        cfg = self.config; middle_band = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        temp_direction = None
        if middle_band:
            if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: temp_direction = "BUY"
            elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: temp_direction = "SELL"
        
        self._log_criteria("Path Check: Trending Trigger", temp_direction is not None, f"Direction: {temp_direction}")
        if temp_direction and cfg.get('direction', 0) in [0, 1 if temp_direction == "BUY" else -1]:
            score, weights, min_score = 0, cfg.get('weights_trending',{}), cfg.get('min_trending_score', 10)
            confirmation_details = []

            score += weights.get('htf_alignment', 0)
            confirmation_details.append("HTF Trend Aligned (by trigger)")
            self._log_criteria("Score: HTF Alignment", True, "Confirmed by trigger")
            
            rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
            rsi_zones = cfg.get('trending_rsi_zones', {})
            rsi_cond = self._is_valid_number(rsi_val) and ((temp_direction == "BUY" and rsi_zones.get('buy_min', 45) < rsi_val < rsi_zones.get('buy_max', 65)) or \
               (temp_direction == "SELL" and rsi_zones.get('sell_min', 35) < rsi_val < rsi_zones.get('sell_max', 55)))
            self._log_criteria("Score: RSI Cooldown", rsi_cond, f"Value: {rsi_val:.2f}")
            if rsi_cond:
                score += weights.get('rsi_cooldown', 0)
                confirmation_details.append(f"RSI in Cooldown Zone ({rsi_val:.2f})")

            adx_series = self._safe_get(indicators, ['adx', 'series'], [])
            adx_accel_cond = len(adx_series) >= 3 and adx_series[-1] > adx_series[-3]
            self._log_criteria("Score: ADX Acceleration", adx_accel_cond, f"Series: ...{adx_series[-3:]}")
            if adx_accel_cond:
                score += weights.get('adx_acceleration_confirmation', 0)
                confirmation_details.append("ADX is Accelerating")
                
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            adx_strength_cond = adx_percentile >= cfg.get('min_adx_percentile_for_trending', 70.0)
            self._log_criteria("Score: ADX Strength", adx_strength_cond, f"Percentile: {adx_percentile:.2f}%")
            if adx_strength_cond:
                score += weights.get('adx_strength', 0)
                confirmation_details.append(f"ADX Strength Confirmed ({adx_percentile:.2f}%)")

            macd_analysis = self._safe_get(indicators, ['macd', 'analysis'], {})
            hist_state = self._safe_get(macd_analysis, ['context', 'histogram_state'])
            macd_cond = (temp_direction == "BUY" and hist_state == "Green") or (temp_direction == "SELL" and hist_state == "Red")
            self._log_criteria("Score: MACD Acceleration", macd_cond, f"State: {hist_state}")
            if macd_cond:
                score += weights.get('macd_aligned', 0)
                confirmation_details.append(f"MACD Re-Acceleration ({hist_state})")

            if score >= min_score:
                risk_params = self._orchestrate_static_risk(temp_direction, current_price)
                if risk_params:
                    self._log_final_decision(temp_direction, f"Pullback triggered (Score: {score})")
                    confirmations_dict = {
                        "final_score": score,
                        "trade_mode": "Pullback",
                        "details": confirmation_details,
                        "risk_engine_source": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
                        "risk_reward_ratio": risk_params.get('risk_reward_ratio')
                    }
                    return { "direction": temp_direction, "entry_price": current_price, **risk_params, "confirmations": confirmations_dict }

            self._log_final_decision("HOLD", f"Trending conditions not met (Score: {score} < {min_score})."); return None
            
        self._log_final_decision("HOLD", "Trending trigger conditions not met."); return None
