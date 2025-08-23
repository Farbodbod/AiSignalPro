# backend/engines/strategies/volume_catalyst.py (v9.1 - The Final Polish)

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, Tuple, List, ClassVar
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystPro(BaseStrategy):
    """
    VolumeCatalystPro - (v9.1 - The Final Polish)
    ------------------------------------------------------------------
    This version incorporates final polishing touches for world-class quality.
    The Quantum Score is now a float for higher precision, and the HTF filter
    logging is more granular, distinguishing between missing data and opposing
    trends for superior observability.
    """
    strategy_name: str = "VolumeCatalystPro"
    default_config: ClassVar[Dict[str, Any]] = {
        "min_quality_score": 70.0, # Now a float for higher precision
        "weights": { "volume_catalyst_strength": 4, "momentum_thrust": 3, "volatility_release": 3, },
        "cci_threshold": 100.0,
        "atr_sl_multiplier": 1.5,
        "min_rr_ratio": 2.0,
        "htf_confirmation_enabled": True,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { "min_required_score": 2, "adx": {"weight": 1, "min_strength": 25}, "supertrend": {"weight": 1} }
    }

    def _to_float(self, v: Any, default: Optional[float] = None) -> Optional[float]:
        if v is None: return default
        try: return float(v)
        except (ValueError, TypeError): return default

    def _calculate_breakout_quality_score(self, direction: str, whales_data: Dict, cci_data: Dict, bollinger_data: Dict) -> Tuple[float, List[str]]:
        weights, score, confirmations = self.config.get('weights', {}), 0, []
        
        whales_analysis = (whales_data.get('analysis', {})) or {}
        if whales_analysis.get('is_whale_activity'):
            whale_pressure = str(whales_analysis.get('pressure', '')).lower()
            if (direction == "BUY" and 'buy' in whale_pressure) or (direction == "SELL" and 'sell' in whale_pressure):
                score += weights.get('volume_catalyst_strength', 4)
                confirmations.append(f"Volume Catalyst (Spike: {whales_analysis.get('spike_score', 0):.2f})")

        cci_val = self._to_float((cci_data.get('values') or {}).get('cci'))
        if pd.notna(cci_val):
            cci_threshold = float(self.config.get('cci_threshold', 100.0))
            if (direction == "BUY" and cci_val > cci_threshold) or (direction == "SELL" and cci_val < -cci_threshold):
                score += weights.get('momentum_thrust', 3)
                confirmations.append(f"Momentum Thrust (CCI: {cci_val:.2f})")

        if (bollinger_data.get('analysis', {}) or {}).get('is_squeeze_release', False):
            score += weights.get('volatility_release', 3)
            confirmations.append("Volatility Release")
            
        # ✅ FINAL POLISH: Return score as a float for higher precision.
        max_possible_score = sum(weights.values())
        normalized_score = round((score / max_possible_score) * 100, 2) if max_possible_score > 0 else 0.0
            
        return normalized_score, confirmations

    def _find_structural_breakout(self, structure_data: Dict) -> Tuple[Optional[str], Optional[float]]:
        if self.df is None or len(self.df) < 2 or self.price_data is None: return None, None
        
        current_price = self.price_data.get('close')
        prev_close = self._to_float(self.df['close'].iloc[-2])
        if prev_close is None or current_price is None: return None, None

        prox_analysis = (structure_data.get('analysis') or {}).get('proximity', {})
        
        nearest_resistance = self._to_float((prox_analysis.get('nearest_resistance_details') or {}).get('price'))
        if nearest_resistance is not None and prev_close <= nearest_resistance < current_price:
            return "BUY", nearest_resistance

        nearest_support = self._to_float((prox_analysis.get('nearest_support_details') or {}).get('price'))
        if nearest_support is not None and prev_close >= nearest_support > current_price:
            return "SELL", nearest_support
            
        return None, None

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None
        
        required_names = ['structure', 'whales', 'cci', 'keltner_channel', 'bollinger', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        missing = [name for name, data in indicators.items() if data is None or not data.get('values')]
        if missing:
            reason = f"Invalid/Missing indicators (or 'values' key): {', '.join(missing)}"
            self._log_criteria("Data Availability", False, reason); self._log_final_decision("HOLD", reason); return None
        self._log_criteria("Data Availability", True, "All required indicators are present.")

        signal_direction, broken_level = self._find_structural_breakout(indicators['structure'])
        trigger_is_ok = signal_direction is not None
        self._log_criteria("Primary Trigger (Structural Breakout)", trigger_is_ok, f"Detected: {signal_direction} @ {broken_level}" if trigger_is_ok else "No structural breakout.")
        if not trigger_is_ok: self._log_final_decision("HOLD", "No valid entry trigger."); return None
        
        bqs, score_details = self._calculate_breakout_quality_score(signal_direction, indicators['whales'], indicators['cci'], indicators['bollinger'])
        min_score = float(cfg.get('min_quality_score', 70.0))
        score_is_ok = bqs >= min_score
        self._log_criteria("Breakout Quality Score", score_is_ok, f"Score={bqs:.2f} vs min={min_score}. Details: {', '.join(score_details) or 'none'}")
        if not score_is_ok: self._log_final_decision("HOLD", "Breakout Quality Score is too low."); return None
        confirmations: Dict[str, Any] = {"breakout_quality_score": bqs, "score_details": ", ".join(score_details)}

        # ✅ FINAL POLISH: More granular HTF check and logging.
        if cfg.get('htf_confirmation_enabled', True):
            target_htf = cfg.get('htf_map', {}).get(self.primary_timeframe)
            if not target_htf: # Highest timeframe, HTF check passes by default
                self._log_criteria("HTF Filter", True, "At highest timeframe, HTF check not required.")
                htf_ok = True
            elif not self.htf_analysis:
                self._log_criteria("HTF Filter", False, f"HTF data package for '{target_htf}' not available.")
                htf_ok = False
            else:
                htf_ok = self._get_trend_confirmation(signal_direction)
                self._log_criteria("HTF Filter", htf_ok, "HTF aligned." if htf_ok else "Not aligned with HTF trend.")
            
            if not htf_ok: self._log_final_decision("HOLD", "HTF filter failed."); return None
            confirmations['htf_filter'] = "Passed (HTF Aligned)"
        
        entry_price = self.price_data.get('close')
        keltner_mid = self._to_float((indicators['keltner_channel']['values'] or {}).get('middle_band'))
        atr_value = self._to_float((indicators['atr']['values'] or {}).get('atr'))
        
        if not all(pd.notna(v) for v in [entry_price, keltner_mid, atr_value]):
            self._log_final_decision("HOLD", "Missing data for Stop Loss calculation."); return None

        atr_mult = float(cfg.get('atr_sl_multiplier', 1.5))
        stop_loss = keltner_mid - (atr_value * atr_mult) if signal_direction == "BUY" else keltner_mid + (atr_value * atr_mult)
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)
        if not risk_params or not risk_params.get("targets"):
            self._log_final_decision("HOLD", "Risk engine failed to produce parameters."); return None

        rr_val = risk_params.get('risk_reward_ratio')
        min_rr = float(cfg.get('min_rr_ratio', 2.0))
        rr_display = f"{rr_val:.2f}" if rr_val is not None else "N/A"
        rr_is_ok = rr_val is not None and rr_val >= min_rr
        self._log_criteria("Final R/R Check", rr_is_ok, f"Calculated={rr_display}, Required={min_rr}")
        if not rr_is_ok: self._log_final_decision("HOLD", "Final R/R check failed."); return None
        confirmations['rr_check'] = f"Passed (R/R: {rr_display})"
        
        self._log_final_decision(signal_direction, "All criteria met. Volume Catalyst signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
