# backend/engines/strategies/ichimacdpro.py (v2.1 - The Protocol Patch)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchiMACDPro(BaseStrategy):
    """
    IchiMACDPro - (v2.1 - The Protocol Patch)
    -----------------------------------------------------------------------------------------
    This version applies a critical hotfix to resolve a TypeError. The call to the
    _is_trend_exhausted_dynamic helper function has been corrected to pass only the
    expected keyword arguments, excluding the 'enabled' flag. This ensures perfect
    compliance with the BaseStrategy's function signatures and guarantees stable,
    error-free execution of the Exhaustion Shield.
    """
    strategy_name: str = "IchiMACDPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "min_rr_ratio": 2.0,

        "exhaustion_shield": {
            "enabled": True,
            "rsi_lookback": 120,
            "rsi_buy_percentile": 88,
            "rsi_sell_percentile": 12
        },
        
        "htf_confirmation_enabled": True, 
        "htf_map": { "5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d" },
        "htf_confirmations": { 
            "min_required_score": 2,
            "adx": {"weight": 1, "min_percentile": 70.0},
            "supertrend": {"weight": 1}
        },
        
        "conviction_scoring": {
            "enabled": True,
            "min_conviction_score": 13,
            "weights": {
                "ma_accelerating": 5,
                "ichi_tsa_cross": 5,
                "macd_confirm": 4,
                "htf_alignment": 3
            }
        },
        
        "indicator_configs": {
            "fast_ma":    { "name": "fast_ma", "ma_type": "DEMA", "period": 200 },
            "ichimoku":   { "name": "ichimoku" },
            "macd":       { "name": "macd" },
            "adx":        { "name": "adx" },
            "rsi":        { "name": "rsi" },
            "supertrend": { "name": "supertrend" }
        }
    }

    def _calculate_conviction_score(self, indicators: Dict) -> Tuple[int, List[str], Optional[str]]:
        # --- This function remains unchanged ---
        cfg = self.config.get('conviction_scoring', {})
        weights = cfg.get('weights', {})
        score, details, confirmed_direction = 0, [], None
        ma_analysis = self._safe_get(indicators['fast_ma'], ['analysis'], {})
        if ma_analysis.get('strength') == 'Accelerating':
            signal = ma_analysis.get('signal')
            if signal == 'Buy':
                confirmed_direction = "BUY"
                score += weights.get('ma_accelerating', 0)
                details.append("MA Accel+")
            elif signal == 'Sell':
                confirmed_direction = "SELL"
                score += weights.get('ma_accelerating', 0)
                details.append("MA Accel-")
        if not confirmed_direction:
            return 0, ["MA Not Accelerating"], None
        ichi_analysis = self._safe_get(indicators['ichimoku'], ['analysis'], {})
        tsa_cross = ichi_analysis.get('tsa_cross')
        if (confirmed_direction == "BUY" and tsa_cross == "Bullish Crossover") or \
           (confirmed_direction == "SELL" and tsa_cross == "Bearish Crossover"):
            score += weights.get('ichi_tsa_cross', 0)
            details.append("Ichi Cross")
        macd_context = self._safe_get(indicators['macd'], ['analysis', 'context'], {})
        hist_state = macd_context.get('histogram_state')
        required_state = "Green" if confirmed_direction == "BUY" else "Red"
        if hist_state == required_state:
            score += weights.get('macd_confirm', 0)
            details.append(f"MACD {hist_state}")
        if self.config.get('htf_confirmation_enabled'):
            if self._get_trend_confirmation(confirmed_direction):
                score += weights.get('htf_alignment', 0)
                details.append("HTF Aligned")
        return score, details, confirmed_direction

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        required_names = ['fast_ma', 'ichimoku', 'macd', 'rsi', 'supertrend', 'structure', 'pivots', 'atr', 'adx']
        
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None

        # --- STAGE 1: THE GATEKEEPER (Exhaustion Shield) ---
        shield_cfg = cfg.get('exhaustion_shield', {})
        if shield_cfg.get('enabled', True):
            # ✅ SURGICAL FIX v2.1: Create a clean dictionary for the function call,
            # excluding the 'enabled' key to prevent the TypeError.
            shield_params = {
                "rsi_lookback": shield_cfg.get('rsi_lookback', 120),
                "rsi_buy_percentile": shield_cfg.get('rsi_buy_percentile', 88),
                "rsi_sell_percentile": shield_cfg.get('rsi_sell_percentile', 12)
            }
            
            # Determine direction for the shield check
            temp_direction = "BUY" if self._safe_get(indicators['fast_ma'], ['analysis', 'signal']) == 'Buy' else "SELL"
            
            # Call the function with the cleaned, correct parameters
            if self._is_trend_exhausted_dynamic(direction=temp_direction, **shield_params):
                self._log_final_decision("HOLD", "Vetoed by Exhaustion Shield: Army is fatigued."); return None
        
        self._log_criteria("Defensive Shield", True, "Army has sufficient stamina for an attack.")

        # --- STAGE 2: THE WAR COUNCIL (Conviction Scoring) ---
        scoring_cfg = cfg.get('conviction_scoring', {})
        if scoring_cfg.get('enabled'):
            min_score = scoring_cfg.get('min_conviction_score', 13)
            conviction_score, score_details, signal_direction = self._calculate_conviction_score(indicators)
            
            if not signal_direction or conviction_score < min_score:
                self._log_final_decision("HOLD", f"War council did not reach consensus. Score {conviction_score}/{min_score}. Details: {', '.join(score_details)}")
                return None
            self._log_criteria("War Council Consensus", True, f"Score: {conviction_score}/{min_score}. Details: {', '.join(score_details)}")
        else:
             self._log_final_decision("HOLD", "Conviction scoring is disabled."); return None

        # --- STAGE 3: RISK ORCHESTRATION & EXECUTION ---
        entry_price = self._safe_get(self.price_data, ['close'])
        
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 2.0)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params:
            self._log_final_decision("HOLD", "OHRE engine failed to generate a valid risk plan."); return None
            
        confirmations = {
            "conviction_score": f"{conviction_score}/17 ({', '.join(score_details)})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "IchiMACDPro signal confirmed by the Quantum Legion.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
