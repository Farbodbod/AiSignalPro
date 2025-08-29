# backend/engines/strategies/bollinger_bands_directed_maestro.py (v10.3 - Final Polish Edition)

import logging
from typing import Dict, Any, Optional, ClassVar, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BollingerBandsDirectedMaestro(BaseStrategy):
    """
    BollingerBandsDirectedMaestro - (v10.3 - Final Polish Edition)
    -------------------------------------------------------------------------
    The definitive, Gold Master version of the strategy, incorporating final
    polishes for maximum robustness and code clarity. This version includes:
    1.  A semantically correct 'is not None' check for ADX values.
    2.  Informative warnings for unrecognized candlestick strength values.
    3.  A robust and consistent logging protocol using '_log_criteria'.
    4.  Pre-extraction of variables for enhanced readability.
    This represents the culmination of our collaborative development and
    rigorous auditing process.
    """
    strategy_name: str = "BollingerBandsDirectedMaestro"
    
    default_config: ClassVar[Dict[str, Any]] = {
      "enabled": True, "direction": 0, "max_adx_for_ranging": 20.0, "min_adx_for_trending": 25.0,
      "sl_atr_buffer_multipliers": {"squeeze": 0.6, "ranging": 1.3, "trending": 0.8},
      "vol_ratio_cap": 0.1, "max_sl_multiplier_cap": 2.5,
      "min_squeeze_score": 6, "weights_squeeze": {"breakout_strength": 4, "momentum_confirmation": 3, "htf_alignment": 2},
      "min_ranging_score": 7, "weights_ranging": {"rsi_reversal": 4, "volume_fade": 3, "candlestick": {"weak": 1, "medium": 2, "strong": 3}},
      "min_trending_score": 7, "weights_trending": {"htf_alignment": 5, "rsi_cooldown": 3, "adx_strength": 1},
      "htf_confirmation_enabled": True, "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
      "htf_confirmations": { "min_required_score": 1, "adx": {"weight": 1, "min_strength": 25}, "supertrend": {"weight": 1}},
      "allow_mixed_mode": False
    }

    def _safe_get(self, data: Dict, keys: List[str], default: Any = None) -> Any:
        for key in keys:
            if not isinstance(data, dict): return default
            data = data.get(key)
        return data if data is not None else default

    def _validate_blueprint(self, blueprint: Dict) -> bool:
        required_keys = {"direction", "entry_price", "trade_mode", "sl_logic", "tp_logic"}
        if not required_keys.issubset(blueprint.keys()):
            logger.error(f"[{self.strategy_name}] Malformed blueprint generated, missing keys.")
            return False
        return True

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: return None
        
        current_price = self._safe_get(self.price_data, ['close'])
        if not current_price or current_price <= 0:
            self._log_final_decision("HOLD", f"Invalid current_price: {current_price}"); return None

        required = ['bollinger', 'rsi', 'adx', 'patterns', 'volume', 'atr']
        indicators = {name: self.get_indicator(name) for name in required}
        
        missing_indicators = [name for name, data in indicators.items() if data is None]
        if missing_indicators:
            self._log_final_decision("HOLD", f"Required indicators are missing: {', '.join(missing_indicators)}"); return None
        
        atr_value = self._safe_get(indicators, ['atr', 'values', 'atr'])
        if atr_value is None: self._log_final_decision("HOLD", "ATR value is missing."); return None
        
        vol_ratio = atr_value / current_price
        clamped_vol_ratio = min(vol_ratio, cfg.get('vol_ratio_cap', 0.1))
        
        bollinger_analysis = self._safe_get(indicators, ['bollinger', 'analysis'], default={})
        bollinger_values = self._safe_get(indicators, ['bollinger', 'values'], default={})
        rsi_val = self._safe_get(indicators, ['rsi', 'values', 'rsi'])
        _, adx_value = self._get_market_regime(0)
        
        is_squeeze = self._safe_get(bollinger_analysis, ['is_squeeze_release'], False)
        self._log_criteria("Path Check: Squeeze", is_squeeze, f"Squeeze Release detected: {is_squeeze}")
        if is_squeeze:
            trade_mode = "Squeeze Breakout"
            score, weights, min_score = 0, cfg['weights_squeeze'], cfg['min_squeeze_score']
            trade_signal = self._safe_get(bollinger_analysis, ['trade_signal'], default='')
            temp_direction = "BUY" if "Bullish" in trade_signal else "SELL" if "Bearish" in trade_signal else None
            
            if temp_direction:
                strength_ok = self._safe_get(bollinger_analysis, ['strength']) == 'Strong'
                self._log_criteria("Squeeze: Breakout Strength", strength_ok, "Breakout confirmed with strong volume.")
                if strength_ok: score += weights['breakout_strength']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and rsi_val > 55) or (temp_direction == "SELL" and rsi_val < 45))
                rsi_display = f"{rsi_val:.2f}" if rsi_val is not None else "N/A"
                self._log_criteria("Squeeze: Momentum Confirmation", rsi_ok, f"RSI={rsi_display} confirms momentum.")
                if rsi_ok: score += weights['momentum_confirmation']
                
                htf_ok = self._get_trend_confirmation(temp_direction)
                self._log_criteria("Squeeze: HTF Alignment", htf_ok, "HTF trend confirms breakout direction.")
                if htf_ok: score += weights['htf_alignment']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['squeeze']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "confirmations": {"final_score": score},
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "atr_multiple", "multiples": [2.0, 3.5, 5.0]}
                    }
                    if self._validate_blueprint(blueprint):
                        risk_params = self._calculate_smart_risk_management(
                            entry_price=current_price,
                            direction=temp_direction,
                            sl_params=blueprint['sl_logic'],
                            tp_logic=blueprint['tp_logic']
                        )
                        if not risk_params or not risk_params.get("risk_reward_ratio", 0) > 0:
                            self._log_final_decision("HOLD", "Risk management failed or R/R is zero.")
                            return None
                        
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        blueprint.update(risk_params)
                        return blueprint
                else:
                    self._log_final_decision("HOLD", f"{trade_mode} score {score}/{min_score} was below threshold.")
                    return None
        
        adx_display = f"{adx_value:.2f}" if adx_value is not None else "N/A"
        market_regime = "RANGING" if adx_value is not None and adx_value <= cfg['max_adx_for_ranging'] else "TRENDING" if adx_value is not None and adx_value >= cfg['min_adx_for_trending'] else "UNCERTAIN"
        self._log_criteria("Path Check: Market Regime", market_regime, f"ADX={adx_display}")

        if market_regime == "RANGING":
            trade_mode = "Mean Reversion"
            bb_lower = self._safe_get(bollinger_values, ['bb_lower'])
            bb_upper = self._safe_get(bollinger_values, ['bb_upper'])
            if bb_lower is None or bb_upper is None: 
                self._log_final_decision("HOLD", "Bollinger Bands values missing for Ranging check."); return None
            
            temp_direction = "BUY" if current_price <= bb_lower else "SELL" if current_price >= bb_upper else None
            trigger_ok = temp_direction is not None
            self._log_criteria("Ranging: Entry Trigger", trigger_ok, "Price is at outer bands.")
            
            if trigger_ok and cfg['direction'] in [0, 1 if temp_direction == "BUY" else -1]:
                score, weights, min_score = 0, cfg['weights_ranging'], cfg['min_ranging_score']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and rsi_val < 30) or (temp_direction == "SELL" and rsi_val > 70))
                rsi_display = f"{rsi_val:.2f}" if rsi_val is not None else "N/A"
                self._log_criteria("Ranging: RSI Reversal", rsi_ok, f"RSI={rsi_display} shows over-extension.")
                if rsi_ok: score += weights['rsi_reversal']
                
                candle_info = self._get_candlestick_confirmation(temp_direction)
                candle_ok = candle_info is not None
                self._log_criteria("Ranging: Candlestick Confirmation", candle_ok, f"Found pattern: {self._safe_get(candle_info, ['name'])}")
                if candle_ok:
                    strength = self._safe_get(candle_info, ['strength'], default='weak')
                    if strength in weights['candlestick']:
                        score += weights['candlestick'][strength]
                    else:
                        logger.warning(f"[{self.strategy_name}] Unrecognized candlestick strength '{strength}' received. Assigning 0 score.")

                volume_ok = self._safe_get(indicators, ['volume', 'analysis', 'is_below_average'], False)
                self._log_criteria("Ranging: Volume Fade", volume_ok, "Volume is below average, confirming exhaustion.")
                if volume_ok: score += weights['volume_fade']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['ranging']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "confirmations": {"final_score": score},
                        "sl_logic": {"type": "band", "band_name": "bb_lower" if temp_direction == "BUY" else "bb_upper", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "range_targets", "targets": ["middle_band", "opposite_band"]}
                    }
                    if self._validate_blueprint(blueprint):
                        risk_params = self._calculate_smart_risk_management(
                            entry_price=current_price,
                            direction=temp_direction,
                            sl_params=blueprint['sl_logic'],
                            tp_logic=blueprint['tp_logic']
                        )
                        if not risk_params or not risk_params.get("risk_reward_ratio", 0) > 0:
                            self._log_final_decision("HOLD", "Risk management failed or R/R is zero.")
                            return None
                        
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        blueprint.update(risk_params)
                        return blueprint
                else:
                    self._log_final_decision("HOLD", f"{trade_mode} score {score}/{min_score} was below threshold.")
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
            
            trigger_ok = temp_direction is not None
            self._log_criteria("Trending: Pullback Trigger", trigger_ok, "Valid bounce off middle band detected.")
            if trigger_ok:
                score, weights, min_score = 0, cfg['weights_trending'], cfg['min_trending_score']
                
                self._log_criteria("Trending: HTF Alignment", True, "HTF trend confirmed (trigger condition).")
                score += weights['htf_alignment']
                
                rsi_ok = rsi_val is not None and ((temp_direction == "BUY" and 40 < rsi_val < 70) or (temp_direction == "SELL" and 30 < rsi_val < 60))
                rsi_display = f"{rsi_val:.2f}" if rsi_val is not None else "N/A"
                self._log_criteria("Trending: RSI Cooldown", rsi_ok, f"RSI={rsi_display} is in healthy pullback zone.")
                if rsi_ok: score += weights['rsi_cooldown']
                
                # POLISH 1: Use semantically correct check for ADX
                adx_ok = adx_value is not None and adx_value >= cfg['min_adx_for_trending']
                self._log_criteria("Trending: ADX Strength", adx_ok, f"ADX={adx_display} confirms strong trend.")
                if adx_ok: score += weights['adx_strength']

                if score >= min_score:
                    base_multiplier = cfg['sl_atr_buffer_multipliers']['trending']
                    dynamic_multiplier = base_multiplier * (1 + clamped_vol_ratio * 5)
                    final_multiplier = min(dynamic_multiplier, cfg['max_sl_multiplier_cap'])
                    blueprint = {
                        "direction": temp_direction, "entry_price": current_price, "trade_mode": trade_mode,
                        "confirmations": {"final_score": score, "adx_strength": adx_value},
                        "sl_logic": {"type": "band", "band_name": "middle_band", "buffer_atr_multiplier": final_multiplier},
                        "tp_logic": {"type": "fibonacci_extension", "levels": [1.618, 2.618, 4.236]}
                    }
                    if self._validate_blueprint(blueprint):
                        risk_params = self._calculate_smart_risk_management(
                            entry_price=current_price,
                            direction=temp_direction,
                            sl_params=blueprint['sl_logic'],
                            tp_logic=blueprint['tp_logic']
                        )
                        if not risk_params or not risk_params.get("risk_reward_ratio", 0) > 0:
                            self._log_final_decision("HOLD", "Risk management failed or R/R is zero.")
                            return None
                        
                        self._log_final_decision(temp_direction, f"{trade_mode} triggered (Score: {score})")
                        blueprint.update(risk_params)
                        return blueprint
                else:
                    self._log_final_decision("HOLD", f"{trade_mode} score {score}/{min_score} was below threshold.")
                    return None
        
        self._log_final_decision("HOLD", f"Market regime is '{market_regime}', no actionable setup found.")
        return None
