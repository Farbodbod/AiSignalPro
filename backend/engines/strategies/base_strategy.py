# engines/strategies/base_strategy.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseStrategy(ABC):
    """
    کلاس پایه انتزاعی (Abstract Base Class) برای تمام استراتژی‌های معاملاتی.

    این کلاس یک "قرارداد" استاندارد برای تمام موتورهای استراتژی تعریف می‌کند.
    هر استراتژی باید بتواند:
    1. تحلیل‌های جامع را از IndicatorAnalyzer دریافت کند.
    2. بر اساس قوانین داخلی خود، یک سیگنال معاملاتی (BUY, SELL) تولید کند.
    3. در صورت تولید سیگنال، جزئیات کامل آن (نقطه ورود، حد ضرر، اهداف) را ارائه دهد.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        """
        سازنده کلاس.

        Args:
            analysis_summary (Dict[str, Any]): خروجی کامل و تحلیل‌شده از متد get_analysis_summary()
                                               در کلاس IndicatorAnalyzer.
            config (Dict[str, Any], optional): تنظیمات خاص مربوط به این استراتژی.
        """
        self.analysis = analysis_summary
        self.config = config or {}
        self.strategy_name = self.__class__.__name__

    @abstractmethod
    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        متد اصلی که منطق استراتژی را پیاده‌سازی می‌کند.

        این متد باید دیکشنری self.analysis را بررسی کرده و بر اساس قوانین
        استراتژی، تصمیم به تولید سیگنال بگیرد.

        Returns:
            Optional[Dict[str, Any]]: 
                - اگر سیگنالی پیدا شود، یک دیکشنری حاوی تمام جزئیات معامله را برمی‌گرداند.
                - اگر هیچ سیگنالی مطابق با قوانین استراتژی پیدا نشود، None را برمی‌گرداند.
        """
        pass

    def _calculate_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        یک متد کمکی برای محاسبه حد ضرر و اهداف بر اساس مدیریت ریسک.
        این متد به صورت پیش‌فرض از نسبت‌های ریسک به ریوارد استاندارد استفاده می‌کند.
        """
        if entry_price == stop_loss or stop_loss == 0:
            return {}

        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0:
            return {}
        
        # استفاده از نسبت‌های ریسک به ریوارد تعریف شده در کانفیگ یا مقادیر پیش‌فرض
        reward_ratios = self.config.get('reward_tp_ratios', [1.5, 3.0, 5.0])
        
        if direction == 'BUY':
            targets = [entry_price + (risk_amount * r) for r in reward_ratios]
        elif direction == 'SELL':
            targets = [entry_price - (risk_amount * r) for r in reward_ratios]
        else:
            return {}

        # محاسبه نسبت ریسک به ریوارد واقعی تا اولین هدف
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)

        return {
            "stop_loss": round(stop_loss, 5),
            "targets": [round(t, 5) for t in targets],
            "risk_reward_ratio": actual_rr
        }
