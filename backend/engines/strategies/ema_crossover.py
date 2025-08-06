import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class EmaCrossoverStrategy(BaseStrategy):
    """
    یک استراتژی روند مبتنی بر تقاطع EMAها، که با فیلترهای پیشرفته برای
    افزایش دقت، تقویت شده است.
    1. سیگنال اولیه: تقاطع دو EMA.
    2. فیلتر قدرت روند: ADX باید قدرت کافی را نشان دهد.
    3. فیلتر روند اصلی: سیگنال باید هم‌جهت با روند در تایم‌فریم بالاتر باشد.
    4. فیلتر تایید نهایی: یک الگوی کندل استیک بازگشتی باید سیگنال را تایید کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "EmaCrossoverPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "short_period": self.config.get("ema_short_period", 9),
            "long_period": self.config.get("ema_long_period", 21),
            "min_adx_strength": self.config.get("min_adx_strength", 25),
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 2.0),
            "htf_trend_ma_type": self.config.get("htf_trend_ma_type", "ema_200") # نام کلید در htf_analysis
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها و کانفیگ
        cfg = self._get_signal_config()
        ema_cross_indicator_name = f"signal_ema_cross_{cfg['short_period']}_{cfg['long_period']}"
        
        ema_signal_data = self.analysis.get(ema_cross_indicator_name)
        adx_data = self.analysis.get('adx')
        atr_data = self.analysis.get('atr')
        price_data = self.analysis.get('price_data')

        if not all([ema_signal_data is not None, adx_data, atr_data, price_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        # 2. بررسی سیگنال اولیه از EMA Cross
        signal_direction = None
        if ema_signal_data == 1:
            signal_direction = "BUY"
        elif ema_signal_data == -1:
            signal_direction = "SELL"
        
        if not signal_direction:
            return None
        
        logger.info(f"[{self.strategy_name}] Initial signal: {signal_direction} from EMA cross.")
        
        # --- اینجا معجزه شروع می‌شود: فیلترهای چندلایه ---

        # 3. فیلتر شماره ۱: قدرت روند (ADX)
        if adx_data['adx'] < cfg['min_adx_strength']:
            logger.info(f"[{self.strategy_name}] Signal ignored. ADX ({adx_data['adx']:.2f}) is below threshold ({cfg['min_adx_strength']}).")
            return None

        # 4. فیلتر شماره ۲: تایید تایم‌فریم بالاتر (HTF)
        htf_trend_aligned = False
        if self.htf_analysis:
            htf_price = self.htf_analysis.get('price_data', {}).get('close')
            htf_trend_ma_value = self.htf_analysis.get(cfg['htf_trend_ma_type'], {}).get('value')
            
            if htf_price is not None and htf_trend_ma_value is not None:
                if signal_direction == "BUY" and htf_price > htf_trend_ma_value:
                    htf_trend_aligned = True
                elif signal_direction == "SELL" and htf_price < htf_trend_ma_value:
                    htf_trend_aligned = True

        if not htf_trend_aligned:
            logger.info(f"[{self.strategy_name}] Signal ignored. Not aligned with HTF trend.")
            return None

        # 5. فیلتر شماره ۳: تایید کندل استیک
        confirming_pattern = self._get_candlestick_confirmation(signal_direction)
        if not confirming_pattern:
            logger.info(f"[{self.strategy_name}] Signal ignored. No confirming candlestick pattern found.")
            return None
        
        logger.info(f"✨ [{self.strategy_name}] Signal confirmed by all filters!")

        # 6. محاسبه مدیریت ریسک
        entry_price = price_data['close']
        long_ema_col = f'long_ema_{cfg["long_period"]}'
        long_ema_value = self.analysis.get(long_ema_col)
        atr_value = atr_data.get('value', entry_price * 0.01) # Fallback
        
        stop_loss = 0
        if long_ema_value:
            if signal_direction == "BUY":
                stop_loss = long_ema_value - (atr_value * cfg['atr_sl_multiplier'])
            else: # SELL
                stop_loss = long_ema_value + (atr_value * cfg['atr_sl_multiplier'])
        
        if stop_loss == 0: # Fallback if long_ema is somehow missing
            if signal_direction == "BUY": stop_loss = entry_price - (atr_value * 2)
            else: stop_loss = entry_price + (atr_value * 2)
            
        risk_params = self._calculate_smart_risk_management(entry_price, signal_direction, stop_loss)

        # 7. آماده‌سازی خروجی نهایی
        confirmations = {
            "ema_cross": f"{cfg['short_period']}/{cfg['long_period']}",
            "adx_strength": round(adx_data['adx'], 2),
            "htf_confirmation": "Aligned",
            "candlestick_pattern": confirming_pattern
        }
        
        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            **risk_params,
            "confirmations": confirmations
        }
