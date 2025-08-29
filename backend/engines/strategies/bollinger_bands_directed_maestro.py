# backend/engines/strategies/bollinger_bands_directed_maestro.py (v5.0 - Definitive Edition)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v5.0 - Definitive Edition)
    -------------------------------------------------------------------------
    This is the definitive, world-class version of the adaptive strategy, hardened
    by a meticulous triple-check audit protocol. It incorporates all final
    architectural mandates and fixes the critical pullback trigger logic that
    caused inverted stop-losses. The trigger now requires a confirmation close
    across the middle band, ensuring maximum robustness. This version is the
    culmination of all strategic refinements and is production-ready.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True,
      "direction": 0,
      
      "max_adx_for_ranging": 20.0,
      "min_adx_for_trending": 25.0,
      
      "sl_atr_buffer_multipliers": {
        "squeeze": 0.5,
        "ranging": 1.2,
        "trending": 0.75
      },
      
      "min_squeeze_score": 4,
      "weights_squeeze": {
        "breakout_strength": 3,
        "momentum_confirmation": 2,
        "htf_alignment": 1
      },
      "min_ranging_score": 4,
      "weights_ranging": {
        "rsi_reversal": 3,
        "volume_fade": 2,
        "candlestick": 1
      },
      "min_trending_score": 4,
      "weights_trending": {
        "htf_alignment": 3,
        "rsi_cooldown": 2,
        "adx_strength": 1
      },
      
      "htf_confirmation_enabled": True,
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { 
          "min_required_score": 1, 
          "adx": {"weight": 1, "min_strength": 25}, 
          "supertrend": {"weight": 1}
      }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available."); return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'whales', 'atr']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        self._log_criteria("Data Availability", True, "All required indicators are valid.")

        bollinger_analysis = indicators['bollinger'].get('analysis', {})
        bollinger_values = indicators['bollinger'].get('values', {})
        is_squeeze_release = bollinger_analysis.get('is_squeeze_release', False)
        
        signal_direction: Optional[str] = None
        confirmations: Dict[str, Any] = {}
        stop_loss: Optional[float] = None
        current_price = self.price_data.get('close')
        atr_value = indicators['atr'].get('values', {}).get('atr')
        sl_multipliers = cfg.get('sl_atr_buffer_multipliers', {})

        if not atr_value:
            self._log_final_decision("HOLD", "ATR value is missing for adaptive SL."); return None

        self._log_criteria("Path 1: Squeeze Release Check", is_squeeze_release, "Squeeze Release detected. Activating Breakout Hunter." if is_squeeze_release else "No Squeeze Release. Proceeding to standard analysis.")
        if is_squeeze_release:
            score, weights, min_score = 0, cfg.get('weights_squeeze', {}), cfg.get('min_squeeze_score', 4)
            bb_trade_signal = bollinger_analysis.get('trade_signal', '')
            signal_direction = "BUY" if "Bullish" in bb_trade_signal else "SELL" if "Bearish" in bb_trade_signal else None

            if not signal_direction: self._log_final_decision("HOLD", "Squeeze direction unclear."); return None

            strength_ok = bollinger_analysis.get('strength') == 'Strong'
            self._log_criteria("Score Check (Squeeze): Breakout Strength", strength_ok, f"Volume confirmed strength." if strength_ok else "Weak volume on breakout.")
            if strength_ok: score += weights.get('breakout_strength', 0)
            
            rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
            momentum_ok = (signal_direction == "BUY" and rsi_value > 50) or (signal_direction == "SELL" and rsi_value < 50)
            self._log_criteria("Score Check (Squeeze): Momentum Confirm", momentum_ok, f"RSI {rsi_value:.2f} confirms direction." if momentum_ok else f"RSI {rsi_value:.2f} does not confirm direction.")
            if momentum_ok: score += weights.get('momentum_confirmation', 0)
            
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
            self._log_criteria("Score Check (Squeeze): HTF Alignment", htf_ok, "No strong opposing HTF trend." if htf_ok else "Strong opposing HTF trend detected.")
            if htf_ok: score += weights.get('htf_alignment', 0)

            if score >= min_score:
                middle_band = bollinger_values.get('middle_band')
                buffer = atr_value * sl_multipliers.get('squeeze', 0.5)
                stop_loss = middle_band - buffer if signal_direction == "BUY" else middle_band + buffer
                confirmations = {"mode": "Squeeze Breakout", "final_score": score}
            else: self._log_final_decision("HOLD", f"Squeeze Release score {score} is below required {min_score}."); return None
        else:
            _, adx_value = self._get_market_regime(0)
            max_ranging, min_trending = cfg.get('max_adx_for_ranging', 20.0), cfg.get('min_adx_for_trending', 25.0)
            market_regime = "RANGING" if adx_value <= max_ranging else "TRENDING" if adx_value >= min_trending else "UNCERTAIN"
            
            if market_regime == "UNCERTAIN": self._log_final_decision("HOLD", f"ADX {adx_value:.2f} is in Zone of Uncertainty ({max_ranging}-{min_trending})."); return None
            self._log_criteria("Path 2: Market Regime", True, f"Detected '{market_regime}' (ADX: {adx_value:.2f})")
            
            if market_regime == "RANGING":
                lower_band, upper_band = bollinger_values.get('bb_lower'), bollinger_values.get('bb_upper')
                if not all(v is not None for v in [lower_band, upper_band, current_price]): self._log_final_decision("HOLD", "Invalid BB data."); return None
                
                long_trigger = current_price <= lower_band
                short_trigger = current_price >= upper_band
                if not (long_trigger or short_trigger): self._log_final_decision("HOLD", "Price not at outer bands."); return None
                
                temp_direction = "BUY" if long_trigger else "SELL"
                score, weights, min_score = 0, cfg.get('weights_ranging', {}), cfg.get('min_ranging_score', 4)

                if temp_direction == "BUY" and cfg.get('direction', 0) in [0, 1]:
                    opposite_direction = "SELL"
                    htf_ok = not self._get_trend_confirmation(opposite_direction)
                    self._log_criteria("Score Check (Ranging): HTF Alignment", htf_ok, "No strong opposing HTF trend." if htf_ok else "Strong opposing HTF trend detected.")
                    if not htf_ok: self._log_final_decision("HOLD", "Mean Reversion vetoed by strong HTF trend."); return None

                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                    rsi_ok = rsi_value < 30
                    self._log_criteria("Score Check (Ranging): RSI Reversal", rsi_ok, f"RSI is oversold ({rsi_value:.2f})." if rsi_ok else f"RSI not oversold ({rsi_value:.2f}).")
                    if rsi_ok: score += weights.get('rsi_reversal', 0)

                    volume_ok = not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False))
                    self._log_criteria("Score Check (Ranging): Volume Fade", volume_ok, "Volume is low (fading)." if volume_ok else "High volume detected.")
                    if volume_ok: score += weights.get('volume_fade', 0)
                    
                    candle_ok = self._get_candlestick_confirmation("BUY") is not None
                    self._log_criteria("Score Check (Ranging): Candlestick", candle_ok, "Reversal candle found." if candle_ok else "No reversal candle.")
                    if candle_ok: score += weights.get('candlestick', 0)
                    
                    if score >= min_score:
                        signal_direction = "BUY"; buffer = atr_value * sl_multipliers.get('ranging', 1.2)
                        stop_loss, confirmations = lower_band - buffer, {"mode": "Mean Reversion", "final_score": score}
                    else: self._log_final_decision("HOLD", f"Ranging score {score} < {min_score}."); return None
                elif temp_direction == "SELL" and cfg.get('direction', 0) in [0, -1]:
                    opposite_direction = "BUY"
                    htf_ok = not self._get_trend_confirmation(opposite_direction)
                    self._log_criteria("Score Check (Ranging): HTF Alignment", htf_ok, "No strong opposing HTF trend." if htf_ok else "Strong opposing HTF trend detected.")
                    if not htf_ok: self._log_final_decision("HOLD", "Mean Reversion vetoed by strong HTF trend."); return None
                    
                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                    rsi_ok = rsi_value > 70
                    self._log_criteria("Score Check (Ranging): RSI Reversal", rsi_ok, f"RSI is overbought ({rsi_value:.2f})." if rsi_ok else f"RSI not overbought ({rsi_value:.2f}).")
                    if rsi_ok: score += weights.get('rsi_reversal', 0)

                    volume_ok = not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False))
                    self._log_criteria("Score Check (Ranging): Volume Fade", volume_ok, "Volume is low (fading)." if volume_ok else "High volume detected.")
                    if volume_ok: score += weights.get('volume_fade', 0)

                    candle_ok = self._get_candlestick_confirmation("SELL") is not None
                    self._log_criteria("Score Check (Ranging): Candlestick", candle_ok, "Reversal candle found." if candle_ok else "No reversal candle.")
                    if candle_ok: score += weights.get('candlestick', 0)
                    
                    if score >= min_score:
                        signal_direction = "SELL"; buffer = atr_value * sl_multipliers.get('ranging', 1.2)
                        stop_loss, confirmations = upper_band + buffer, {"mode": "Mean Reversion", "final_score": score}
                    else: self._log_final_decision("HOLD", f"Ranging score {score} < {min_score}."); return None

            elif market_regime == "TRENDING":
                middle_band = bollinger_values.get('middle_band')
                price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
                if not all(v is not None for v in [middle_band, price_low, price_high, current_price]): self._log_final_decision("HOLD", "Invalid middle band or price data."); return None
                
                temp_direction = None
                if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band:
                    temp_direction = "BUY"
                elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band:
                    temp_direction = "SELL"
                
                if not temp_direction: self._log_final_decision("HOLD", "No confirmed pullback bounce off the middle band."); return None
                
                score, weights, min_score = 0, cfg.get('weights_trending', {}), cfg.get('min_trending_score', 4)
                
                if temp_direction == "BUY":
                    score += weights.get('htf_alignment', 0)
                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                    rsi_ok = rsi_value < 50
                    self._log_criteria("Score Check (Trending): RSI Cooldown", rsi_ok, f"RSI is cooled down ({rsi_value:.2f})." if rsi_ok else "RSI is still hot.")
                    if rsi_ok: score += weights.get('rsi_cooldown', 0)

                    adx_ok = adx_value >= min_trending
                    self._log_criteria("Score Check (Trending): ADX Strength", adx_ok, "Trend is strong." if adx_ok else "Trend is not strong enough.")
                    if adx_ok: score += weights.get('adx_strength', 0)
                    
                    if score >= min_score:
                        signal_direction = "BUY"; buffer = atr_value * sl_multipliers.get('trending', 0.75)
                        stop_loss, confirmations = middle_band - buffer, {"mode": "Pullback", "final_score": score}
                    else: self._log_final_decision("HOLD", f"Trending score {score} < {min_score}."); return None
                elif temp_direction == "SELL":
                    score += weights.get('htf_alignment', 0)
                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                    rsi_ok = rsi_value > 50
                    self._log_criteria("Score Check (Trending): RSI Cooldown", rsi_ok, f"RSI is cooled down ({rsi_value:.2f})." if rsi_ok else "RSI is still hot.")
                    if rsi_ok: score += weights.get('rsi_cooldown', 0)

                    adx_ok = adx_value >= min_trending
                    self._log_criteria("Score Check (Trending): ADX Strength", adx_ok, "Trend is strong." if adx_ok else "Trend is not strong enough.")
                    if adx_ok: score += weights.get('adx_strength', 0)

                    if score >= min_score:
                        signal_direction = "SELL"; buffer = atr_value * sl_multipliers.get('trending', 0.75)
                        stop_loss, confirmations = middle_band + buffer, {"mode": "Pullback", "final_score": score}
                    else: self._log_final_decision("HOLD", f"Trending score {score} < {min_score}."); return None

        if not signal_direction: self._log_final_decision("HOLD", "No valid trade path confirmed."); return None
            
        risk_params = self._calculate_smart_risk_management(entry_price=current_price, direction=signal_direction, stop_loss=stop_loss)
        if not risk_params or not risk_params.get("targets"): self._log_final_decision("HOLD", "Risk parameter calculation failed."); return None

        self._log_final_decision(signal_direction, f"Adaptive signal confirmed in '{confirmations.get('mode')}' mode.")
        
        return { "direction": signal_direction, "entry_price": current_price, **risk_params, "confirmations": confirmations }
