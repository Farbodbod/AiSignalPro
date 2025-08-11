from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    """
    World-Class Base Strategy - The Strategy Toolkit for AiSignalPro (v3.3 - Anti-Fragile)
    This version features a bulletproof 'get_indicator' method that acts as a
    smart guard, ensuring strategies never receive failed or incomplete indicator data.
    """
    strategy_name: str = "BaseStrategy"

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], primary_timeframe: str, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis = primary_analysis
        self.config = config or {}
        self.htf_analysis = htf_analysis or {}
        self.primary_timeframe = primary_timeframe
        self.price_data = self.analysis.get('price_data', {})
        self.df = primary_analysis.get('final_df') # Assume the final_df is passed in the analysis package

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        pass

    # --- TOOLKIT: HELPER METHODS FOR STRATEGIES ---

    def get_indicator(self, name: str, analysis_source: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        ✅ FIX: Bulletproof 'Safe Getter' for indicator data.
        It checks for existence, validity (not None), and absence of error status
        before returning the data.
        """
        source = analysis_source if analysis_source is not None else self.analysis
        
        indicator_data = source.get(name)
        
        # 1. Check for existence and that it's a dictionary
        if not indicator_data or not isinstance(indicator_data, dict):
            return None
        
        # 2. Check for an explicit error/failure status
        if "error" in indicator_data.get("status", "").lower() or "failed" in indicator_data.get("status", "").lower():
            return None
        
        # 3. Check for the essential 'analysis' key
        if 'analysis' not in indicator_data:
            return None

        return indicator_data

    def _get_trend_confirmation(self, direction: str, timeframe: str) -> bool:
        # Use the safe getter for HTF analysis
        adx_analysis = self.get_indicator('adx', analysis_source=self.htf_analysis)
        supertrend_analysis = self.get_indicator('supertrend', analysis_source=self.htf_analysis)
        
        if not adx_analysis or not supertrend_analysis:
            logger.warning(f"HTF Trend confirmation failed for {timeframe}: missing adx or supertrend data.")
            return False
            
        min_adx = self.config.get('min_adx_for_confirmation', 20)
        adx_strength = adx_analysis.get('values', {}).get('adx', 0)
        adx_direction = adx_analysis.get('analysis', {}).get('direction')
        supertrend_trend = supertrend_analysis.get('analysis', {}).get('trend')
        
        if adx_strength < min_adx: return False
        
        if direction.upper() == 'BUY':
            return adx_direction == 'Bullish' and supertrend_trend == 'Uptrend'
        elif direction.upper() == 'SELL':
            return adx_direction == 'Bearish' and supertrend_trend == 'Downtrend'
        return False
        
    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if not all([entry_price, direction, stop_loss]) or entry_price == stop_loss: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount < 1e-9: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        
        # Use the safe getter for structure data
        structure_data = self.get_indicator('structure')
        key_levels = structure_data.get('key_levels', {}) if structure_data else {}
        targets = []
        
        resistances_raw = key_levels.get('resistances', [])
        supports_raw = key_levels.get('supports', [])
        
        resistances = sorted([r for r in list(resistances_raw) if isinstance(r, (int, float))])
        supports = sorted([s for s in list(supports_raw) if isinstance(s, (int, float))], reverse=True)

        if direction.upper() == 'BUY':
            targets = [r for r in resistances if r > entry_price][:3]
        elif direction.upper() == 'SELL':
            targets = [s for s in supports if s < entry_price][:3]

        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (risk_amount * r if direction.upper() == 'BUY' else -risk_amount * r) for r in reward_ratios]
        
        if not targets: return {"stop_loss": round(stop_loss, 5), "targets": [], "risk_reward_ratio": 0}
        
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)
        
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
