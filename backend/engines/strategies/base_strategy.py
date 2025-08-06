# engines/strategies/base_strategy.py (v2.1 - MTF Aware)
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseStrategy(ABC):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis = analysis_summary
        self.config = config or {}
        self.htf_analysis = htf_analysis
        self.strategy_name = self.__class__.__name__

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]: pass

    def _calculate_smart_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        if entry_price == stop_loss or stop_loss == 0: return {}
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return {}
        structure_data = self.analysis.get('structure', {}); key_levels = structure_data.get('key_levels', {}); targets = []
        if direction == 'BUY':
            resistances = sorted([r for r in key_levels.get('resistances', []) if r > entry_price]); targets = resistances[:3]
        elif direction == 'SELL':
            supports = sorted([s for s in key_levels.get('supports', []) if s < entry_price], reverse=True); targets = supports[:3]
        if not targets:
            reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
            targets = [entry_price + (risk_amount * r if direction == 'BUY' else -risk_amount * r) for r in reward_ratios]
        if not targets: return {"stop_loss": round(stop_loss, 5), "targets": [], "risk_reward_ratio": 0}
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)
        return {"stop_loss": round(stop_loss, 5), "targets": [round(t, 5) for t in targets], "risk_reward_ratio": actual_rr}
    _calculate_risk_management = _calculate_smart_risk_management
