# engines/strategies/base_strategy.py (v2.2 - با فیلتر کندل استیک جهانی)

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseStrategy(ABC):
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        self.analysis = analysis_summary
        self.config = config or {}
        self.htf_analysis = htf_analysis
        self.strategy_name = self.__class__.__name__

        # --- ✨ ارتقای جدید: تعریف لیست الگوهای کندلی کلیدی ---
        self.BULLISH_REVERSAL_PATTERNS = ['HAMMER', 'INVERTEDHAMMER', 'MORNINGSTAR', 'BULLISHENGULFING', 'PIERCING', 'MORNINGDOJISTAR', '3WHITESOLDIERS']
        self.BEARISH_REVERSAL_PATTERNS = ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING', 'DARKCLOUDCOVER', 'EVENINGDOJISTAR', 'HANGINGMAN', '3BLACKCROWS']

    def _get_candlestick_confirmation(self, direction: str) -> Optional[str]:
        """
        یک فیلتر جهانی که بررسی می‌کند آیا یک الگوی کندلی بازگشتی هم‌جهت با سیگنال وجود دارد یا خیر.
        
        Returns:
            نام اولین الگوی تاییدکننده، یا None در صورت عدم وجود.
        """
        patterns_data = self.analysis.get('patterns', {})
        found_patterns = patterns_data.get('patterns', [])
        if not found_patterns:
            return None

        target_patterns = self.BULLISH_REVERSAL_PATTERNS if direction == "BUY" else self.BEARISH_REVERSAL_PATTERNS

        for pattern in found_patterns:
            if pattern.upper() in target_patterns:
                return pattern # اولین الگوی هم‌جهت را برمی‌گردانیم
        
        return None

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        pass

    # ... (متد _calculate_smart_risk_management بدون تغییر باقی می‌ماند)
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
