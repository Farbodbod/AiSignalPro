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
            current_price = self.indicators.get('close', 0)

            if not atr or not pivots or current_price == 0:
                return None

            if direction == 'BUY':
                # برای خرید، زیر آخرین کف (low pivot) که پایین تر از قیمت فعلی است قرار می‌دهیم
                relevant_pivots = [p[1] for p in pivots if p[1] < current_price]
                if not relevant_pivots: return None
                
                last_low_pivot = max(relevant_pivots)
                return round(last_low_pivot - (atr * 0.5), 4)
            
            elif direction == 'SELL':
                # برای فروش، بالای آخرین سقف (high pivot) که بالاتر از قیمت فعلی است قرار می‌دهیم
                relevant_pivots = [p[1] for p in pivots if p[1] > current_price]
                if not relevant_pivots: return None

                last_high_pivot = min(relevant_pivots)
                return round(last_high_pivot + (atr * 0.5), 4)
            
            return None
        except Exception as e:
            logger.error(f"Error calculating Stop Loss: {e}")
            return None

    def calculate_targets(self, direction: str, entry_price: float, stop_loss: float) -> List[float]:
        """
        (نسخه ضد خطا) تارگت‌های سود را بر اساس جهت سیگنال محاسبه می‌کند.
        """
        if stop_loss is None or entry_price == stop_loss:
            return []
            
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return []
        
        targets = []
        pivots = self.market_structure.get("pivots", [])

        try:
            if direction == 'BUY':
                # برای خرید، اهداف باید بالاتر از قیمت ورود باشند
                # تارگت اول: ۱.۵ برابر ریسک
                target_1 = entry_price + (risk_amount * 1.5)
                targets.append(round(target_1, 4))
                
                # تارگت دوم: نزدیک‌ترین پیوت مقاومت بعدی
                potential_targets = sorted([p[1] for p in pivots if p[1] > target_1])
                if potential_targets:
                    targets.append(round(potential_targets[0], 4))

            elif direction == 'SELL':
                # برای فروش، اهداف باید پایین‌تر از قیمت ورود باشند
                # تارگت اول: ۱.۵ برابر ریسک
                target_1 = entry_price - (risk_amount * 1.5)
                targets.append(round(target_1, 4))
                
                # تارگت دوم: نزدیک‌ترین پیوت حمایت بعدی
                potential_targets = sorted([p[1] for p in pivots if p[1] < target_1], reverse=True)
                if potential_targets:
                    targets.append(round(potential_targets[0], 4))

            return sorted(list(set(targets)))
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
        
        risk_reward_ratio = 0
        if targets and stop_loss and (entry_price - stop_loss) != 0:
            reward = abs(targets[0] - entry_price)
            risk = abs(entry_price - stop_loss)
            if risk > 0:
                risk_reward_ratio = round(reward / risk, 2)

        return {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward_ratio": risk_reward_ratio,
            "support_levels": sorted([p[1] for p in self.market_structure.get("pivots", []) if p[1] < entry_price], reverse=True)[:3],
            "resistance_levels": sorted([p[1] for p in self.market_structure.get("pivots", []) if p[1] > entry_price])[:3],
        }

    def is_strategy_valid(self, strategy: Dict[str, Any]) -> bool:
        """
        بررسی می کند که آیا استراتژی تولید شده معتبر و کامل است یا خیر.
        """
        if not strategy:
            return False
        
        has_stop_loss = strategy.get("stop_loss") is not None
        has_targets = strategy.get("targets") is not None and len(strategy["targets"]) > 0
        
        # یک استراتژی فقط زمانی معتبر است که هم حد ضرر و هم حداقل یک تارگت داشته باشد
        return has_stop_loss and has_targets
