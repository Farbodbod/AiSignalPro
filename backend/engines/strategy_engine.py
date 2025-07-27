# engines/strategy_engine.py

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self, analysis_data: Dict[str, Any]):
        """
        این موتور، داده‌های تحلیلی خام را به عنوان ورودی می‌گیرد.
        """
        self.data = analysis_data
        self.indicators = self.data.get("indicators", {})
        self.market_structure = self.data.get("market_structure", {})

    def calculate_stop_loss(self, direction: str) -> Optional[float]:
        """
        حد ضرر را به صورت هوشمند بر اساس ساختار بازار و نوسانات (ATR) محاسبه می‌کند.
        """
        try:
            atr = self.indicators.get("atr")
            pivots = self.market_structure.get("pivots", [])
            if not atr or not pivots:
                return None

            if direction == 'BUY':
                # برای خرید، زیر آخرین کف (low pivot) قرار می‌دهیم
                last_low_pivot = max([p[1] for p in pivots if p[2] == 'minor' and p[1] < self.indicators.get('close', 0)], default=None)
                if last_low_pivot:
                    return round(last_low_pivot - (atr * 0.5), 4) # کمی پایین‌تر از کف با ضریب ATR
            elif direction == 'SELL':
                # برای فروش، بالای آخرین سقف (high pivot) قرار می‌دهیم
                last_high_pivot = min([p[1] for p in pivots if p[2] == 'minor' and p[1] > self.indicators.get('close', 0)], default=None)
                if last_high_pivot:
                    return round(last_high_pivot + (atr * 0.5), 4) # کمی بالاتر از سقف با ضریب ATR
            return None
        except Exception as e:
            logger.error(f"Error calculating Stop Loss: {e}")
            return None

    def calculate_targets(self, direction: str, entry_price: float, stop_loss: float) -> List[float]:
        """
        تارگت‌های سود را بر اساس پیوت‌های بعدی و نسبت ریسک به ریوارد محاسبه می‌کند.
        """
        if stop_loss is None:
            return []
            
        risk_amount = abs(entry_price - stop_loss)
        targets = []

        try:
            pivots = self.market_structure.get("pivots", [])
            if not pivots:
                return []

            if direction == 'BUY':
                # تارگت‌ها، پیوت‌های سقف (high pivots) بعدی هستند
                potential_targets = sorted([p[1] for p in pivots if p[1] > entry_price])
                # تارگت اول: حداقل ۱.۵ برابر ریسک
                target_1 = entry_price + (risk_amount * 1.5)
                targets.append(round(target_1, 4))
                # تارگت دوم: نزدیک‌ترین پیوت به تارگت اول
                if potential_targets:
                    targets.append(round(min(potential_targets, key=lambda x:abs(x-target_1)), 4))

            elif direction == 'SELL':
                # تارگت‌ها، پیوت‌های کف (low pivots) بعدی هستند
                potential_targets = sorted([p[1] for p in pivots if p[1] < entry_price], reverse=True)
                target_1 = entry_price - (risk_amount * 1.5)
                targets.append(round(target_1, 4))
                if potential_targets:
                    targets.append(round(min(potential_targets, key=lambda x:abs(x-target_1)), 4))

            return sorted(list(set(targets))) # حذف موارد تکراری و مرتب‌سازی
        except Exception as e:
            logger.error(f"Error calculating Targets: {e}")
            return []


    def generate_strategy(self, signal_type: str) -> Dict[str, Any]:
        """
        استراتژی کامل معامله (حد ضرر، تارگت‌ها و...) را تولید می‌کند.
        """
        if signal_type not in ["BUY", "SELL"]:
            return {}

        entry_price = self.indicators.get("close", 0)
        stop_loss = self.calculate_stop_loss(signal_type)
        targets = self.calculate_targets(signal_type, entry_price, stop_loss)
        
        # محاسبه ریسک به ریوارد برای اولین تارگت
        risk_reward_ratio = 0
        if targets and stop_loss and (entry_price - stop_loss) != 0:
            reward = abs(targets[0] - entry_price)
            risk = abs(entry_price - stop_loss)
            risk_reward_ratio = round(reward / risk, 2)

        return {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward_ratio": risk_reward_ratio,
            "support_levels": sorted([p[1] for p in self.market_structure.get("pivots", []) if p[1] < entry_price], reverse=True)[:3],
            "resistance_levels": sorted([p[1] for p in self.market_structure.get("pivots", []) if p[1] > entry_price])[:3],
        }
