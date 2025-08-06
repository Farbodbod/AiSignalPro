import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class KeltnerBreakoutStrategy(BaseStrategy):
    """
    یک استراتژی شکست مبتنی بر کانال کلتنر که با ADX (برای قدرت روند)
    و CCI (برای مومنتوم) فیلتر می‌شود تا سیگنال‌های با احتمال موفقیت بالا را شناسایی کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "KeltnerMomentumBreakout"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "keltner_ema_period": self.config.get("keltner_ema_period", 20),
            "keltner_atr_period": self.config.get("keltner_atr_period", 10),
            "keltner_atr_multiplier": self.config.get("keltner_atr_multiplier", 2.0),
            "min_adx_strength": self.config.get("min_adx_strength", 25),
            "cci_threshold": self.config.get("cci_threshold", 100)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        keltner_indicator_name = f'keltner_channel_{cfg["keltner_ema_period"]}_{cfg["keltner_atr_multiplier"]}'
        
        keltner_data = self.analysis.get(keltner_indicator_name)
        adx_data = self.analysis.get('adx')
        cci_data = self.analysis.get('cci')
        price_data = self.analysis.get('price_data')

        if not all([keltner_data, adx_data, cci_data, price_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        keltner_values = keltner_data.get('values', {})
        upper_band = keltner_values.get('upper_band')
        lower_band = keltner_values.get('lower_band')
        current_price = price_data['close']
        
        potential_direction = None

        # 2. بررسی سیگنال اولیه: شکست کانال کلتنر
        if current_price > upper_band:
            potential_direction = "BUY"
        elif current_price < lower_band:
            potential_direction = "SELL"

        if not potential_direction:
            return None
        
        logger.info(f"[{self.strategy_name}] Initial Breakout Signal: {potential_direction} from Keltner Channel.")
        
        # --- فیلترهای پیشرفته ---

        # 3. فیلتر قدرت روند (ADX)
        if adx_data['adx'] < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal ignored. ADX ({adx_data['adx']:.2f}) is below strength threshold.")
            return None

        # 4. فیلتر مومنتوم (CCI)
        cci_value = cci_data.get('value')
        if potential_direction == "BUY" and cci_value < cfg['cci_threshold']:
            logger.info(f"[{self.strategy_name}] Signal ignored. CCI ({cci_value:.2f}) has not confirmed bullish momentum.")
            return None
        if potential_direction == "SELL" and cci_value > -cfg['cci_threshold']:
            logger.info(f"[{self.strategy_name}] Signal ignored. CCI ({cci_value:.2f}) has not confirmed bearish momentum.")
            return None

        # 5. فیلتر نهایی: تایید کندل استیک
        confirming_pattern = self._get_candlestick_confirmation(potential_direction)
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal ignored. No confirming candlestick pattern.")
            return None

        logger.info(f"✨ [{self.strategy_name}] Breakout signal fully confirmed by ADX, CCI, and Candlestick!")

        # 6. محاسبه مدیریت ریسک
        # حد ضرر، خط میانی کانال کلتنر است که یک حمایت/مقاومت داینامیک کلیدی است
        middle_band = keltner_values.get('middle_band')
        if not middle_band: return None # اگر خط میانی موجود نباشد، سیگنال را لغو کن
        
        stop_loss = middle_band
        risk_params = self._calculate_smart_risk_management(current_price, potential_direction, stop_loss)

        # 7. آماده‌سازی خروجی نهایی
        confirmations = {
            "breakout_trigger": "Keltner Channel Break",
            "trend_strength": f"ADX at {round(adx_data['adx'], 2)}",
            "momentum_confirmation": f"CCI at {round(cci_value, 2)}",
            "candlestick_pattern": confirming_pattern
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": potential_direction,
            "entry_price": current_price,
            **risk_params,
            "confirmations": confirmations
        }
