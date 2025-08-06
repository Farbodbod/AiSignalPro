import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VwapReversionStrategy(BaseStrategy):
    """
    یک استراتژی بازگشت به میانگین مخصوص معاملات روزانه که به دنبال بازگشت قیمت
    از باندهای VWAP به سمت خط اصلی VWAP است. این استراتژی با RSI و الگوهای
    کندلی فیلتر می‌شود.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "VwapBouncer"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "vwap_std_dev_multiplier": self.config.get("vwap_std_dev_multiplier", 1.0),
            "rsi_oversold": self.config.get("rsi_oversold", 35),
            "rsi_overbought": self.config.get("rsi_overbought", 65),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.2)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        vwap_indicator_name = f'vwap_bands_{cfg["vwap_std_dev_multiplier"]}'
        
        vwap_data = self.analysis.get(vwap_indicator_name)
        rsi_data = self.analysis.get('rsi')
        price_data = self.analysis.get('price_data')
        atr_data = self.analysis.get('atr')

        if not all([vwap_data, rsi_data, price_data, atr_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        vwap_values = vwap_data.get('values', {})
        lower_band = vwap_values.get('lower_band')
        upper_band = vwap_values.get('upper_band')
        current_price = price_data['close']
        
        potential_direction = None

        # 2. بررسی شرط اول: کشش قیمت به سمت باندها
        if current_price <= lower_band and rsi_data['value'] < cfg['rsi_oversold']:
            potential_direction = "BUY"
        elif current_price >= upper_band and rsi_data['value'] > cfg['rsi_overbought']:
            potential_direction = "SELL"

        if not potential_direction:
            return None
        
        logger.info(f"[{self.strategy_name}] Potential {potential_direction} signal: Price at VWAP band with RSI confirmation.")

        # 3. بررسی شرط نهایی: تایید کندل استیک
        confirming_pattern = self._get_candlestick_confirmation(potential_direction)
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal ignored. No confirming reversal candlestick pattern.")
            return None

        logger.info(f"✨ [{self.strategy_name}] Reversion signal fully confirmed!")

        # 4. محاسبه مدیریت ریسک
        atr_value = atr_data.get('value', current_price * 0.01)
        
        if potential_direction == "BUY":
            stop_loss = price_data['low'] - (atr_value * cfg['atr_sl_multiplier'])
        else: # SELL
            stop_loss = price_data['high'] + (atr_value * cfg['atr_sl_multiplier'])
            
        risk_params = self._calculate_smart_risk_management(current_price, potential_direction, stop_loss)

        # 5. هدف‌گیری هوشمند: اولین حد سود، خط VWAP است
        vwap_line = vwap_values.get('vwap')
        if vwap_line and risk_params.get('targets'):
            risk_params['targets'][0] = vwap_line
            # بروزرسانی نسبت ریسک به ریوارد بر اساس هدف جدید
            risk_amount = abs(current_price - stop_loss)
            if risk_amount > 0:
                risk_params['risk_reward_ratio'] = round(abs(vwap_line - current_price) / risk_amount, 2)

        # 6. آماده‌سازی خروجی نهایی
        confirmations = {
            "trigger": f"Price reached {'Lower' if potential_direction == 'BUY' else 'Upper'} VWAP Band",
            "rsi_confirmation": f"RSI at {round(rsi_data['value'], 2)} ({'Oversold' if potential_direction == 'BUY' else 'Overbought'})",
            "reversal_pattern": confirming_pattern
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": potential_direction,
            "entry_price": current_price,
            **risk_params,
            "confirmations": confirmations
        }
