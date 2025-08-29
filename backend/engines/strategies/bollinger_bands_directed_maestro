# backend/engines/strategies/bollinger_bands_directed_maestro.py (v2.0 - Triple-Threat Specialist)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v2.0 - Triple-Threat Specialist)
    -------------------------------------------------------------------------
    This masterclass version evolves the strategy into a "Triple-Threat Specialist".
    It now possesses a third, prioritized personality: a "Breakout Hunter" that
    activates exclusively on a Bollinger Bands Squeeze Release. If this rare,
    high-probability event is not present, the Maestro seamlessly reverts to its
    standard analysis, deploying its Mean Reversion or Pullback expertise based
    on the market regime. This layered, hierarchical logic makes it exceptionally
    adaptive and comprehensive.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True,
      "direction": 0, # 0: both, 1: long_only, -1: short_only
      "adx_trend_threshold": 23.0,
      
      # --- Squeeze Release (Breakout) Logic ---
      "min_squeeze_score": 4,
      "weights_squeeze": {
        "breakout_strength": 3,
        "momentum_confirmation": 2,
        "htf_alignment": 1
      },
      
      # --- Ranging (Mean Reversion) Logic ---
      "min_ranging_score": 4,
      "weights_ranging": {
        "rsi_reversal": 3,
        "volume_fade": 2,
        "candlestick": 1
      },
      
      # --- Trending (Pullback) Logic ---
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
        
        signal_direction: Optional[str] = None
        score: int = 0
        confirmations: Dict[str, Any] = {}
        stop_loss: Optional[float] = None
        current_price = self.price_data.get('close')

        # --- Path 1: Check for the "Brilliant Move" (Squeeze Release) FIRST ---
        if is_squeeze_release:
            self._log_criteria("Special Event Check", True, "Squeeze Release detected. Activating Breakout Hunter logic.")
            weights = cfg.get('weights_squeeze', {})
            min_score = cfg.get('min_squeeze_score', 4)
            
            bb_trade_signal = bollinger_analysis.get('trade_signal', '')
            temp_direction = "BUY" if "Bullish" in bb_trade_signal else "SELL" if "Bearish" in bb_trade_signal else None

            if temp_direction:
                # Breakout Strength (Volume)
                if bollinger_analysis.get('strength') == 'Strong': score += weights.get('breakout_strength', 0)
                # Momentum Confirmation
                rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                if (temp_direction == "BUY" and rsi_value > 50) or (temp_direction == "SELL" and rsi_value < 50): score += weights.get('momentum_confirmation', 0)
                # HTF Alignment
                if self._get_trend_confirmation(temp_direction): score += weights.get('htf_alignment', 0)

                if score >= min_score:
                    signal_direction = temp_direction
                    confirmations = {"mode": "Squeeze Breakout", "final_score": score}
                    # For breakouts, a dynamic SL like the middle band is effective.
                    stop_loss = indicators['bollinger'].get('values', {}).get('middle_band')
                else:
                    self._log_final_decision("HOLD", f"Squeeze Release score {score} is below required {min_score}.")
                    return None # End analysis for this candle, as the special event was not confirmed.
        
        # --- Path 2: If no Squeeze Release, proceed to standard Ranging/Trending analysis ---
        else:
            self._log_criteria("Special Event Check", False, "No Squeeze Release. Proceeding to standard regime analysis.")
            market_regime, adx_value = self._get_market_regime(cfg.get('adx_trend_threshold', 23.0))
            self._log_criteria("Market Regime", True, f"Detected '{market_regime}' (ADX: {adx_value:.2f})")
            
            bb_values = indicators['bollinger'].get('values', {})
            lower_band, upper_band = bb_values.get('bb_lower'), bb_values.get('bb_upper')
            if not all([lower_band, upper_band, current_price]):
                self._log_final_decision("HOLD", "Invalid Bollinger Band or price data.")
                return None

            long_trigger = (current_price < lower_band)
            short_trigger = (current_price > upper_band)
            
            temp_direction = "BUY" if long_trigger else "SELL" if short_trigger else None

            if temp_direction:
                if market_regime == "RANGING":
                    weights = cfg.get('weights_ranging', {})
                    min_score = cfg.get('min_ranging_score', 4)
                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
                    
                    if temp_direction == "BUY" and cfg.get('direction', 0) in [0, 1]:
                        if rsi_value < 30: score += weights.get('rsi_reversal', 0)
                        if not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False)): score += weights.get('volume_fade', 0)
                        if self._get_candlestick_confirmation("BUY"): score += weights.get('candlestick', 0)
                        if score >= min_score: 
                            signal_direction, stop_loss = "BUY", lower_band
                            confirmations = {"mode": "Mean Reversion", "final_score": score}

                    elif temp_direction == "SELL" and cfg.get('direction', 0) in [0, -1]:
                        if rsi_value > 70: score += weights.get('rsi_reversal', 0)
                        if not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False)): score += weights.get('volume_fade', 0)
                        if self._get_candlestick_confirmation("SELL"): score += weights.get('candlestick', 0)
                        if score >= min_score:
                             signal_direction, stop_loss = "SELL", upper_band
                             confirmations = {"mode": "Mean Reversion", "final_score": score}
                    
                    if signal_direction is None: self._log_final_decision("HOLD", f"Ranging score {score} is below required {min_score}.")

                elif market_regime == "TRENDING":
                    weights = cfg.get('weights_trending', {})
                    min_score = cfg.get('min_trending_score', 4)
                    rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)

                    if temp_direction == "BUY" and cfg.get('direction', 0) in [0, 1]:
                        if self._get_trend_confirmation("BUY"):
                            score += weights.get('htf_alignment', 0)
                            if rsi_value < 50: score += weights.get('rsi_cooldown', 0)
                            if adx_value > cfg.get('adx_trend_threshold', 23.0): score += weights.get('adx_strength', 0)
                            if score >= min_score:
                                signal_direction, stop_loss = "BUY", lower_band
                                confirmations = {"mode": "Pullback", "final_score": score}
                        else: self._log_criteria("HTF Alignment", False, "Signal is counter to HTF trend.")

                    elif temp_direction == "SELL" and cfg.get('direction', 0) in [0, -1]:
                        if self._get_trend_confirmation("SELL"):
                            score += weights.get('htf_alignment', 0)
                            if rsi_value > 50: score += weights.get('rsi_cooldown', 0)
                            if adx_value > cfg.get('adx_trend_threshold', 23.0): score += weights.get('adx_strength', 0)
                            if score >= min_score:
                                signal_direction, stop_loss = "SELL", upper_band
                                confirmations = {"mode": "Pullback", "final_score": score}
                        else: self._log_criteria("HTF Alignment", False, "Signal is counter to HTF trend.")
                    
                    if signal_direction is None and score > 0: self._log_final_decision("HOLD", f"Trending score {score} is below required {min_score}.")

        # --- 5. Final Validation & Risk Management ---
        if not signal_direction:
            return None
            
        self._log_criteria("Final Signal Confirmation", True, f"A valid '{confirmations.get('mode')}' signal was confirmed with score {confirmations.get('final_score')}.")
        
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
