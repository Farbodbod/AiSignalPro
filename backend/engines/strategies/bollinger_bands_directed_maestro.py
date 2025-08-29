# backend/engines/strategies/bollinger_bands_directed_maestro.py (v3.3.1 - Naming Fix)

import logging
from typing import Dict, Any, Optional, ClassVar
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v3.3.1 - Naming Fix)
    --------------------------------------------------------------------------------
    This patch fixes a critical bug where the strategy_name was not being correctly
    overridden due to a syntax error, causing signals to be logged with the
    source 'BaseStrategy'. All other logic remains identical to v3.3.
    """
    # ✅ CRITICAL FIX: Correctly assigned the class variable to override the base name.
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True,
      "direction": 0,
      
      "sl_atr_multiplier": 2.0,
      "min_sl_percentage": 0.5,
      "max_sl_percentage": 10.0,

      "adx_trend_threshold": 23.0,

      "min_squeeze_score": 4,
      "weights_squeeze": {"breakout_strength": 3, "momentum_confirmation": 2, "htf_alignment": 1},
      
      "min_ranging_score": 4,
      "weights_ranging": {"rsi_reversal": 3, "volume_fade": 2, "candlestick": 1},
      
      "min_trending_score": 4,
      "weights_trending": {"htf_alignment": 3, "rsi_cooldown": 2, "adx_strength": 1},
      
      "htf_confirmation_enabled": True,
      "htf_map": {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d"},
      
      "htf_confirmations": {
          "min_required_score": 1,
          "adx": {
              "weight": 1,
              "min_strength": 20
          },
          "supertrend": {
              "weight": 1
          }
      }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'whales', 'atr']
        indicators = {name: self.get_indicator(name) for name in required}
        if any(data is None for data in indicators.values()): return None

        current_price = self.price_data.get('close')
        bollinger_analysis = indicators['bollinger'].get('analysis', {})
        
        if current_price is None or not bollinger_analysis: return None

        is_squeeze_release = bollinger_analysis.get('is_squeeze_release', False)
        is_in_squeeze = bollinger_analysis.get('is_in_squeeze', False)

        if is_squeeze_release:
            return self._evaluate_breakout_signal(indicators, current_price)

        if is_in_squeeze:
            self._log_final_decision("HOLD", "Squeeze Active. Strategic patience engaged.")
            return None

        market_regime, adx_value = self._get_market_regime(cfg.get('adx_trend_threshold', 23.0))
        if market_regime == "TRENDING":
            return self._evaluate_trending_signal(indicators, current_price, adx_value)
        elif market_regime == "RANGING":
            return self._evaluate_ranging_signal(indicators, current_price)

        return None
        
    def _evaluate_breakout_signal(self, indicators: Dict, price: float) -> Optional[Dict[str, Any]]:
        bb_analysis = indicators['bollinger'].get('analysis', {})
        direction = "BUY" if "Bullish" in bb_analysis.get('trade_signal', '') else "SELL"
        
        score, contributors = 0, []
        weights = self.config.get('weights_squeeze', {})
        
        if bb_analysis.get('strength') == 'Strong':
            score += weights.get('breakout_strength', 0)
            contributors.append("Breakout_Strength")

        rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
        if (direction == "BUY" and rsi_value > 50) or (direction == "SELL" and rsi_value < 50):
            score += weights.get('momentum_confirmation', 0)
            contributors.append("Momentum_Confirm")

        if self._get_trend_confirmation(direction):
            score += weights.get('htf_alignment', 0)
            contributors.append("HTF_Alignment")

        min_score = self.config.get('min_squeeze_score', 4)
        if score < min_score:
            self._log_final_decision("HOLD", f"Breakout score {score} is below required {min_score}.")
            return None
        
        return self._build_final_signal(
            direction=direction, entry_price=price, indicators=indicators,
            engine="Breakout", final_score=score, contributors=contributors
        )

    def _evaluate_trending_signal(self, indicators: Dict, price: float, adx_value: float) -> Optional[Dict[str, Any]]:
        middle_band = indicators['bollinger'].get('values', {}).get('middle_band')
        if middle_band is None: return None
        
        direction = "BUY" if price <= middle_band else "SELL"
        if (self.config.get('direction', 0) == 1 and direction == "SELL") or \
           (self.config.get('direction', 0) == -1 and direction == "BUY"):
            return None

        score, contributors = 0, []
        weights = self.config.get('weights_trending', {})

        if self._get_trend_confirmation(direction):
            score += weights.get('htf_alignment', 0)
            contributors.append("HTF_Alignment")

        rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
        if (direction == "BUY" and rsi_value < 50) or (direction == "SELL" and rsi_value > 50):
            score += weights.get('rsi_cooldown', 0)
            contributors.append("RSI_Cooldown")
            
        if adx_value > self.config.get('adx_trend_threshold', 23.0):
            score += weights.get('adx_strength', 0)
            contributors.append("ADX_Strength")
            
        min_score = self.config.get('min_trending_score', 4)
        if score < min_score:
            self._log_final_decision("HOLD", f"Trending score {score} is below required {min_score}.")
            return None

        return self._build_final_signal(
            direction=direction, entry_price=price, indicators=indicators,
            engine="Trend_Pullback", final_score=score, contributors=contributors
        )

    def _evaluate_ranging_signal(self, indicators: Dict, price: float) -> Optional[Dict[str, Any]]:
        bb_values = indicators['bollinger'].get('values', {})
        lower_band, upper_band = bb_values.get('lower_band'), bb_values.get('upper_band')
        if lower_band is None or upper_band is None: return None
        
        direction = "BUY" if price <= lower_band else "SELL" if price >= upper_band else None
        if direction is None: return None

        if (self.config.get('direction', 0) == 1 and direction == "SELL") or \
           (self.config.get('direction', 0) == -1 and direction == "BUY"):
            return None

        score, contributors = 0, []
        weights = self.config.get('weights_ranging', {})

        rsi_value = indicators['rsi'].get('values', {}).get('rsi', 50)
        if (direction == "BUY" and rsi_value < 30) or (direction == "SELL" and rsi_value > 70):
            score += weights.get('rsi_reversal', 0)
            contributors.append("RSI_Reversal")

        if not (indicators['whales'].get('analysis', {}).get('is_whale_activity', False)):
            score += weights.get('volume_fade', 0)
            contributors.append("Volume_Fade")

        if self._get_candlestick_confirmation(direction):
            score += weights.get('candlestick', 0)
            contributors.append("Candlestick")

        min_score = self.config.get('min_ranging_score', 4)
        if score < min_score:
            self._log_final_decision("HOLD", f"Ranging score {score} is below required {min_score}.")
            return None

        return self._build_final_signal(
            direction=direction, entry_price=price, indicators=indicators,
            engine="Mean_Reversion", final_score=score, contributors=contributors
        )

    def _build_final_signal(self, direction: str, entry_price: float, indicators: Dict, engine: str, final_score: int, contributors: list) -> Optional[Dict[str, Any]]:
        bb_values = indicators['bollinger'].get('values', {})
        atr_value = indicators['atr'].get('values', {}).get('atr')

        if atr_value is None:
            self._log_final_decision("HOLD", "ATR value is missing, cannot build final signal.")
            return None
            
        sl_buffer = atr_value * self.config.get('sl_atr_multiplier', 2.0)

        sl_base = None
        if engine == "Breakout" or engine == "Trend_Pullback":
            sl_base = bb_values.get('middle_band')
        elif engine == "Mean_Reversion":
            sl_base = bb_values.get('lower_band') if direction == "BUY" else bb_values.get('upper_band')

        if sl_base is None:
            self._log_final_decision("HOLD", f"Could not determine SL base for {engine} engine.")
            return None

        stop_loss = sl_base - sl_buffer if direction == "BUY" else sl_base + sl_buffer
        
        if (direction == "BUY" and stop_loss >= entry_price) or \
           (direction == "SELL" and stop_loss <= entry_price):
            logger.error(f"FATAL LOGIC ERROR: Invalid SL calculated for {direction} signal. SL: {stop_loss}, Entry: {entry_price}. Aborting.")
            return None

        min_sl_dist = entry_price * (self.config.get('min_sl_percentage', 0.5) / 100)
        max_sl_dist = entry_price * (self.config.get('max_sl_percentage', 10.0) / 100)
        current_sl_dist = abs(entry_price - stop_loss)
        
        if current_sl_dist < min_sl_dist:
            stop_loss = entry_price - min_sl_dist if direction == "BUY" else entry_price + min_sl_dist
        
        if current_sl_dist > max_sl_dist:
            self._log_final_decision("HOLD", f"Calculated SL distance exceeds max {self.config.get('max_sl_percentage')}% threshold.")
            return None

        risk_params = self._calculate_smart_risk_management(
            entry_price=entry_price, direction=direction, stop_loss=stop_loss
        )
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk parameter calculation failed.")
            return None

        self._log_final_decision(direction, f"Signal confirmed via {engine} engine with score {final_score}.")

        return {
            "direction": direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": {
                "engine": engine,
                "final_score": final_score,
                "contributors": contributors
            }
        }
