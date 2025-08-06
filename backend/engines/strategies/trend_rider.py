import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class TrendRiderStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - TrendRiderPro ✨
    یک استراتژی روندساز پیشرفته که از SuperTrend یا EMA Cross برای ورود استفاده کرده،
    با ADX و DEMA/TEMA فیلتر شده و با Chandelier Exit مدیریت می‌شود.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "TrendRiderPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "entry_trigger_type": self.config.get("entry_trigger_type", "supertrend"), # 'supertrend' or 'ema_cross'
            # EMA Cross Params
            "ema_short_period": self.config.get("ema_short_period", 9),
            "ema_long_period": self.config.get("ema_long_period", 21),
            # SuperTrend Params
            "supertrend_atr_period": self.config.get("supertrend_atr_period", 10),
            "supertrend_multiplier": self.config.get("supertrend_multiplier", 3.0),
            # Chandelier Exit (Stop Loss) Params
            "chandelier_atr_period": self.config.get("chandelier_atr_period", 22),
            "chandelier_atr_multiplier": self.config.get("chandelier_atr_multiplier", 3.0),
            # Filter Params
            "min_adx_strength": self.config.get("min_adx_strength", 25),
            "trend_filter_ma_period": self.config.get("trend_filter_ma_period", 50) # DEMA/TEMA period
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        price_data = self.analysis.get('price_data')
        adx_data = self.analysis.get('adx')
        chandelier_indicator_name = f'chandelier_exit_{cfg["chandelier_atr_period"]}_{cfg["chandelier_atr_multiplier"]}'
        chandelier_data = self.analysis.get(chandelier_indicator_name)
        
        if not all([price_data, adx_data, chandelier_data]):
            return None

        # 2. بررسی سیگنال ورود بر اساس کانفیگ
        signal_direction = None
        entry_trigger_name = ""
        
        if cfg['entry_trigger_type'] == 'ema_cross':
            entry_trigger_name = f"EMA Cross ({cfg['ema_short_period']}/{cfg['ema_long_period']})"
            ema_cross_signal = self.analysis.get(f"signal_ema_cross_{cfg['ema_short_period']}_{cfg['ema_long_period']}")
            if ema_cross_signal == 1: signal_direction = "BUY"
            elif ema_cross_signal == -1: signal_direction = "SELL"
        else: # Default to supertrend
            entry_trigger_name = f"SuperTrend ({cfg['supertrend_atr_period']},{cfg['supertrend_multiplier']})"
            st_indicator_name = f"supertrend_{cfg['supertrend_atr_period']}_{cfg['supertrend_multiplier']}"
            supertrend_data = self.analysis.get(st_indicator_name)
            if supertrend_data and supertrend_data.get('signal') == "Bullish Trend Change": signal_direction = "BUY"
            elif supertrend_data and supertrend_data.get('signal') == "Bearish Trend Change": signal_direction = "SELL"

        if not signal_direction:
            return None
            
        # 3. اعمال فیلترهای پیشرفته
        # فیلتر قدرت روند ADX
        if adx_data['adx'] < cfg['min_adx_strength']:
            return None

        # فیلتر تایید روند با DEMA/TEMA (فرض می‌کنیم تحلیلگر FastMA با این پریود اجرا شده)
        ma_filter_name = f'dema_{cfg["trend_filter_ma_period"]}' # میتوان TEMA هم باشد
        ma_filter_data = self.analysis.get(ma_filter_name)
        if ma_filter_data:
            ma_value = ma_filter_data.get('values', {}).get(f'dema_{cfg["trend_filter_ma_period"]}')
            if ma_value:
                if signal_direction == "BUY" and price_data['close'] < ma_value: return None
                if signal_direction == "SELL" and price_data['close'] > ma_value: return None
        
        # فیلتر تایید تایم فریم بالاتر (HTF)
        # (منطق HTF از نسخه قبلی شما می‌تواند در اینجا نیز اضافه شود)

        logger.info(f"✨ [{self.strategy_name}] Signal for {signal_direction} confirmed by filters.")

        # 4. محاسبه مدیریت ریسک با Chandelier Exit
        entry_price = price_data['close']
        chandelier_values = chandelier_data.get('values', {})
        stop_loss = chandelier_values.get('long_stop') if signal_direction == "BUY" else chandelier_values.get('short_stop')

        if not stop_loss: return None
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # 5. آماده‌سازی خروجی نهایی
        confirmations = {
            "entry_trigger": entry_trigger_name,
            "strength_filter": f"ADX > {cfg['min_adx_strength']} (Value: {round(adx_data['adx'], 2)})",
            "exit_management": f"Chandelier Stop at {stop_loss}"
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
