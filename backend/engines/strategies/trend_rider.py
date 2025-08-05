# engines/strategies/trend_rider.py

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderStrategy(BaseStrategy):
    """
    استراتژی تعقیب روند پیشرفته "Trend Rider".
    این استراتژی با ترکیب سیگنال تغییر روند از SuperTrend و فیلتر قدرت روند از ADX،
    به دنبال شکار شروع روندهای قوی و قابل اعتماد است.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "TrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض و قابل بازنویسی این استراتژی را برمی‌گرداند."""
        return {
            "min_adx_strength": self.config.get("min_adx_strength", 25),
            "atr_multiplier_sl": self.config.get("atr_multiplier_sl", 2.0),
            "reward_tp_ratios": self.config.get("reward_tp_ratios", [1.5, 3.0, 4.5]),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        منطق اصلی استراتژی را برای یافتن سیگنال خرید یا فروش پیاده‌سازی می‌کند.
        """
        # استخراج امن تحلیل‌های مورد نیاز
        supertrend_data = self.analysis.get('supertrend')
        adx_data = self.analysis.get('adx')
        entry_price = self.analysis.get('price_data', {}).get('close')

        if not all([supertrend_data, adx_data, entry_price]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data (SuperTrend, ADX, or Price).")
            return None

        cfg = self._get_signal_config()
        signal_direction = None
        
        # ۱. بررسی ماشه ورود (تغییر روند در SuperTrend)
        if supertrend_data['signal'] == "Bullish Trend Change":
            signal_direction = "BUY"
        elif supertrend_data['signal'] == "Bearish Trend Change":
            signal_direction = "SELL"
        
        if not signal_direction:
            return None # هیچ تغییر روندی رخ نداده است

        # ۲. بررسی فیلتر تایید (قدرت روند ADX)
        if adx_data['adx'] < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal for {signal_direction} ignored. ADX ({adx_data['adx']:.2f}) is below threshold ({cfg['min_adx_strength']}).")
            return None

        # اگر هر دو شرط برقرار باشند، سیگنال معتبر است
        logger.info(f"✨ [{self.strategy_name}] Valid signal found! Direction: {signal_direction}, ADX Strength: {adx_data['adx']:.2f}")

        # ۳. محاسبه مدیریت ریسک
        # در این استراتژی، حد ضرر مستقیماً از خط SuperTrend گرفته می‌شود.
        stop_loss = supertrend_data['value']
        
        # محاسبه اهداف سود با استفاده از متد کمکی کلاس پایه
        risk_params = self._calculate_risk_management(entry_price, signal_direction, stop_loss)

        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            "stop_loss": risk_params.get("stop_loss"),
            "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": {
                "supertrend_signal": supertrend_data['signal'],
                "adx_strength": round(adx_data['adx'], 2)
            }
        }

    def _calculate_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        نسخه بازنویسی شده برای استفاده از حد ضرر دقیق SuperTrend.
        """
        if entry_price == stop_loss: return {}

        risk_amount = abs(entry_price - stop_loss)
        reward_ratios = self._get_signal_config()['reward_tp_ratios']
        
        if direction == 'BUY':
            targets = [entry_price + (risk_amount * r) for r in reward_ratios]
        else: # SELL
            targets = [entry_price - (risk_amount * r) for r in reward_ratios]

        # محاسبه نسبت ریسک به ریوارد واقعی تا اولین هدف
        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)

        return {
            "stop_loss": round(stop_loss, 5),
            "targets": [round(t, 5) for t in targets],
            "risk_reward_ratio": actual_rr
        }

