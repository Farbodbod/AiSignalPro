import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class VolumeCatalystStrategy(BaseStrategy):
    """
    ✨ UPGRADE v3.0 - VolumeCatalystPro ✨
    یک استراتژی شکست پیشرفته که شکست سطوح کلیدی را با یک کاتالیزور حجمی
    شناسایی کرده و آن را با مومنتوم CCI و انبساط نوسان Keltner Channel
    تایید می‌کند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "VolumeCatalystPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "cci_threshold": self.config.get("cci_threshold", 100),
            "keltner_ema_period": self.config.get("keltner_ema_period", 20),
            "keltner_atr_multiplier": self.config.get("keltner_atr_multiplier", 2.0),
            "volatility_squeeze_period": self.config.get("volatility_squeeze_period", 20)
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها
        cfg = self._get_signal_config()
        structure_data = self.analysis.get('structure'); whales_data = self.analysis.get('whales'); cci_data = self.analysis.get('cci'); price_data = self.analysis.get('price_data')
        
        keltner_upper_col = f"keltner_upper_{cfg['keltner_ema_period']}_{cfg['keltner_atr_multiplier']}"
        keltner_lower_col = f"keltner_lower_{cfg['keltner_ema_period']}_{cfg['keltner_atr_multiplier']}"
        keltner_middle_col = f"keltner_middle_{cfg['keltner_ema_period']}"
        
        keltner_upper = self.analysis.get(keltner_upper_col); keltner_lower = self.analysis.get(keltner_lower_col); keltner_middle = self.analysis.get(keltner_middle_col)

        if not all([structure_data, whales_data, cci_data, price_data, keltner_upper, keltner_lower, keltner_middle]):
            return None

        # 2. بررسی سیگنال اولیه: شکست سطح با حجم بالا
        key_levels = structure_data.get('key_levels', {}); supports = key_levels.get('supports', []); resistances = key_levels.get('resistances', []); current_price = price_data['close']; prev_price = self.analysis.get('price_data_prev', {}).get('close');
        if prev_price is None: return None
        
        signal_direction, broken_level = None, None
        
        if resistances and current_price > resistances[0] and prev_price < resistances[0]:
            if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Buying Pressure':
                signal_direction, broken_level = "BUY", resistances[0]
        
        if not signal_direction and supports and current_price < supports[0] and prev_price > supports[0]:
            if whales_data['status'] == 'Whale Activity Detected' and whales_data['pressure'] == 'Selling Pressure':
                signal_direction, broken_level = "SELL", supports[0]
        
        if not signal_direction: return None
        
        # 3. فیلترهای پیشرفته
        # فیلتر مومنتوم CCI
        if signal_direction == "BUY" and cci_data['value'] < cfg['cci_threshold']: return None
        if signal_direction == "SELL" and cci_data['value'] > -cfg['cci_threshold']: return None

        # فیلتر انبساط نوسان Keltner Channel
        keltner_width = keltner_upper['values'] - keltner_lower['values']
        avg_keltner_width = keltner_width.rolling(window=cfg['volatility_squeeze_period']).mean().iloc[-1]
        if keltner_width.iloc[-1] < avg_keltner_width: return None

        logger.info(f"✨ [{self.strategy_name}] Volume Breakout signal for {signal_direction} fully confirmed!")

        # 4. محاسبه مدیریت ریسک
        # حد ضرر، خط میانی کانال کلتنر است
        stop_loss = keltner_middle['values'].iloc[-1]
        risk_params = self._calculate_smart_risk_management(current_price, signal_direction, stop_loss)

        # 5. آماده‌سازی خروجی نهایی
        confirmations = {
            "trigger": f"Volume-backed break of level {broken_level}",
            "momentum_confirmation": f"CCI at {round(cci_data['value'], 2)}",
            "volatility_confirmation": "Keltner Channel expanding",
            "volume_spike_factor": whales_data['spike_factor']
        }
        
        return {"strategy_name": self.strategy_name, "direction": signal_direction, "entry_price": current_price, **risk_params, "confirmations": confirmations}
