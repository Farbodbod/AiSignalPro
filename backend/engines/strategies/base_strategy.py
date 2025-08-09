from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseStrategy(ABC):
    """
    World-Class Base Strategy - The Strategy Toolkit for AiSignalPro (v3.0)
    -----------------------------------------------------------------------
    This base class acts as a powerful toolkit for developing strategies.
    It provides a suite of helper methods to easily access and interpret the rich,
    multi-timeframe analysis summary provided by the IndicatorAnalyzer, making
    strategy code clean, readable, and robust.
    """
    strategy_name: str = "BaseStrategy"

    def __init__(self, mtf_summary: Dict[str, Any], config: Dict[str, Any], primary_timeframe: str):
        """
        Initializes the strategy with the full multi-timeframe analysis summary.

        Args:
            mtf_summary (Dict[str, Any]): The complete nested dictionary output from IndicatorAnalyzer.
            config (Dict[str, Any]): The specific configuration for this strategy.
            primary_timeframe (str): The main timeframe this strategy operates on.
        """
        self.mtf_summary = mtf_summary
        self.config = config or {}
        self.primary_timeframe = primary_timeframe
        
        # A direct accessor for the primary timeframe's analysis for convenience
        self.analysis = self.mtf_summary.get(self.primary_timeframe, {})
        self.price_data = self.mtf_summary.get('price_data', {})

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        The main method to be implemented by child strategies.
        It should return a signal package if conditions are met, otherwise None.
        """
        pass

    # --- TOOLKIT: HELPER METHODS FOR STRATEGIES ---

    def get_indicator(self, name: str, timeframe: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Safely retrieves the full analysis output for a specific indicator on a given timeframe.
        
        Example: self.get_indicator('rsi', '4h')
        """
        tf = timeframe if timeframe is not None else self.primary_timeframe
        return self.mtf_summary.get(tf, {}).get(name)

    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        """
        A universal filter that checks if a confirming candlestick pattern exists.
        It's now compatible with the rich output of our world-class PatternIndicator.
        """
        pattern_analysis = self.get_indicator('patterns')
        if not pattern_analysis or 'analysis' not in pattern_analysis:
            return None

        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}
        min_reliability_score = reliability_map.get(min_reliability, 1)

        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        
        found_patterns = pattern_analysis['analysis'].get(target_pattern_list, [])
        
        for pattern in found_patterns:
            pattern_reliability_score = reliability_map.get(pattern.get('reliability'), 0)
            if pattern_reliability_score >= min_reliability_score:
                return pattern # Return the first valid confirming pattern
        
        return None

    def _get_trend_confirmation(self, direction: str, timeframe: str) -> bool:
        """
        Checks a higher timeframe to confirm if the general trend aligns with the signal direction.
        A crucial filter for avoiding counter-trend trades.
        """
        adx_analysis = self.get_indicator('adx', timeframe)
        supertrend_analysis = self.get_indicator('supertrend', timeframe)
        
        if not adx_analysis or not supertrend_analysis:
            return False # If HTF data is not available, do not confirm

        min_adx = self.config.get('min_adx_for_confirmation', 20)
        
        adx_strength = adx_analysis.get('values', {}).get('adx', 0)
        adx_direction = adx_analysis.get('analysis', {}).get('direction')
        supertrend_direction = supertrend_analysis.get('analysis', {}).get('trend')

        if adx_strength < min_adx:
            return False # Trend is not strong enough on the higher timeframe

        if direction.upper() == 'BUY':
            return adx_direction == 'Bullish' and supertrend_direction == 'Uptrend'
        elif direction.upper() == 'SELL':
            return adx_direction == 'Bearish' and supertrend_direction == 'Downtrend'
        
        return False

    def _get_volume_confirmation(self) -> bool:
        """
        Checks the WhaleIndicator for significant volume activity on the signal candle.
        """
        whale_analysis = self.get_indicator('whales')
        if not whale_analysis:
            return False
        
        min_spike_score = self.config.get('min_whale_spike_score', 1.5)
        
        is_whale_activity = whale_analysis.get('analysis', {}).get('is_whale_activity', False)
        spike_score = whale_analysis.get('analysis', {}).get('spike_score', 0)

        return is_whale_activity and spike_score >= min_spike_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        Calculates stop-loss and take-profit targets.
        It prioritizes structural S/R levels and falls back to R/R ratios.
        """
        if not all([entry_price, direction, stop_loss]) or entry_price == stop_loss:
            return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}

        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0:
            return {"stop_loss": stop_loss, "targets": [], "risk_reward_ratio": 0}

        structure_data = self.get_indicator('structure')
        key_levels = structure_data.get('key_levels', {}) if structure_data else {}
        targets = []

        if direction.upper() == 'BUY':
            resistances = sorted([r for r in key_levels.get('resistances', []) if r > entry_price])
            targets = resistances[:3]
        elif direction.upper() == 'SELL':
            supports = sorted([s for s in key_levels.get('supports', []) if s < entry_price], reverse=True)
            targets = supports[:3]

        # Fallback to R/R ratios if no structural targets are found
        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (risk_amount * r if direction.upper() == 'BUY' else -risk_amount * r) for r in reward_ratios]

        if not targets:
            return {"stop_loss": round(stop_loss, 5), "targets": [], "risk_reward_ratio": 0}
            
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)
        
        return {
            "stop_loss": round(stop_loss, 5),
            "targets": [round(t, 5) for t in targets],
            "risk_reward_ratio": actual_rr
        }
