import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeReversalStrategy(BaseStrategy):
    """
    یک استراتژی بازگشتی که به دنبال جهش‌های حجمی (فعالیت نهنگ‌ها)
    در سطوح کلیدی حمایت و مقاومت می‌گردد و با یک الگوی کندلی
    بازگشتی، سیگنال ورود را تایید می‌کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "WhaleReversal"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "proximity_percent": self.config.get("proximity_percent", 0.005),  # 0.5% فاصله از سطح
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.5)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        structure_data = self.analysis.get('structure')
        whales_data = self.analysis.get('whales')
        price_data = self.analysis.get('price_data')
        atr_data = self.analysis.get('atr')

        if not all([structure_data, whales_data, price_data, atr_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        key_levels = structure_data.get('key_levels', {})
        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])
        current_low = price_data['low']
        current_high = price_data['high']
        
        tested_level = None
        potential_direction = None

        # 2. بررسی مکان: آیا قیمت در حال تست یک سطح کلیدی است؟
        # تست سطوح حمایت
        for level in supports:
            if abs(current_low - level) / level < cfg['proximity_percent']:
                tested_level = level
                potential_direction = "BUY"
                break
        
        # تست سطوح مقاومت
        if not tested_level:
            for level in resistances:
                if abs(current_high - level) / level < cfg['proximity_percent']:
                    tested_level = level
                    potential_direction = "SELL"
                    break
        
        if not tested_level:
            return None # قیمت در هیچ ناحیه حساسی نیست

        logger.info(f"[{self.strategy_name}] Price is testing a key level: {tested_level} for a potential {potential_direction} signal.")

        # 3. بررسی بازیگر اصلی: آیا فعالیت نهنگ‌ها شناسایی شده؟
        if whales_data.get('status') != 'Whale Activity Detected':
            logger.info(f"[{self.strategy_name}] Signal ignored. No whale activity detected at the key level.")
            return None

        # 4. بررسی اقدام نهایی: آیا الگوی کندلی بازگشتی وجود دارد؟
        confirming_pattern = self._get_candlestick_confirmation(potential_direction)
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal ignored. No confirming reversal candlestick pattern.")
            return None

        logger.info(f"✨ [{self.strategy_name}] Reversal signal confirmed by Level, Volume, and Candlestick!")

        # 5. محاسبه مدیریت ریسک
        entry_price = price_data['close']
        atr_value = atr_data.get('value', entry_price * 0.01)
        
        # حد ضرر دقیقا در آن سوی سطح کلیدی قرار می‌گیرد
        if potential_direction == "BUY":
            stop_loss = tested_level - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = tested_level + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(entry_price, potential_direction, stop_loss)

        # 6. آماده‌سازی خروجی نهایی
        confirmations = {
            "tested_level": f"{'Support' if potential_direction == 'BUY' else 'Resistance'} at {tested_level}",
            "volume_trigger": f"Whale Activity ({whales_data.get('pressure', 'N/A')})",
            "reversal_pattern": confirming_pattern
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": potential_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
