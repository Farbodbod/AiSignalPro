# backend/engines/strategies/bollinger_bands_directed_maestro.py (v9.1 - Diagnostic Logging Edition)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v9.1 - Diagnostic Logging Edition)
    -------------------------------------------------------------------------
    This version builds upon the rock-solid foundation of v9.0 by introducing
    an advanced diagnostic logging system. Instead of generic 'HOLD' messages,
    it now provides specific, context-aware reasons for rejecting potential
    setups (e.g., "Score below threshold", "No valid pullback"). This enhancement
    is critical for sophisticated performance analysis, debugging, and future
    strategy calibration, ensuring complete transparency in the decision-making
    process.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0, "max_adx_for_ranging": 20.0, "min_adx_for_trending": 25.0,
      "sl_atr_buffer_multipliers": {"squeeze": 0.6, "ranging": 1.3, "trending": 0.8},
      "vol_ratio_cap": 0.1,
      "max_sl_multiplier_cap": 2.5,
      "min_squeeze_score": 6, 
      "weights_squeeze": {"breakout_strength": 4, "momentum_confirmation": 3, "htf_alignment": 2},
      "min_ranging_score": 7, 
      "weights_ranging": {
          "rsi_reversal": 4, 
          "volume_fade": 3,
          "candlestick": {"weak": 1, "medium": 2, "strong": 3}
      },
      "min_trending_score": 7, 
      "weights_trending": {"htf_alignment": 5, "rsi_cooldown": 3, "adx_strength": 1},
      "htf_confirmation_enabled": True, 
      "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { 
          "min_required_score": 1, 
          "adx": {"weight": 1, "min_strength": 25}, 
          "supertrend": {"weight": 1}
      },
      "allow_mixed_mode": False
    }

    def _safe_get(self, data: Dict, keys: List[str], default: Any = None) -> Any:
        """A helper function to safely access nested dictionary keys."""
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key)
        return data if data is not None else default

    def _validate_blueprint(self, blueprint: Dict) -> bool:
        """Ensures the generated blueprint conforms to the system's contract."""
        required_keys = {"direction", "entry_price", "trade_mode", "sl_logic", "tp_logic"}
        if not required_keys.issubset(blueprint.keys()):
            logger.error(f"[{self.strategy_name}] Malformed blueprint generated, missing keys. Blueprint: {blueprint}")
            return False
        return True

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        if not self.price_data: 
            return None
        
        current_price = self._safe_get(self.price_data, ['close'])
        
        if not current_price or current_price <= 0:
            logger.error(f"[{self.strategy_name}] Invalid current_price: {current_price}; aborting check.")
            return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr']
        indicators = {name: self.get_indicator(name) for name in required}
        
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if atr_value is None:
            logger.warning(f"[{self.strategy_name}] Critical indicator ATR is missing. Aborting.")
            return None

        vol_ratio = atr_value / current_price
        clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))

        # --- Path 1: Squeeze Breakout (The Breakout Hunter) ---
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], default={})
        if self._safe_get(bollinger_analysis, ['is_squeeze_release']):
            trade_mode = "Squeeze Breakout"
            score, weights, min_score = 0, cfg['weights_squeeze'], cfg['min_squeeze_score']
            trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], default='')
            temp_direction = "BUY" if "Bullish" in trade_signal else "SELL" if "Bearish" in trade_signal else None
            
            if temp_direction:
                if self._safe_get(bollinger_analysis, ['strength']) == 'Strong': 
                    score += weights['breakout_strength']
                
                rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
                if rsi_val and ((temp_direction == "BUY" and rsi_val > 55) or (temp_direction == "SELL" and rsi_val < 45)): 
                    score += weights['momentum_confirmation']
                
                if self._get_trend_confirmation(temp_direction): 
                    score += weights['htf_alignment']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['squeeze']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    
                    blueprint = {
                        "direction": temp_direction, 
                        "entry_price": current_price, 
                        "trade_mode": trade_mode,
                        "confirmations": {"final_score": score},
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "atr_multiple", "multiples": [2.0, 3.5, 5.0]}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        return blueprint
                else:
                    logger.info(f"[{self.strategy_name}] {trade_mode} setup considered but score {score}/{min_score} was below threshold.")
        
        # --- Path 2: Ranging / Trending Analysis ---
        _, adx_value = self._get_market_regime(0)
        market_regime = "RANGING" if adx_value is not None and adx_value <= cfg['max_adx_for_ranging'] else "TRENDING" if adx_value is not None and adx_value >= cfg['min_adx_for_trending'] else "UNCERTAIN"

        if market_regime == "RANGING":
            trade_mode = "Mean Reversion"
            bb_lower = self._safe_get(indicators, ['bollinger', 'values', 'bb_lower'])
            bb_upper = self._safe_get(indicators, ['bollinger', 'values', 'bb_upper'])
            if bb_lower is None or bb_upper is None: return None

            temp_direction = "BUY" if current_price <= bb_lower else "SELL" if current_price >= bb_upper else None
            
            if temp_direction and cfg['direction'] in [0, 1 if temp_direction == "BUY" else -1]:
                score, weights, min_score = 0, cfg['weights_ranging'], cfg['min_ranging_score']
                rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])

                if rsi_val and ((temp_direction == "BUY" and rsi_val < 30) or (temp_direction == "SELL" and rsi_val > 70)): 
                    score += weights['rsi_reversal']
                
                candle_info = self._get_candlestick_confirmation(temp_direction)
                if candle_info: 
                    score += weights['candlestick'].get(self._safe_get(candle_info, ['strength'], default='weak'), 0)

                if self._safe_get(indicators, ['volume', 'analysis', 'is_below_average']): 
                    score += weights['volume_fade']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['ranging']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    
                    blueprint = {
                        "direction": temp_direction, 
                        "entry_price": current_price, 
                        "trade_mode": trade_mode,
                        "confirmations": {"final_score": score},
                        "sl_logic": {"type": "band", "band_name": "bb_lower" if temp_direction == "BUY" else "bb_upper", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "range_targets", "targets": ["middle_band", "opposite_band"]}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        return blueprint
                else:
                    logger.info(f"[{self.strategy_name}] {trade_mode} setup considered but score {score}/{min_score} was below threshold.")

        elif market_regime == "TRENDING":
            trade_mode = "Pullback"
            middle_band = self._safe_get(indicators, ['bollinger', 'values', 'middle_band'])
            price_low = self._safe_get(self.price_data, ['low'])
            price_high = self._safe_get(self.price_data, ['high'])
            temp_direction = None
            
            if middle_band and price_low and price_high:
                if self._get_trend_confirmation("BUY") and price_low <= middle_band and current_price > middle_band: 
                    temp_direction = "BUY"
                elif self._get_trend_confirmation("SELL") and price_high >= middle_band and current_price < middle_band: 
                    temp_direction = "SELL"
            
            if temp_direction:
                score, weights, min_score = 0, cfg['weights_trending'], cfg['min_trending_score']
                score += weights['htf_alignment'] 
                
                rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
                if rsi_val and ((temp_direction == "BUY" and 40 < rsi_val < 70) or (temp_direction == "SELL" and 30 < rsi_val < 60)): 
                    score += weights['rsi_cooldown']
                
                if adx_value and adx_value >= cfg['min_adx_for_trending']: 
                    score += weights['adx_strength']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['trending']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])

                    blueprint = {
                        "direction": temp_direction, 
                        "entry_price": current_price, 
                        "trade_mode": trade_mode,
                        "confirmations": {"final_score": score, "adx_strength": adx_value},
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "fibonacci_extension", "levels": [1.618, 2.618, 4.236]}
                    }
                    if self._validate_blueprint(blueprint):
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score}, ADX: {adx_value:.2f})")
                        return blueprint
                else:
                    logger.info(f"[{self.strategy_name}] {trade_mode} setup considered but score {score}/{min_score} was below threshold.")
            else:
                 logger.info(f"[{self.strategy_name}] {trade_mode} regime detected, but no valid bounce/pullback pattern was found.")

        final_hold_reason = f"No high-conviction setup found in any mode (Regime: {market_regime})."
        if market_regime == "UNCERTAIN":
            final_hold_reason = f"HOLD decision due to 'UNCERTAIN' market regime (ADX: {adx_value:.2f}). Patiently waiting for clarity."
        
        self._log_final_decision("HOLD", final_hold_reason)
        return None
