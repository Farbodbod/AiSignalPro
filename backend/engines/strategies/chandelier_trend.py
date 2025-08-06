import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class ChandelierTrendStrategy(BaseStrategy):
    """
    یک استراتژی پیرو روند که از SuperTrend برای ورود و از Chandelier Exit
    به عنوان یک حد ضرر متحرک و هوشمند استفاده می‌کند.
    این استراتژی با ADX برای سنجش قدرت روند فیلتر می‌شود.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "ChandelierTrendRider"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "chandelier_atr_period": self.config.get("chandelier_atr_period", 22),
            "chandelier_atr_multiplier": self.config.get("chandelier_atr_multiplier", 3.0),
            "supertrend_atr_period": self.config.get("supertrend_atr_period", 10),
            "supertrend_multiplier": self.config.get("supertrend_multiplier", 3.0),
            "min_adx_strength": self.config.get("min_adx_strength", 25)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        # نام دینامیک اندیکاتورها بر اساس کانفیگ
        chandelier_indicator_name = f'chandelier_exit_{cfg["chandelier_atr_period"]}_{cfg["chandelier_atr_multiplier"]}'
        supertrend_indicator_name = f'supertrend_{cfg["supertrend_atr_period"]}_{cfg["supertrend_multiplier"]}'

        supertrend_data = self.analysis.get(supertrend_indicator_name)
        chandelier_data = self.analysis.get(chandelier_indicator_name)
        adx_data = self.analysis.get('adx')
        price_data = self.analysis.get('price_data')

        if not all([supertrend_data, chandelier_data, adx_data, price_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        # 2. بررسی سیگنال ورود از SuperTrend
        signal_direction = None
        if supertrend_data.get('signal') == "Bullish Trend Change":
            signal_direction = "BUY"
        elif supertrend_data.get('signal') == "Bearish Trend Change":
            signal_direction = "SELL"
        
        if not signal_direction:
            return None
        
        logger.info(f"[{self.strategy_name}] Initial Entry Signal: {signal_direction} from SuperTrend.")
        
        # 3. فیلتر شماره ۱: قدرت روند (ADX)
        if adx_data['adx'] < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal ignored. ADX ({adx_data['adx']:.2f}) is below trend strength threshold ({cfg['min_adx_strength']}).")
            return None

        # میتوان فیلتر HTF را نیز مانند استراتژی قبلی در اینجا اضافه کرد
        
        logger.info(f"✨ [{self.strategy_name}] Trend signal confirmed by ADX!")

        # 4. محاسبه مدیریت ریسک با استفاده از Chandelier Exit
        entry_price = price_data['close']
        
        # حد ضرر، نقطه خروج چلچراغی است. این کلیدی‌ترین بخش استراتژی است.
        stop_loss = None
        chandelier_values = chandelier_data.get('values', {})
        if signal_direction == "BUY":
            stop_loss = chandelier_values.get('long_stop')
        else: # SELL
            stop_loss = chandelier_values.get('short_stop')
        
        if not stop_loss:
            logger.warning(f"[{self.strategy_name}] Could not determine Chandelier stop loss. Aborting.")
            return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # 5. آماده‌سازی خروجی نهایی
        confirmations = {
            "entry_trigger": f"SuperTrend ({cfg['supertrend_atr_period']},{cfg['supertrend_multiplier']})",
            "strength_filter": f"ADX > {cfg['min_adx_strength']} (Value: {round(adx_data['adx'], 2)})",
            "exit_management": f"Chandelier Stop Loss ({cfg['chandelier_atr_period']},{cfg['chandelier_atr_multiplier']})"
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
