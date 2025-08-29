# backend/engines/strategies/bollinger_bands_directed_maestro.py (v2.1 - Glass Box Logging)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v2.1 - Glass Box Logging)
    -------------------------------------------------------------------------
    This version implements a crucial "Glass Box" architectural upgrade. The
    decision-making logic within `check_signal` has been fully refactored to
    provide step-by-step, transparent logging for every single criterion.
    This eliminates ambiguous 'HOLD' reasons and provides a complete narrative
    of the strategy's thought process, from the initial trigger check to the
    final score calculation, enabling precise calibration and debugging.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True,
      "direction": 0,
      "adx_trend_threshold": 23.0,
      
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
      "htf_confirmations": { "min_required_score": 1, "adx": {"weight": 1}, "supertrend": {"weight": 1}}
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data:
            self._log_final_decision("HOLD", "No price data available.")
            return None

        # --- 1. Data Availability ---
        required = ['bollinger', 'rsi', 'adx', 'patterns', 'whales']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}")
            return None
        self._log_criteria("Data Availability", True, "All required indicators are valid.")

        # --- 2. Hierarchical Logic ---
        bollinger_analysis = indicators['bollinger'].get('analysis', {})
        is_squeeze_release = bollinger_analysis.get('is_squeeze_release', False)
        
        # --- PATH 1: SQUEEZE RELEASE (BREAKOUT) LOGIC ---
        self._log_criteria("Path 1: Squeeze Release Check", is_squeeze_release, "Squeeze Release detected. Activating Breakout Hunter." if is_squeeze_release else "No Squeeze Release. Proceeding to standard analysis.")
        if is_squeeze_release:
            score, confirmations = 0, {}
            weights = cfg.get('weights_squeeze', {})
            min_score = cfg.get('min_squeeze_score', 4)
            
            bb_trade_signal = bollinger_analysis.get('trade_signal', '')
            signal_direction = "BUY" if "Bullish" in bb_trade_signal else "SELL" if "Bearish" in bb_trade_signal else None

            if not signal_direction:
                self._log_final_decision("HOLD", "Squeeze Release detected but direction is unclear.")
                return None

            # Scoring for Squeeze Release
            strength_ok = bollinger_analysis.get('strength') == 'Strong'
            self._log_criteria("Score Check: Breakout Strength", strength_ok, f"Volume confirmed strength." if strength_ok else "Weak volume on breakout.")
            if strength_ok: score += weights.get('breakout_strength', 0)

            rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
            momentum_ok = (signal_direction == "BUY" and rsi_value > 50) or (signal_direction == "SELL" and rsi_value < 50)
            self._log_criteria("Score Check: Momentum Confirm", momentum_ok, f"RSI {rsi_value:.2f} confirms direction." if momentum_ok else f"RSI {rsi_value:.2f} does not confirm direction.")
            if momentum_ok: score += weights.get('momentum_confirmation', 0)

            htf_ok = self._get_trend_confirmation(signal_direction)
            self._log_criteria("Score Check: HTF Alignment", htf_ok, "Aligned with HTF." if htf_ok else "Not aligned with HTF.")
            if htf_ok: score += weights.get('htf_alignment', 0)

            # Final check for this path
            if score >= min_score:
                stop_loss = indicators['bollinger'].get('values', {}).get('middle_band')
                confirmations = {"mode": "Squeeze Breakout", "final_score": score}
                # Fall through to final risk management section
            else:
                self._log_final_decision("HOLD", f"Squeeze Release score {score} is below required {min_score}.")
                return None
        
        # --- PATH 2: STANDARD REGIME (RANGING/TRENDING) LOGIC ---
        else:
            market_regime, adx_value = self._get_market_regime(cfg.get('adx_trend_threshold', 23.0))
            self._log_criteria("Path 2: Market Regime", True, f"Detected '{market_regime}' (ADX: {adx_value:.2f})")
            
            bb_values = indicators['bollinger'].get('values', {})
            lower_band, upper_band = bb_values.get('bb_lower'), bb_values.get('bb_upper')
            current_price = self.price_data.get('close')

            long_trigger = current_price < lower_band
            short_trigger = current_price > upper_band

            self._log_criteria("Primary Trigger (Long)", long_trigger, f"Price {current_price:.4f} vs Lower Band {lower_band:.4f}")
            self._log_criteria("Primary Trigger (Short)", short_trigger, f"Price {current_price:.4f} vs Upper Band {upper_band:.4f}")

            if not (long_trigger or short_trigger):
                self._log_final_decision("HOLD", "Price is not touching the bands.")
                return None

            signal_direction = "BUY" if long_trigger else "SELL"
            score, confirmations, stop_loss = 0, {}, None
            
            if market_regime == "RANGING":
                weights = cfg.get('weights_ranging', {})
                min_score = cfg.get('min_ranging_score', 4)
                rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                
                # Scoring for Ranging
                if signal_direction == "BUY" and cfg.get('direction', 0) in [0, 1]:
                    rsi_ok = rsi_value < 30
                    self._log_criteria("Score Check: RSI Reversal", rsi_ok, f"RSI is oversold ({rsi_value:.2f})." if rsi_ok else f"RSI not oversold ({rsi_value:.2f}).")
                    if rsi_ok: score += weights.get('rsi_reversal', 0)

                    volume_ok = not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False))
                    self._log_criteria("Score Check: Volume Fade", volume_ok, "Volume is low (fading)." if volume_ok else "High volume detected.")
                    if volume_ok: score += weights.get('volume_fade', 0)
                    
                    candle_ok = self._get_candlestick_confirmation("BUY") is not None
                    self._log_criteria("Score Check: Candlestick", candle_ok, "Reversal candle found." if candle_ok else "No reversal candle.")
                    if candle_ok: score += weights.get('candlestick', 0)

                    if score < min_score: self._log_final_decision("HOLD", f"Ranging score {score} is below required {min_score}."); return None
                    stop_loss, confirmations = lower_band, {"mode": "Mean Reversion", "final_score": score}

                elif signal_direction == "SELL" and cfg.get('direction', 0) in [0, -1]:
                    rsi_ok = rsi_value > 70
                    self._log_criteria("Score Check: RSI Reversal", rsi_ok, f"RSI is overbought ({rsi_value:.2f})." if rsi_ok else f"RSI not overbought ({rsi_value:.2f}).")
                    if rsi_ok: score += weights.get('rsi_reversal', 0)

                    volume_ok = not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False))
                    self._log_criteria("Score Check: Volume Fade", volume_ok, "Volume is low (fading)." if volume_ok else "High volume detected.")
                    if volume_ok: score += weights.get('volume_fade', 0)

                    candle_ok = self._get_candlestick_confirmation("SELL") is not None
                    self._log_criteria("Score Check: Candlestick", candle_ok, "Reversal candle found." if candle_ok else "No reversal candle.")
                    if candle_ok: score += weights.get('candlestick', 0)

                    if score < min_score: self._log_final_decision("HOLD", f"Ranging score {score} is below required {min_score}."); return None
                    stop_loss, confirmations = upper_band, {"mode": "Mean Reversion", "final_score": score}

            elif market_regime == "TRENDING":
                weights = cfg.get('weights_trending', {})
                min_score = cfg.get('min_trending_score', 4)
                rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)

                # Scoring for Trending
                if signal_direction == "BUY" and cfg.get('direction', 0) in [0, 1]:
                    htf_ok = self._get_trend_confirmation("BUY")
                    self._log_criteria("Score Check: HTF Alignment", htf_ok, "Aligned with HTF." if htf_ok else "Counter to HTF trend.")
                    if not htf_ok: self._log_final_decision("HOLD", "Pullback signal is counter-trend."); return None
                    score += weights.get('htf_alignment', 0)
                    
                    rsi_ok = rsi_value < 50
                    self._log_criteria("Score Check: RSI Cooldown", rsi_ok, f"RSI is cooled down ({rsi_value:.2f})." if rsi_ok else "RSI is still hot.")
                    if rsi_ok: score += weights.get('rsi_cooldown', 0)

                    adx_ok = adx_value > cfg.get('adx_trend_threshold', 23.0)
                    self._log_criteria("Score Check: ADX Strength", adx_ok, "Trend is strong." if adx_ok else "Trend is not strong enough.")
                    if adx_ok: score += weights.get('adx_strength', 0)
                    
                    if score < min_score: self._log_final_decision("HOLD", f"Trending score {score} is below required {min_score}."); return None
                    stop_loss, confirmations = lower_band, {"mode": "Pullback", "final_score": score}

                elif signal_direction == "SELL" and cfg.get('direction', 0) in [0, -1]:
                    htf_ok = self._get_trend_confirmation("SELL")
                    self._log_criteria("Score Check: HTF Alignment", htf_ok, "Aligned with HTF." if htf_ok else "Counter to HTF trend.")
                    if not htf_ok: self._log_final_decision("HOLD", "Pullback signal is counter-trend."); return None
                    score += weights.get('htf_alignment', 0)

                    rsi_ok = rsi_value > 50
                    self._log_criteria("Score Check: RSI Cooldown", rsi_ok, f"RSI is cooled down ({rsi_value:.2f})." if rsi_ok else "RSI is still hot.")
                    if rsi_ok: score += weights.get('rsi_cooldown', 0)

                    adx_ok = adx_value > cfg.get('adx_trend_threshold', 23.0)
                    self._log_criteria("Score Check: ADX Strength", adx_ok, "Trend is strong." if adx_ok else "Trend is not strong enough.")
                    if adx_ok: score += weights.get('adx_strength', 0)

                    if score < min_score: self._log_final_decision("HOLD", f"Trending score {score} is below required {min_score}."); return None
                    stop_loss, confirmations = upper_band, {"mode": "Pullback", "final_score": score}

        # --- 3. Final Validation & Risk Management ---
        if not signal_direction:
            self._log_final_decision("HOLD", "No valid trade path was confirmed after analysis.")
            return None
            
        current_price = self.price_data.get('close')
        risk_params = self._calculate_smart_risk_management(entry_price=current_price, direction=signal_direction, stop_loss=stop_loss)

        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None

        self._log_final_decision(signal_direction, f"Adaptive signal confirmed in '{confirmations.get('mode')}' mode.")
        
        return {
            "direction": signal_direction,
            "entry_price": current_price,
            **risk_params,
            "confirmations": confirmations
        }
