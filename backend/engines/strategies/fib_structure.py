import logging
from typing import Dict, Any, Optional, List, Tuple
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class FibStructureStrategy(BaseStrategy):
    """
    یک استراتژی بازگشتی بسیار پیشرفته که بر اساس تلاقی (Confluence) بین
    سطوح فیبوناچی و سطوح حمایت/مقاومت ساختاری عمل می‌کند.
    """

    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None, htf_analysis: Optional[Dict[str, Any]] = None):
        super().__init__(analysis_summary, config, htf_analysis)
        self.strategy_name = "ConfluenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """
        پارامترهای قابل تنظیم استراتژی را از فایل کانفیگ بارگیری می‌کند.
        """
        return {
            "fib_levels_to_watch": self.config.get("fib_levels_to_watch", ["38.2", "50", "61.8", "78.6"]),
            "confluence_proximity_percent": self.config.get("confluence_proximity_percent", 0.003),  # 0.3%
            "atr_sl_multiplier": self.config.get("atr_sl_multiplier", 1.5)
        }

    def _find_confluence_zones(self, fib_data: Dict, structure_data: Dict, direction: str) -> List[Dict[str, Any]]:
        """
        این متد قلب استراتژی است: پیدا کردن نواحی تلاقی (PRZ).
        """
        cfg = self._get_signal_config()
        fib_levels = fib_data.get('levels', {})
        key_levels = structure_data.get('key_levels', {})
        
        target_sr_levels = key_levels.get('supports', []) if direction == "BUY" else key_levels.get('resistances', [])
        
        confluence_zones = []

        for fib_level_str in cfg['fib_levels_to_watch']:
            fib_price = fib_levels.get(fib_level_str)
            if not fib_price: continue

            for sr_price in target_sr_levels:
                # بررسی نزدیکی و تلاقی دو سطح
                if abs(fib_price - sr_price) / sr_price < cfg['confluence_proximity_percent']:
                    prz = {
                        "price": (fib_price + sr_price) / 2,
                        "fib_level": fib_level_str,
                        "structure_level": sr_price
                    }
                    confluence_zones.append(prz)
        
        return confluence_zones

    def check_signal(self) -> Optional[Dict[str, Any]]:
        # 1. دریافت داده‌ها
        fib_data = self.analysis.get('fibonacci')
        structure_data = self.analysis.get('structure')
        price_data = self.analysis.get('price_data')
        atr_data = self.analysis.get('atr')

        if not all([fib_data, structure_data, price_data, atr_data]):
            logger.debug(f"[{self.strategy_name}] Missing required indicator data.")
            return None

        # 2. تعیین جهت مورد انتظار برای بازگشت
        swing_trend = fib_data.get('trend_of_swing')
        potential_direction = "BUY" if swing_trend == "Up" else "SELL" if swing_trend == "Down" else None
        if not potential_direction:
            return None

        # 3. پیدا کردن نواحی تلاقی (PRZ)
        pr_zones = self._find_confluence_zones(fib_data, structure_data, potential_direction)
        if not pr_zones:
            return None
        
        logger.info(f"[{self.strategy_name}] Found {len(pr_zones)} Potential Reversal Zones (PRZ).")

        # 4. بررسی تست قیمت و تایید نهایی
        for zone in pr_zones:
            is_testing = False
            if potential_direction == "BUY" and price_data['low'] <= zone['price']:
                is_testing = True
            elif potential_direction == "SELL" and price_data['high'] >= zone['price']:
                is_testing = True
            
            if is_testing:
                logger.info(f"[{self.strategy_name}] Price is testing a PRZ at {zone['price']}.")
                confirming_pattern = self._get_candlestick_confirmation(potential_direction)
                if confirming_pattern:
                    logger.info(f"✨ [{self.strategy_name}] Confluence signal confirmed at {zone['price']} by {confirming_pattern}!")
                    
                    # 5. محاسبه مدیریت ریسک
                    entry_price = price_data['close']
                    atr_value = atr_data.get('value', entry_price * 0.01)
                    stop_loss = zone['structure_level'] - (atr_value * self._get_signal_config()['atr_sl_multiplier']) if potential_direction == "BUY" else zone['structure_level'] + (atr_value * self._get_signal_config()['atr_sl_multiplier'])
                    
                    risk_params = self._calculate_smart_risk_management(entry_price, potential_direction, stop_loss)

                    # 6. آماده‌سازی خروجی نهایی
                    confirmations = {
                        "confluence_zone_price": zone['price'],
                        "fibonacci_level": f"{zone['fib_level']}%",
                        "structure_level": zone['structure_level'],
                        "reversal_pattern": confirming_pattern
                    }
                    return {
                        "strategy_name": self.strategy_name, "direction": potential_direction,
                        "entry_price": entry_price, **risk_params, "confirmations": confirmations
                    }
        return None
