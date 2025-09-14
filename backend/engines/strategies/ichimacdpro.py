# backend/engines/strategies/ichimacdpro.py (v1.1 - The Sentinel's Patch)

import logging
from typing import Dict, Any, Optional, Tuple, ClassVar, List

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchiMACDPro(BaseStrategy):
    """
    IchiMACDPro - (v1.1 - The Sentinel's Patch)
    -----------------------------------------------------------------------------------------
    This version incorporates a critical bug fix identified during the final quality
    assurance review. The 'adx' indicator has been added to the required_names
    list, as it is a vital dependency for the OHRE v3.0 risk management engine
    in the BaseStrategy. This patch ensures the risk engine functions correctly
    and the strategy can operate at its full potential.
    """
    strategy_name: str = "IchiMACDPro"

    default_config: ClassVar[Dict[str, Any]] = {
        "min_rr_ratio": 2.0,
        
        "indicator_configs": {
            "fast_ma": {
                "name": "fast_ma",
                "ma_type": "DEMA",
                "period": 200
            },
            "ichimoku": {
                "name": "ichimoku",
                "tenkan_period": 9,
                "kijun_period": 26,
                "senkou_b_period": 52
            },
            "macd": {
                "name": "macd",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9
            }
        }
    }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        cfg = self.config
        
        # --- 1. Get All Required Indicators ---
        # ✅ CRITICAL FIX v1.1: 'adx' is now included as a required indicator for the OHRE engine.
        required_names = ['fast_ma', 'ichimoku', 'macd', 'structure', 'pivots', 'atr', 'adx']
        
        indicators = {name: self.get_indicator(name) for name in required_names}
        if any(data is None for data in indicators.values()):
            missing = [name for name, data in indicators.items() if data is None]
            self._log_final_decision("HOLD", f"Indicators missing: {', '.join(missing)}"); return None

        # --- STAGE 1: The Strategic Filter (Macro Trend Health) ---
        ma_analysis = self._safe_get(indicators['fast_ma'], ['analysis'], {})
        ma_signal = ma_analysis.get('signal')
        ma_strength = ma_analysis.get('strength')
        
        allowed_direction = None
        if ma_signal == 'Buy' and ma_strength == 'Accelerating':
            allowed_direction = "BUY"
        elif ma_signal == 'Sell' and ma_strength == 'Accelerating':
            allowed_direction = "SELL"
        
        if not allowed_direction:
            self._log_final_decision("HOLD", f"Macro trend is not strong and accelerating. (Signal: {ma_signal}, Strength: {ma_strength})")
            return None
        self._log_criteria("Macro Trend Filter", True, f"Validated Accelerating Trend. Allowed Direction: {allowed_direction}")

        # --- STAGE 2: The Entry Trigger (Ichimoku Convergence) ---
        ichi_analysis = self._safe_get(indicators['ichimoku'], ['analysis'], {})
        tsa_cross = ichi_analysis.get('tsa_cross')
        
        trigger_ok = (allowed_direction == "BUY" and tsa_cross == "Bullish Crossover") or \
                     (allowed_direction == "SELL" and tsa_cross == "Bearish Crossover")
        
        if not trigger_ok:
            self._log_final_decision("HOLD", f"Ichimoku trigger not found or not aligned. (TSA Cross: {tsa_cross})")
            return None
        self._log_criteria("Entry Trigger (Ichimoku)", True, f"Found aligned '{tsa_cross}' signal.")
        
        # --- STAGE 3: The Qualitative Confirmation (MACD Power) ---
        macd_context = self._safe_get(indicators['macd'], ['analysis', 'context'], {})
        histogram_state = macd_context.get('histogram_state')
        
        required_state = "Green" if allowed_direction == "BUY" else "Red"
        
        if histogram_state != required_state:
            self._log_final_decision("HOLD", f"MACD confirmation failed. Required state '{required_state}', but got '{histogram_state}'.")
            return None
        self._log_criteria("Qualitative Confirmation (MACD)", True, f"MACD state is '{histogram_state}', confirming high-conviction momentum.")
        
        # --- STAGE 4: Risk Orchestration & Execution ---
        signal_direction = allowed_direction
        entry_price = self._safe_get(self.price_data, ['close'])
        
        self.config['override_min_rr_ratio'] = cfg.get('min_rr_ratio', 2.0)
        risk_params = self._orchestrate_static_risk(direction=signal_direction, entry_price=entry_price)
        self.config.pop('override_min_rr_ratio', None)

        if not risk_params:
            self._log_final_decision("HOLD", "OHRE engine failed to generate a valid risk plan."); return None
            
        confirmations = {
            "macro_trend": f"Accelerating {ma_signal} (DEMA 200)",
            "entry_trigger": tsa_cross,
            "momentum_confirmation": f"MACD State: {histogram_state} (Strength: {self._safe_get(indicators['macd'], ['analysis', 'strength'])})",
            "risk_engine": self.log_details["risk_trace"][-1].get("source", "OHRE v3.0"),
            "risk_reward": risk_params.get('risk_reward_ratio'),
        }
        self._log_final_decision(signal_direction, "IchiMACDPro Convergence signal confirmed.")
        
        return {"direction": signal_direction, "entry_price": entry_price, **risk_params, "confirmations": confirmations}
