# engines/strategies/volume_catalyst.py

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystStrategy(BaseStrategy):
    """
    استراتژی "کاتالیزور حجم".
    این استراتژی به دنبال شکست‌های ساختاری (Structural Breakouts) است که
    با یک اسپایک حجمی قابل توجه (فعالیت نهنگ) تایید شده باشند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "VolumeCatalyst"

    def check_signal(self) -> Optional[Dict[str, Any]]:
        structure_data = self.analysis.get('structure')
        whales_data = self.analysis.get('whales')
        price_data = self.analysis.get('price_data')

        if not all([structure_data, whales_data, price_data]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data.")
            return None

        # اطمینان از وجود داده‌های کلیدی
        key_levels = structure_data.get('key_levels', {})
        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])
        current_price = price_data['close']
        prev_price = self.analysis.get('price_data_prev', {}).get('close') # نیاز به داده کندل قبل

        if prev_price is None:
            # این حالت زمانی رخ می‌دهد که دیتافریم فقط یک ردیف دارد.
            # ما برای تشخیص شکست، حداقل به دو ردیف نیاز داریم.
            # در یک سیستم واقعی، باید دیتافریم کندل‌های قبلی را نیز در دسترس داشته باشیم.
            # فعلا این بخش را ساده نگه می‌داریم و فرض می‌کنیم این داده موجود است.
            # در آینده می‌توانیم `IndicatorAnalyzer` را برای ارائه این داده ارتقا دهیم.
            # در حال حاضر، اگر داده کندل قبل موجود نباشد، استراتژی را اجرا نمی‌کنیم.
            return None

        signal_direction = None
        broken_level = None

        # ۱. بررسی شکست مقاومت (Breakout)
        if resistances:
            nearest_resistance = resistances[0]
            if current_price > nearest_resistance and prev_price < nearest_resistance:
                # تایید با حجم
                if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Buying Pressure':
                    signal_direction = "BUY"
                    broken_level = nearest_resistance

        # ۲. بررسی شکست حمایت (Breakdown)
        if not signal_direction and supports:
            nearest_support = supports[0]
            if current_price < nearest_support and prev_price > nearest_support:
                # تایید با حجم
                if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Selling Pressure':
                    signal_direction = "SELL"
                    broken_level = nearest_support

        if not signal_direction:
            return None
            
        logger.info(f"✨ [{self.strategy_name}] Valid signal! {signal_direction} Breakout confirmed by Whale Activity.")

        # ۳. محاسبه مدیریت ریسک
        # حد ضرر را در سمت دیگر سطح شکست‌خورده قرار می‌دهیم
        atr_val = self.analysis.get('atr', {}).get('value', current_price * 0.015)
        
        stop_loss = broken_level - atr_val if signal_direction == "BUY" else broken_level + atr_val
        risk_params = self._calculate_risk_management(current_price, signal_direction, stop_loss)

        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": current_price,
            "stop_loss": risk_params.get("stop_loss"),
            "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": {
                "broken_level": broken_level,
                "volume_spike_factor": whales_data['spike_factor']
            }
        }
