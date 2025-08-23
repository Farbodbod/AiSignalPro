# backend/engines/strategies/volume_reversal.py (v9.1 - The Grandmaster Polish)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, Tuple, List, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class WhaleReversal(BaseStrategy):
    """
    WhaleReversal - (v9.1 - The Grandmaster Polish)
    --------------------------------------------------------------
    This version includes the final polish for world-class status. It fixes a
    critical regression bug by restoring the configurable ATR SL multiplier,
    improves data access clarity, and maintains all previously hardened features,
    making it a truly robust and flexible reversal hunting engine.
    """
    strategy_name: str = "WhaleReversal"
    default_config: ClassVar[Dict[str, Any]] = {
        "min_reversal_score": 7,
        "weights": { "whale_intensity": 4, "rejection_wick": 3, "volatility_context": 2, "candlestick_pattern": 2 },
        "adaptive_proximity_multiplier": 0.5,
        "min_rr_ratio": 2.0,
        "atr_sl_multiplier": 1.5, # The configurable SL multiplier
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { "min_required_score": 1, "adx": {"weight": 1, "min_strength": 25} }
    }

    def _to_float(self, v: Any, default: Optional[float] = None) -> Optional[float]:
        if v is None: return default
        try: return float(v)
        except (ValueError, TypeError): return default

    def _calculate_reversal_strength_score(self, direction: str, whales_data: Dict, bollinger_data: Dict) -> Tuple[int, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}) or {}, 0, []
        whales_analysis = (whales_data.get('analysis', {})) or {}
        spike_score = self._to_float(whales_analysis.get('spike_score'), 0.0)
        
        if whales_analysis.get('is_whale_activity', False) and spike_score > 2.5:
            score += int(weights.get('whale_intensity', 4))
            confirmations.append(f"High Whale Intensity (Score: {spike_score:.2f})")

        candle = self.price_data or {}
        high, low, close, open_ = candle.get('high'), candle.get('low'), candle.get('close'), candle.get('open')
        if all(pd.notna(v) for v in [high, low, close, open_]):
            wick, body = high - low, abs(close - open_)
            if wick > 1e-9:
                if body / wick < 0.33:
                    if (direction == "BUY" and (close - low) > (wick * 0.66)) or \
                       (direction == "SELL" and (high - close) > (wick * 0.66)):
                        score += int(weights.get('rejection_wick', 3)); confirmations.append("Strong Rejection Wick")
        
        bollinger_analysis = (bollinger_data.get('analysis', {})) or {}
        if not bollinger_analysis.get('is_in_squeeze', True):
            score += int(weights.get('volatility_context', 2)); confirmations.append("High Volatility Context")

        if self._get_candlestick_confirmation(direction, min_reliability='Strong'):
            score += int(weights.get('candlestick_pattern', 2)); confirmations.append("Strong Candlestick Pattern")
            
        return score, confirmations

    def _find_tested_level(self, cfg: Dict, structure_data: Dict, atr_data: Dict) -> Tuple[Optional[str], Optional[float]]:
        price_low, price_high = self.price_data.get('low'), self.price_data.get('high')
        # ✅ POLISHED: Cleaner and safer ATR value extraction.
        atr_value = (atr_data.get('values') or {}).get('atr')
        if not all(pd.notna(v) for v in [price_low, price_high, atr_value]): return None, None
        
        proximity_zone = atr_value * cfg.get('adaptive_proximity_multiplier', 0.5)
        prox_analysis = (structure_data.get('analysis') or {}).get('proximity', {})
        
        nearest_support = self._to_float((prox_analysis.get('nearest_support_details') or {}).get('price'))
        if nearest_support is not None and (price_low - nearest_support) < proximity_zone:
            return "BUY", nearest_support

        nearest_resistance = self._to_float((prox_analysis.get('nearest_resistance_details') or {}).get('price'))
        if nearest_resistance is not None and (nearest_resistance - price_high) < proximity_zone:
            return "SELL", nearest_resistance
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config or {}
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None
            
        required_names = ['structure', 'whales', 'patterns', 'atr', 'bollinger', 'adx']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing = [k for k, v in indicators.items() if v is None or not v.get('values')]
        if missing:
            reason = f"Invalid/Missing indicators (or 'values' key): {', '.join(missing)}"
            self._log_criteria("Data Availability", False, reason); self._log_final_decision("HOLD", reason); return None
        self._log_criteria("Data Availability", True, "All required indicators are present.")

        signal_direction, tested_level = self._find_tested_level(cfg, indicators['structure'], indicators['atr'])
        trigger_is_ok = signal_direction is not None and tested_level is not None
        self._log_criteria("Primary Trigger (Level Test)", trigger_is_ok, f"Triggered: {signal_direction} @ {tested_level}" if trigger_is_ok else "No key S/R level was tested.")
        if not trigger_is_ok: self._log_final_decision("HOLD", "No valid entry trigger."); return None
        
        reversal_score, score_details = self._calculate_reversal_strength_score(signal_direction, indicators['whales'], indicators['bollinger'])
        min_score = int(cfg.get('min_reversal_score', 7))
        score_is_ok = reversal_score >= min_score
        self._log_criteria("Reversal Score Check", score_is_ok, f"Score={reversal_score} vs min={min_score}")
        if not score_is_ok: self._log_final_decision("HOLD", "Reversal Strength Score is too low."); return None
        confirmations = {"reversal_strength_score": reversal_score, "score_details": ", ".join(score_details)}

        if cfg.get('htf_confirmation_enabled', True):
            opposite_direction = "SELL" if signal_direction == "BUY" else "BUY"
            htf_ok = not self._get_trend_confirmation(opposite_direction)
            self._log_criteria("HTF Filter", htf_ok, "Passed (No strong opposing trend)." if htf_ok else "Strong opposing HTF trend detected.")
            if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
            confirmations['htf_filter'] = "Passed (No strong opposing trend)"

        entry_price = self.price_data.get('close')
        atr_value = (indicators['atr']['values'] or {}).get('atr')
        if not all(pd.notna(v) for v in [entry_price, tested_level, atr_value]):
            self._log_final_decision("HOLD", "Missing price data for risk calculation."); return None
            
        # ✅ REGRESSION FIX: Restore configurable ATR SL multiplier.
        sl_mult = float(cfg.get('atr_sl_multiplier', 1.5))
        stop_loss = tested_level - (atr_value * sl_mult) if signal_direction == "BUY" else tested_level + (atr_value * sl_mult)
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk engine failure."); return None
        
        rr_val = risk_params.get('risk_reward_ratio')
        min_rr = float(cfg.get('min_rr_ratio', 2.0))
        rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
        rr_is_ok = rr_val is not None and rr_val >= min_rr
        
        self._log_criteria("Final R/R Check", rr_is_ok, f"R/R={rr_display} vs min={min_rr}")
        if not rr_is_ok: self._log_final_decision("HOLD", "Final R/R check failed."); return None
        confirmations['rr_check'] = f"Passed (R/R={rr_display})"
        
        self._log_final_decision(signal_direction, "All criteria met. Whale Reversal signal confirmed.")
        
        return { "direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations }
