from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseStrategy(ABC):
    """
    World-Class Base Strategy - The Strategy Toolkit for AiSignalPro (v3.2 - Bulletproof & Final)
    ---------------------------------------------------------------------------------------------
    This final, complete version is fully harmonized with the entire AiSignalPro
    ecosystem. It's a robust toolkit for building powerful, multi-timeframe strategies,
    featuring a bulletproof risk management method.
    """
    strategy_name: str = "BaseStrategy"

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], primary_timeframe: str, htf_analysis: Optional[Dict[str, Any]] = None):
        """
        Initializes the strategy with its primary analysis, its own timeframe context,
        and optional HTF analysis.
        """
        self.analysis = primary_analysis
        self.config = config or {}
        self.htf_analysis = htf_analysis or {}
        self.primary_timeframe = primary_timeframe
        self.price_data = self.analysis.get('price_data', {})

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        The main method to be implemented by child strategies.
        It should return a signal package if conditions are met, otherwise None.
        """
        pass

    # --- TOOLKIT: HELPER METHODS FOR STRATEGIES ---

    def get_indicator(self, name: str) -> Optional[Dict[str, Any]]:
        """ Safely retrieves an indicator's analysis from the primary timeframe summary. """
        return self.analysis.get(name)

    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        pattern_analysis = self.get_indicator('patterns')
        if not pattern_analysis or 'analysis' not in pattern_analysis: return None
        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}
        min_reliability_score = reliability_map.get(min_reliability, 1)
        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = pattern_analysis['analysis'].get(target_pattern_list, [])
        for pattern in found_patterns:
            if reliability_map.get(pattern.get('reliability'), 0) >= min_reliability_score:
                return pattern
        return None

    def _get_trend_confirmation(self, direction: str, timeframe: str) -> bool:
        """ Checks the injected htf_analysis to confirm trend alignment. """
        adx_analysis = self.htf_analysis.get('adx')
        supertrend_analysis = self.htf_analysis.get('supertrend')
        if not adx_analysis or not supertrend_analysis: return False
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

    def _get_volume_confirmation(self) -> bool:
        whale_analysis = self.get_indicator('whales')
        if not whale_analysis: return False
        min_spike_score = self.config.get('min_whale_spike_score', 1.5)
        is_whale_activity = whale_analysis.get('analysis', {}).get('is_whale_activity', False)
        spike_score = whale_analysis.get('analysis', {}).get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        Calculates stop-loss and take-profit targets.
        It prioritizes structural S/R levels and falls back to R/R ratios.
        This version is bulletproof against unexpected data types.
        """
        if not all([entry_price, direction, stop_loss]) or entry_price == stop_loss: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount < 1e-9: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        
        structure_data = self.get_indicator('structure')
        key_levels = structure_data.get('key_levels', {}) if structure_data else {}
        targets = []
        
        # ✨ BULLETPROOF FIX: Explicitly convert S/R levels to a sorted list to prevent any TypeErrors.
        resistances_raw = key_levels.get('resistances', [])
        supports_raw = key_levels.get('supports', [])
        
        resistances = sorted([r for r in list(resistances_raw) if isinstance(r, (int, float))])
        supports = sorted([s for s in list(supports_raw) if isinstance(s, (int, float))], reverse=True)

        if direction.upper() == 'BUY':
            structural_targets = [r for r in resistances if r > entry_price][:3]
            targets = structural_targets
        elif direction.upper() == 'SELL':
            structural_targets = [s for s in supports if s < entry_price][:3]
            targets = structural_targets

        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (risk_amount * r if direction.upper() == 'BUY' else -risk_amount * r) for r in reward_ratios]
        
        if not targets: return {"stop_loss": round(stop_loss, 5), "targets": [], "risk_reward_ratio": 0}
        
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)
        
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
