# backend/engines/strategies/trend_rider.py (v12.0 - The Quantum Qualifier)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderPro(BaseStrategy):
    """
    TrendRiderPro - (v12.0 - The Quantum Qualifier)
    -----------------------------------------------------------------------------------------
    The apotheosis of the Trend Rider series. This version integrates a deep analytical
    layer into the established "Quantum Funnel" architecture. It no longer just
    identifies trends; it qualifies their Health (SuperTrend), Power (FastMA),
    and Stamina (MACD), ensuring that only the most robust and highest-quality
    opportunities are considered for execution. This is the pinnacle of its
    evolutionary line.
    """
    strategy_name: str = "TrendRiderPro"

    default_config: ClassVar[Dict[str, Any]] = {
        # --- Stage 1: Battlefield Selection ---
        "market_regime_filter_enabled": True,
        "required_regime": "TRENDING",
        "regime_adx_percentile_threshold": 70.0,
        "default_params": { "min_adx_percentile": 55.0 },
        "timeframe_overrides": {
            "5m": { "min_adx_percentile": 50.0 },
            "1d": { "min_adx_percentile": 60.0 }
        },
        
        # ✅ UPGRADED: The Quantum Scoring Engine
        "conviction_scoring": {
            "enabled": True,
            "min_conviction_score": 10,
            "min_macd_strength": 40,
            "weights": {
                "macd_strong_momentum": 5,
                "htf_alignment": 4,
                "ma_is_accelerating": 3,
                "rsi_room_to_run": 2
            }
        },

        # ✅ NEW: Trend Health Shield
        "trend_health_shield": {
            "enabled": True,
            "veto_on_exhausted": True,
            "veto_on_overextended": True
        },

        # --- Final Defensive Shield ---
        "exhaustion_shield": {
            "enabled": True, "rsi_lookback": 120,
            "rsi_buy_percentile": 85, "rsi_sell_percentile": 15
        },
        
        "min_rr_ratio": 1.8,
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": {
            "min_required_score": 2, 
            "adx": {"weight": 1, "min_percentile": 70.0},
            "supertrend": {"weight": 1}
        }
    }

    def _get_signal_config(self) -> Dict[str, Any]:
        final_cfg = self.config.copy()
        base_params = self.config.get("default_params", {})
        tf_overrides = self.config.get("timeframe_overrides", {}).get(self.primary_timeframe, {})
        final_params = {**base_params, **tf_overrides}
        final_cfg.update(final_params)
        return final_cfg

    def _get_primary_signal(self, cfg: Dict[str, Any]) -> Tuple[Optional[str], str]:
        trigger_name = "SuperTrend Continuation"
        supertrend_data = self.get_indicator('supertrend')
        if not supertrend_data or 'analysis' not in supertrend_data: return None, ""
        analysis = supertrend_data['analysis']
        trend_direction, signal = analysis.get('trend'), analysis.get('signal')
        if signal == 'Trend Continuation':
            if trend_direction == 'Uptrend': return "BUY", trigger_name
            if trend_direction == 'Downtrend': return "SELL", trigger_name
        signal_text = str(signal).lower()
        if "bullish crossover" in signal_text: return "BUY", "SuperTrend Crossover"
        if "bearish crossover" in signal_text: return "SELL", "SuperTrend Crossover"
        return None, ""

    def _fmt5(self, x: Any) -> str:
        return f"{float(x):.5f}" if self._is_valid_number(x) else "N/A"

    def _calculate_conviction_score(self, direction: str, indicators: Dict) -> Tuple[int, List[str]]:
        cfg = self.config.get('conviction_scoring', {})
        weights = cfg.get('weights', {})
        score, details = 0, []

        min_strength = cfg.get('min_macd_strength', 40)
        macd_analysis = self._safe_get(indicators.get('macd'), ['analysis'], {})
        macd_strength = macd_analysis.get('strength', 0)
        macd_momentum = macd_analysis.get('context', {}).get('momentum')
        if macd_momentum == "Increasing" and macd_strength >= min_strength:
            score += weights.get('macd_strong_momentum', 0)
            details.append(f"MACD++ (Str:{macd_strength})")
        
        ma_analysis = self._safe_get(indicators.get('fast_ma'), ['analysis'], {})
        ma_strength = ma_analysis.get('strength')
        if ma_strength == "Accelerating":
            score += weights.get('ma_is_accelerating', 0)
            details.append("MA Accel.")

        rsi_val = self._safe_get(indicators.get('rsi'), ['values', 'rsi'], 50.0)
        if (direction == "BUY" and rsi_val < 75) or (direction == "SELL" and rsi_val > 25):
            score += weights.get('rsi_room_to_run', 0)
            details.append(f"RSI OK ({rsi_val:.1f})")

        if self._get_trend_confirmation(direction):
            score += weights.get('htf_alignment', 0)
            details.append("HTF Aligned")
            
        return score, details

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self._get_signal_config()
        if not self.price_data: self._log_final_decision("HOLD", "No price data available."); return None

        # ✅ CRITICAL FIX: Added 'atr' which is essential for OHRE v3.0
        required_names = ['adx', 'fast_ma', 'supertrend', 'rsi', 'macd', 'structure', 'pivots', 'atr']
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None
        
        # --- STAGE 1: BATTLEFIELD SELECTION ---
        if cfg.get('market_regime_filter_enabled'):
            adx_percentile = self._safe_get(indicators.get('adx'), ['analysis', 'adx_percentile'], 0.0)
            if adx_percentile < cfg.get('regime_adx_percentile_threshold', 70.0):
                self._log_final_decision("HOLD", f"Regime filter failed (ADX %: {adx_percentile:.2f})"); return None
    
        # --- STAGE 2: PRIMARY TRIGGER ---
        signal_direction, entry_trigger_name = self._get_primary_signal(cfg)
        if not signal_direction: return None

        # --- STAGE 3: CORE CONFIRMATION & DEFENSIVE SHIELDS ---
        current_price = self.price_data.get('close')
        ma_value = self._safe_get(indicators.get('fast_ma'), ['values', 'ma_value'])
        if not self._is_valid_number(current_price, ma_value):
            self._log_final_decision("HOLD", "Invalid price/MA for filters."); return None

        if (signal_direction == "BUY" and current_price < ma_value) or \
           (signal_direction == "SELL" and current_price > ma_value):
            self._log_final_decision("HOLD", "Master Trend filter failed."); return None
        
        health_shield_cfg = cfg.get('trend_health_shield', {})
        if health_shield_cfg.get('enabled', True):
            st_analysis = self._safe_get(indicators.get('supertrend'), ['analysis'], {})
            if health_shield_cfg.get('veto_on_exhausted') and st_analysis.get('is_exhausted'):
                self._log_final_decision("HOLD", "Vetoed by Trend Health Shield: Trend is exhausted."); return None
            if health_shield_cfg.get('veto_on_overextended') and st_analysis.get('is_overextended'):
                self._log_final_decision("HOLD", "Vetoed by Trend Health Shield: Trend is overextended."); return None
        
        shield_cfg = cfg.get('exhaustion_shield', {})
        if shield_cfg.get('enabled', True):
            if self._is_trend_exhausted_dynamic(
                direction=signal_direction,
                rsi_lookback=shield_cfg.get('rsi_lookback', 120),
                rsi_buy_percentile=shield_cfg.get('rsi_buy_percentile', 85),
                rsi_sell_percentile=shield_cfg.get('rsi_sell_percentile', 15)
            ):
                self._log_final_decision("HOLD", "Signal vetoed by final RSI Exhaustion Shield."); return None
        
        self._log_criteria("Core Filters & Shields", True, "Signal passed all hard checks.")

        # --- STAGE 4: CONVICTION SCORING ENGINE ---
        scoring_cfg = cfg.get('conviction_scoring', {})
        if scoring_cfg.get('enabled', True):
            min_score = scoring_cfg.get('min_conviction_score', 10)
            conviction_score, score_details = self._calculate_conviction_score(signal_direction, indicators)
            if conviction_score < min_score:
                self._log_final_decision("HOLD", f"Conviction score {conviction_score}/{min_score} too low."); return None
        else:
            conviction_score, score_details = 0, ["Disabled"]

        # --- STAGE 5: RISK ORCHESTRATION ---
        entry_price = self.price_data.get('close')
        min_rr_needed = cfg.get('min_rr_ratio', 1.8)
        self.config['override_min_rr_ratio'] = min_rr_needed
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params:
            self._log_final_decision("HOLD", f"OHRE failed to find plan (min R:R {min_rr_needed})."); return None
        
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "conviction_score": f"{conviction_score}/14 ({', '.join(score_details)})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "High-Conviction signal confirmed by Quantum Engine.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
