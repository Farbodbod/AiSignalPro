import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class MeanReversionStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - VwapReversionPro ✨
    یک استراتژی بازگشت به میانگین تخصصی برای معاملات روزانه که از VWAP Bands
    به عنوان ماشه اصلی و از تایید دوگانه RSI و Williams %R برای فیلتر کردن
    سیگنال‌ها استفاده می‌کند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "VwapReversionPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "vwap_std_dev_multiplier": self.config.get("vwap_std_dev_multiplier", 2.0),
            "rsi_oversold": self.config.get("rsi_oversold", 30),
            "rsi_overbought": self.config.get("rsi_overbought", 70),
            "williams_r_oversold": self.config.get("williams_r_oversold", -80),
            "williams_r_overbought": self.config.get("williams_r_overbought", -20),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.5)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        # نام دینامیک اندیکاتور VWAP
        vwap_indicator_name = f'vwap_bands_{cfg["vwap_std_dev_multiplier"]}'
        
        vwap_data = self.analysis.get(vwap_indicator_name)
        rsi_data = self.analysis.get('rsi')
        williams_r_data = self.analysis.get('williams_r') # اندیکاتور جدید
        price_data = self.analysis.get('price_data')
        atr_data = self.analysis.get('atr')

        if not all([vwap_data, rsi_data, williams_r_data, price_data, atr_data]):
            return None

        # 2. بررسی سیگنال اولیه و فیلترها
        vwap_values = vwap_data.get('values', {})
        lower_band = vwap_values.get('lower_band')
        upper_band = vwap_values.get('upper_band')
        current_price = price_data['close']
        signal_direction = None

        # شرط خرید: قیمت زیر باند پایین VWAP + تایید دوگانه RSI و Williams %R
        is_buy_condition = (
            current_price <= lower_band and
            rsi_data['value'] < cfg['rsi_oversold'] and
            williams_r_data.get('values', {}).get('williams_r', 0) < cfg['williams_r_oversold']
        )

        # شرط فروش: قیمت بالای باند بالای VWAP + تایید دوگانه RSI و Williams %R
        is_sell_condition = (
            current_price >= upper_band and
            rsi_data['value'] > cfg['rsi_overbought'] and
            williams_r_data.get('values', {}).get('williams_r', 0) > cfg['williams_r_overbought']
        )
        
        if is_buy_condition:
            signal_direction = "BUY"
        elif is_sell_condition:
            signal_direction = "SELL"
        
        if not signal_direction:
            return None
        
        logger.info(f"✨ [{self.strategy_name}] Reversion signal for {signal_direction} fully confirmed!")

        # 3. محاسبه مدیریت ریسک
        atr_value = atr_data.get('value')
        # حد ضرر کمی آن طرف‌تر از باند VWAP قرار می‌گیرد
        stop_loss = lower_band - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else upper_band + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(current_price, signal_direction, stop_loss)

        # 4. هدف‌گیری هوشمند: اولین حد سود، خط VWAP است
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'][0] = vwap_line
            # بروزرسانی نسبت ریسک به ریوارد بر اساس هدف جدید
            risk_amount = abs(current_price - stop_loss)
            if risk_amount > 0:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - current_price) / risk_amount, 2)

        # 5. آماده‌سازی خروجی نهایی
        confirmations = {
            "trigger": f"Price at {'Lower' if signal_direction == 'BUY' else 'Upper'} VWAP Band",
            "rsi_value": round(rsi_data['value'], 2),
            "williams_r_value": round(williams_r_data.get('values', {}).get('williams_r', 0), 2),
            "primary_target": "VWAP Line"
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": current_price,
            **risk_params,
            "confirmations": confirmations
        }
