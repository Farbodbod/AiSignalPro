import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - DivergenceSniperPro ✨
    یک استراتژی تک‌تیرانداز که واگرایی‌های قوی را شناسایی کرده و آن‌ها را با
    پیوت‌های ساختاری ZigZag و یک ماشه ورود مبتنی بر مومنتوم (Williams %R) تایید می‌کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "DivergenceSniperPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "zigzag_deviation": self.config.get("zigzag_deviation", 5.0),
            "williams_r_oversold_exit": self.config.get("williams_r_oversold_exit", -80),
            "williams_r_overbought_exit": self.config.get("williams_r_overbought_exit", -20),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.0)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        divergence_data = self.analysis.get('divergence')
        zigzag_data = self.analysis.get(f'zigzag_{cfg["zigzag_deviation"]}')
        williams_r_data = self.analysis.get('williams_r')
        price_data = self.analysis.get('price_data')
        atr_data = self.analysis.get('atr')

        if not all([divergence_data, zigzag_data, williams_r_data, price_data, atr_data]):
            return None

        # 2. بررسی سیگنال اولیه: واگرایی قوی
        if divergence_data.get('strength') != "Strong":
            return None

        signal_direction = "BUY" if divergence_data['type'] == "Bullish" else "SELL"
        
        # 3. فیلتر شماره ۱: تایید ساختاری با ZigZag
        last_pivot = zigzag_data.get('values', {})
        if not last_pivot: return None
        
        # آیا نوع واگرایی با نوع آخرین پیوت ZigZag مطابقت دارد؟
        is_bullish_match = signal_direction == "BUY" and last_pivot.get('last_pivot_type') == 'trough'
        is_bearish_match = signal_direction == "SELL" and last_pivot.get('last_pivot_type') == 'peak'
        
        if not (is_bullish_match or is_bearish_match):
            logger.info(f"[{self.strategy_name}] Divergence found, but not confirmed by a ZigZag pivot.")
            return None

        # 4. فیلتر شماره ۲: ماشه ورود با Williams %R (خروج از ناحیه اشباع)
        # این منطق در اندیکاتور Williams %R پیاده‌سازی شده، ما فقط سیگنال آن را چک می‌کنیم
        if williams_r_data.get('signal') != signal_direction.lower():
            logger.info(f"[{self.strategy_name}] Divergence & Pivot confirmed, but waiting for Williams %R momentum trigger.")
            return None

        # تایید نهایی با کندل استیک (اختیاری اما مفید)
        confirming_pattern = self._get_candlestick_confirmation(signal_direction)
        if not confirming_pattern:
             return None

        logger.info(f"✨ [{self.strategy_name}] Divergence signal fully confirmed by ZigZag, Williams %R, and Candlestick!")
        
        # 5. محاسبه مدیریت ریسک دقیق
        entry_price = price_data['close']
        atr_value = atr_data.get('value')
        
        # حد ضرر بر اساس قیمت پیوت ZigZag
        pivot_price = last_pivot.get('last_pivot_price')
        stop_loss = pivot_price - (atr_value * cfg['atr_sl_multiplier']) if signal_direction == "BUY" else pivot_price + (atr_value * cfg['atr_sl_multiplier'])
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # 6. آماده‌سازی خروجی نهایی
        confirmations = {
            "divergence": f"Strong {divergence_data['type']}",
            "structure_confirmation": f"Confirmed at ZigZag {last_pivot.get('last_pivot_type')} at {pivot_price}",
            "momentum_trigger": f"Williams %R crossed out of {'oversold' if signal_direction == 'BUY' else 'overbought'} zone",
            "candlestick_pattern": confirming_pattern
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
