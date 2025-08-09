from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseStrategy(ABC):
    """
    World-Class Base Strategy - The Strategy Toolkit for AiSignalPro (v3.1 - Final)
    --------------------------------------------------------------------------------
    This final version correctly handles the injection of Higher-Timeframe (HTF)
    analysis, allowing all child strategies to perform robust, multi-timeframe
    confirmations.
    """
    strategy_name: str = "BaseStrategy"

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any], htf_analysis: Optional[Dict[str, Any]] = None):
        """
        Initializes the strategy with its primary analysis and optional HTF analysis.
        """
        self.analysis = analysis_summary
        self.config = config or {}
        self.htf_analysis = htf_analysis or {} # Ensure it's always a dict
        self.price_data = self.analysis.get('price_data', {})

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
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
        """
        ✨ REFINED: Checks the injected htf_analysis to confirm trend alignment.
        """
        # We now look inside self.htf_analysis, which is provided by the orchestrator.
        adx_analysis = self.htf_analysis.get('adx')
        supertrend_analysis = self.htf_analysis.get('supertrend')
        
        if not adx_analysis or not supertrend_analysis: return False

        min_adx = self.config.get('min_adx_for_confirmation', 20)
        adx_strength = adx_analysis.get('values', {}).get('adx', 0)
        adx_direction = adx_analysis.get('analysis', {}).get('direction')
        supertrend_direction = supertrend_analysis.get('analysis', {}).get('trend')

        if adx_strength < min_adx: return False

        if direction.upper() == 'BUY':
            return adx_direction == 'Bullish' and supertrend_direction == 'Uptrend'
        elif direction.upper() == 'SELL':
            return adx_direction == 'Bearish' and supertrend_direction == 'Downtrend'
        return False

    def _get_volume_confirmation(self) -> bool:
        whale_analysis = self.get_indicator('whales')
        if not whale_analysis: return False
        min_spike_score = self.config.get('min_whale_spike_score', 1.5)
        is_whale_activity = whale_analysis.get('analysis', {}).get('is_whale_activity', False)
        spike_score = whale_analysis.get('analysis', {}).get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if not all([entry_price, direction, stop_loss]) or entry_price == stop_loss: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}
        structure_data = self.get_indicator('structure')
        key_levels = structure_data.get('key_levels', {}) if structure_data else {}
        targets = []
        if direction.upper() == 'BUY':
            resistances = sorted([r for r in key_levels.get('resistances', []) if r > entry_price])
            targets = resistances[:3]
        elif direction.upper() == 'SELL':
            supports = sorted([s for s in key_levels.get('supports', []) if s < entry_price], reverse=True)
            targets = supports[:3]
        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (risk_amount * r if direction.upper() == 'BUY' else -risk_amount * r) for r in reward_ratios]
        if not targets: return {"stop_loss": round(stop_loss, 5), "targets": [], "risk_reward_ratio": 0}
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
