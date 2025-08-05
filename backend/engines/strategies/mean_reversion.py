# engines/strategies/mean_reversion.py

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class MeanReversionStrategy(BaseStrategy):
    """
    استراتژی پیشرفته "Mean Reversion Pro".
    این استراتژی به دنبال شناسایی نقاط بازگشتی بازار است که در آن قیمت بیش از حد
    از میانگین خود فاصله گرفته و احتمال بازگشت آن بالاست.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "MeanReversionPro"

    def _get_signal_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض و قابل بازنویسی این استراتژی را برمی‌گرداند."""
        return {
            "rsi_oversold": self.config.get("rsi_oversold", 30),
            "rsi_overbought": self.config.get("rsi_overbought", 70),
            "bb_buy_threshold": self.config.get("bb_buy_threshold", 0), # قیمت زیر باند پایین
            "bb_sell_threshold": self.config.get("bb_sell_threshold", 1), # قیمت بالای باند بالا
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        منطق اصلی استراتژی را برای یافتن سیگنال بازگشتی پیاده‌سازی می‌کند.
        """
        bollinger_data = self.analysis.get('bollinger')
        rsi_data = self.analysis.get('rsi')
        price_data = self.analysis.get('price_data')

        if not all([bollinger_data, rsi_data, price_data]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data (Bollinger, RSI, or Price).")
            return None

        cfg = self._get_signal_config()
        entry_price = price_data['close']
        signal_direction = None

        # ۱. بررسی شرایط خرید (بازگشت از پایین)
        is_price_oversold = bollinger_data['percent_b'] < cfg['bb_buy_threshold']
        is_rsi_oversold = rsi_data['value'] < cfg['rsi_oversold']

        if is_price_oversold and is_rsi_oversold:
            signal_direction = "BUY"

        # ۲. بررسی شرایط فروش (بازگشت از بالا)
        is_price_overbought = bollinger_data['percent_b'] > cfg['bb_sell_threshold']
        is_rsi_overbought = rsi_data['value'] > cfg['rsi_overbought']

        if is_price_overbought and is_rsi_overbought:
            signal_direction = "SELL"
            
        if not signal_direction:
            return None # هیچ شرایط افراطی شناسایی نشد

        logger.info(f"✨ [{self.strategy_name}] Valid signal found! Direction: {signal_direction}")

        # ۳. محاسبه مدیریت ریسک
        # حد ضرر کمی فراتر از باند بولینگر و اولین هدف، باند میانی است
        risk_params = self._calculate_risk_management(entry_price, signal_direction)
        # هدف اول را با باند میانی جایگزین می‌کنیم که هدف اصلی این استراتژی است
        risk_params['targets'][0] = bollinger_data['middle_band']

        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            "stop_loss": risk_params.get("stop_loss"),
            "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": {
                "bollinger_percent_b": bollinger_data['percent_b'],
                "rsi_value": rsi_data['value']
            }
        }
