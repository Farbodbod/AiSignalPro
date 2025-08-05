# engines/strategies/ichimoku_pro.py

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class IchimokuProStrategy(BaseStrategy):
    """
    استراتژی پیشرفته "ایچیموکو پرو".
    این استراتژی از یک سیستم امتیازدهی جامع برای ارزیابی قدرت سیگنال‌های معاملاتی
    بر اساس تمام اجزای سیستم ایچیموکو استفاده می‌کند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "IchimokuPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض و قابل بازنویسی این استراتژی."""
        return {
            "min_score_to_signal": self.config.get("min_score_to_signal", 5),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        ichimoku_data = self.analysis.get('ichimoku')
        price_data = self.analysis.get('price_data')

        if not all([ichimoku_data, price_data]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data.")
            return None

        cfg = self._get_signal_config()
        buy_score = 0
        sell_score = 0
        confirmations = []

        # استخراج داده‌ها برای خوانایی بهتر
        price_pos = ichimoku_data.get('price_position')
        tk_cross = ichimoku_data.get('signal', 'Neutral')
        chikou_confirm = ichimoku_data.get('chikou_confirmation')
        price = price_data.get('close')
        kijun = ichimoku_data.get('kijun_sen')
        senkou_a = ichimoku_data.get('senkou_span_a')
        senkou_b = ichimoku_data.get('senkou_span_b')

        # ۱. امتیازدهی بر اساس شکست ابر (Kumo Breakout)
        if price_pos == "Above Kumo":
            buy_score += 3
            confirmations.append("Above Kumo")
        elif price_pos == "Below Kumo":
            sell_score += 3
            confirmations.append("Below Kumo")

        # ۲. امتیازدهی بر اساس کراس تنکان/کیجون (TK Cross)
        if "Bullish" in tk_cross:
            buy_score += 2
            confirmations.append(tk_cross)
        elif "Bearish" in tk_cross:
            sell_score += 2
            confirmations.append(tk_cross)

        # ۳. امتیازدهی بر اساس تایید چیکو اسپن
        if chikou_confirm == "Bullish Confirmation":
            buy_score += 1
            confirmations.append(chikou_confirm)
        elif chikou_confirm == "Bearish Confirmation":
            sell_score += 1
            confirmations.append(chikou_confirm)

        # ۴. امتیازدهی بر اساس موقعیت قیمت نسبت به کیجون
        if price > kijun:
            buy_score += 1
            confirmations.append("Price above Kijun")
        elif price < kijun:
            sell_score += 1
            confirmations.append("Price below Kijun")
        
        # ۵. امتیازدهی بر اساس رنگ ابر آینده
        if senkou_a > senkou_b:
            buy_score += 1
            confirmations.append("Future Kumo is Bullish")
        elif senkou_a < senkou_b:
            sell_score += 1
            confirmations.append("Future Kumo is Bearish")

        signal_direction = None
        # بررسی امتیاز نهایی برای سیگنال خرید
        if buy_score >= cfg['min_score_to_signal']:
            signal_direction = "BUY"
        # بررسی امتیاز نهایی برای سیگنال فروش
        elif sell_score >= cfg['min_score_to_signal']:
            signal_direction = "SELL"
        
        if not signal_direction:
            return None

        logger.info(f"✨ [{self.strategy_name}] Valid signal! {signal_direction} with score {max(buy_score, sell_score)}")
        
        # مدیریت ریسک: حد ضرر در سمت دیگر کیجون سن قرار می‌گیرد
        atr_val = self.analysis.get('atr', {}).get('value', price * 0.015)
        stop_loss = kijun - atr_val if signal_direction == "BUY" else kijun + atr_val
        risk_params = self._calculate_risk_management(price, signal_direction, stop_loss)

        return {
            "strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": price,
            "stop_loss": risk_params.get("stop_loss"), "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": confirmations
        }
