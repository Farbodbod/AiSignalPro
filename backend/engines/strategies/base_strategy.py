from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
import logging

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    """
    World-Class Base Strategy Framework - (v4.0 - Miracle Framework)
    ---------------------------------------------------------------------------------------------
    This is not just a base class; it's a complete, world-class strategy development
    framework. It features three core miracle engines:
    1.  Dynamic HTF Engine: Intelligently selects the correct higher-timeframe for
        confirmation based on a configurable map.
    2.  Weighted Multi-Confirmation Engine: Allows strategies to define a sophisticated,
        weighted scoring system for HTF trend validation.
    3.  Bulletproof Risk Engine: Calculates risk-reward ratios with pinpoint accuracy,
        accounting for real-world costs like fees and slippage.
    """
    strategy_name: str = "BaseStrategy"
    
    # ✅ MIRACLE UPGRADE: Strategies can define their default configuration here
    default_config: Dict[str, Any] = {}

    def __init__(self, primary_analysis: Dict[str, Any], config: Dict[str, Any], primary_timeframe: str, htf_analysis: Optional[Dict[str, Any]] = None):
        # Merge the provided config with the strategy's default config
        merged_config = {**self.default_config, **(config or {})}
        
        self.analysis = primary_analysis
        self.config = merged_config
        self.htf_analysis = htf_analysis or {}
        self.primary_timeframe = primary_timeframe
        self.price_data = self.analysis.get('price_data')
        self.df = self.analysis.get('final_df')

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        pass

    # --- TOOLKIT: HELPER METHODS FOR STRATEGIES ---

    def get_indicator(self, name: str, analysis_source: Optional[Dict] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """ Bulletproof 'Safe Getter' for indicator data. (Unchanged) """
        if kwargs: logger.warning(f"Strategy '{self.strategy_name}' called get_indicator with unexpected arguments: {kwargs}. These are being ignored.")
        source = analysis_source if analysis_source is not None else self.analysis
        if not source: return None
        indicator_data = source.get(name)
        if not indicator_data or not isinstance(indicator_data, dict): return None
        if "error" in indicator_data.get("status", "").lower() or "failed" in indicator_data.get("status", "").lower(): return None
        if 'analysis' not in indicator_data: return None
        return indicator_data
    
    def _get_candlestick_confirmation(self, direction: str, min_reliability: str = 'Medium') -> Optional[Dict[str, Any]]:
        """ Safely checks for a confirming candlestick pattern. (Unchanged) """
        pattern_analysis = self.get_indicator('patterns')
        if not pattern_analysis: return None
        reliability_map = {'Low': 0, 'Medium': 1, 'Strong': 2}
        min_reliability_score = reliability_map.get(min_reliability, 1)
        target_pattern_list = 'bullish_patterns' if direction.upper() == "BUY" else 'bearish_patterns'
        found_patterns = pattern_analysis['analysis'].get(target_pattern_list, [])
        for pattern in found_patterns:
            if reliability_map.get(pattern.get('reliability'), 0) >= min_reliability_score:
                return pattern
        return None

    def _get_volume_confirmation(self) -> bool:
        """ Safely checks for whale activity. (Unchanged) """
        whale_analysis = self.get_indicator('whales')
        if not whale_analysis: return False
        min_spike_score = self.config.get('min_whale_spike_score', 1.5)
        is_whale_activity = whale_analysis.get('analysis', {}).get('is_whale_activity', False)
        spike_score = whale_analysis.get('analysis', {}).get('spike_score', 0)
        return is_whale_activity and spike_score >= min_spike_score

    def _get_trend_confirmation(self, direction: str) -> bool:
        """
        ✅ MIRACLE UPGRADE: This is now the Weighted Multi-Confirmation Engine.
        It uses a dynamic HTF map and a weighted scoring system defined in the config.
        """
        htf_map = self.config.get('htf_map', {})
        target_htf = htf_map.get(self.primary_timeframe)
        if not target_htf:
            logger.debug(f"[{self.strategy_name}] No HTF mapping defined for timeframe '{self.primary_timeframe}'. Skipping HTF check.")
            return True # If no map, we don't block the signal

        # Ensure the correct HTF analysis package is available
        if not self.htf_analysis or self.htf_analysis.get('timeframe') != target_htf:
            logger.warning(f"[{self.strategy_name}] Required HTF analysis for '{target_htf}' not available. Skipping HTF check.")
            return True

        htf_rules = self.config.get('htf_confirmations', {})
        min_required_score = htf_rules.get('min_required_score', 1)
        current_score = 0
        
        # Check ADX rule
        if "adx" in htf_rules:
            rule = htf_rules['adx']
            adx_analysis = self.get_indicator('adx', analysis_source=self.htf_analysis)
            if adx_analysis:
                adx_strength = adx_analysis.get('values', {}).get('adx', 0)
                adx_dir = adx_analysis.get('analysis', {}).get('direction', 'Neutral')
                if adx_strength >= rule.get('min_strength', 20) and direction.capitalize() in adx_dir:
                    current_score += rule.get('weight', 1)

        # Check SuperTrend rule
        if "supertrend" in htf_rules:
            rule = htf_rules['supertrend']
            st_analysis = self.get_indicator('supertrend', analysis_source=self.htf_analysis)
            if st_analysis:
                st_trend = st_analysis.get('analysis', {}).get('trend', 'Neutral')
                if (direction == "BUY" and st_trend == "Uptrend") or (direction == "SELL" and st_trend == "Downtrend"):
                    current_score += rule.get('weight', 1)

        return current_score >= min_required_score

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        ✅ MIRACLE UPGRADE: This is now the Bulletproof Risk Engine.
        It calculates a more realistic Risk-Reward Ratio by including estimated
        fees and slippage in the total risk calculation.
        """
        if not all([entry_price, direction, stop_loss]) or entry_price == stop_loss: return {}
        
        # Pull cost parameters from the main config
        main_config = self.config.get('_main_config', {}) # Assumes main config is passed
        fees_pct = main_config.get("general", {}).get("assumed_fees_pct", 0.001)
        slippage_pct = main_config.get("general", {}).get("assumed_slippage_pct", 0.0005)
        
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit < 1e-9: return {}
        
        # Calculate total risk including costs
        total_risk_per_unit = risk_per_unit + (entry_price * fees_pct) + (entry_price * slippage_pct)

        structure_data = self.get_indicator('structure')
        key_levels = structure_data.get('key_levels', {}) if structure_data else {}
        targets = []
        
        resistances = sorted([r for r in key_levels.get('resistances', []) if isinstance(r, (int, float))])
        supports = sorted([s for s in key_levels.get('supports', []) if isinstance(s, (int, float))], reverse=True)

        if direction.upper() == 'BUY': targets = [r for r in resistances if r > entry_price][:3]
        elif direction.upper() == 'SELL': targets = [s for s in supports if s < entry_price][:3]
        
        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (total_risk_per_unit * r if direction.upper() == 'BUY' else -total_risk_per_unit * r) for r in reward_ratios]
        
        if not targets: return {}
        
        reward_per_unit = abs(targets[0] - entry_price) - (targets[0] * fees_pct) # Also consider fees on exit
        actual_rr = round(reward_per_unit / total_risk_per_unit, 2) if total_risk_per_unit > 0 else 0
        
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}

