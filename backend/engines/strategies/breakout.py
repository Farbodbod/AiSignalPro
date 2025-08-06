import logging
from typing import Dict, Any, Optional
import pandas as pd
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class BreakoutStrategy(BaseStrategy):
    """
    یک استراتژی برای شکار شکست‌های قیمتی (Breakouts) که با حجم و انبساط نوسان تایید شده‌اند.
    این استراتژی برای جلوگیری از شکست‌های دروغین، از یک سیستم فیلترینگ چندلایه استفاده می‌کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "BreakoutHunter"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "donchian_period": self.config.get("donchian_period", 20),
            "keltner_ema_period": self.config.get("keltner_ema_period", 20),
            "keltner_atr_multiplier": self.config.get("keltner_atr_multiplier", 2.0),
            "min_volume_spike_factor": self.config.get("min_volume_spike_factor", 2.0), # حجم فعلی باید 2 برابر میانگین باشد
            "volatility_squeeze_period": self.config.get("volatility_squeeze_period", 20) # دوره برای تشخیص فشردگی
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        
        # داده‌های مورد نیاز برای این استراتژی
        donchian_indicator_name = f'donchian_channel_{cfg["donchian_period"]}'
        keltner_upper_col = f'keltner_upper_{cfg["keltner_ema_period"]}_{cfg["keltner_atr_multiplier"]}'
        keltner_lower_col = f'keltner_lower_{cfg["keltner_ema_period"]}_{cfg["keltner_atr_multiplier"]}'
        
        donchian_data = self.analysis.get(donchian_indicator_name)
        keltner_upper = self.analysis.get(keltner_upper_col)
        keltner_lower = self.analysis.get(keltner_lower_col)
        volume_data = self.analysis.get('volume_data') # فرض می‌کنیم دیتافریم اصلی حجم را دارد
        price_data = self.analysis.get('price_data')

        if not all([donchian_data, keltner_upper is not None, keltner_lower is not None, volume_data, price_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        # 2. بررسی سیگنال اولیه از Donchian Channel
        signal_direction = donchian_data.get('signal')
        if signal_direction not in ["BUY", "SELL"]:
            return None

        logger.info(f"[{self.strategy_name}] Initial signal: {signal_direction} from Donchian breakout.")
        
        # --- فیلترهای پیشرفته برای تایید شکست ---

        # 3. فیلتر شماره ۱: تایید حجم (Volume Catalyst)
        volume_series = volume_data['volume_series'] # فرض بر اینکه کل سری حجم در دسترس است
        avg_volume = volume_series.rolling(window=20).mean().iloc[-1]
        current_volume = volume_series.iloc[-1]
        
        if current_volume < (avg_volume * cfg['min_volume_spike_factor']):
            logger.info(f"[{self.strategy_name}] Signal ignored. Volume spike is not significant enough.")
            return None

        # 4. فیلتر شماره ۲: انبساط نوسان (Volatility Explosion)
        keltner_width = keltner_upper['values'] - keltner_lower['values'] # یک سری پانداز از عرض کانال
        avg_keltner_width = keltner_width.rolling(window=cfg['volatility_squeeze_period']).mean().iloc[-1]
        current_keltner_width = keltner_width.iloc[-1]
        
        # چک می‌کنیم که آیا نوسان از حالت فشردگی خارج شده یا خیر
        if current_keltner_width < avg_keltner_width:
             logger.info(f"[{self.strategy_name}] Signal ignored. No volatility expansion detected (still in a squeeze).")
             return None
        
        logger.info(f"✨ [{self.strategy_name}] Breakout signal confirmed by Volume and Volatility expansion!")

        # 5. محاسبه مدیریت ریسک
        entry_price = price_data['close']
        donchian_middle_band = donchian_data.get('values', {}).get('middle_band')
        
        # حد ضرر به صورت داینامیک روی خط میانی کانال دونچیان قرار می‌گیرد
        stop_loss = donchian_middle_band if donchian_middle_band else (entry_price * (1 - 0.02) if signal_direction == "BUY" else entry_price * (1 + 0.02))
        
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # 6. آماده‌سازی خروجی نهایی
        confirmations = {
            "breakout_type": f"Donchian Channel ({cfg['donchian_period']})",
            "volume_confirmation": f"Volume spike factor: {round(current_volume / avg_volume, 2)}x",
            "volatility_confirmation": f"KC Width expanded from avg {round(avg_keltner_width, 5)} to {round(current_keltner_width, 5)}"
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
