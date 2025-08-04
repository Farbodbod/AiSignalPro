# engines/strategy_engine.py (نسخه 11.0 با تنظیمات بهینه ریسک)

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self, analysis_data: Dict[str, Any]):
        self.data = analysis_data
        self.indicators = self.data.get("indicators", {})
        self.market_structure = self.data.get("market_structure", {})
        self.trend = self.data.get("trend", {})

    def _calculate_entry_zone(self, entry_price: float) -> List[float]:
        atr = self.indicators.get("atr", 0)
        if atr > 0 and entry_price > 0:
            offset = atr * 0.15 
            return sorted([round(entry_price - offset, 4), round(entry_price + offset, 4)])
        return [round(entry_price, 4)]

    def _calculate_targets(self, direction: str, entry_price: float, stop_loss: float, custom_target: Optional[float] = None) -> List[float]:
        if stop_loss is None or entry_price == stop_loss: return []
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return []
        targets = []
        if custom_target and pd.notna(custom_target):
            targets.append(round(custom_target, 4))
        if direction == 'BUY':
            targets.append(round(entry_price + (risk_amount * 1.5), 4))
            targets.append(round(entry_price + (risk_amount * 2.5), 4)) # اضافه کردن تارگت دوم
        elif direction == 'SELL':
            targets.append(round(entry_price - (risk_amount * 1.5), 4))
            targets.append(round(entry_price - (risk_amount * 2.5), 4))
        return sorted(list(set(targets)))

    def _generate_pivot_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        pivots = self.market_structure.get("pivots", [])
        atr = self.indicators.get("atr", 0)
        if not pivots or atr == 0 or entry_price == 0: return {}
        stop_loss = None
        if direction == 'BUY':
            relevant_pivots = [p[1] for p in pivots if p[1] < entry_price]
            if relevant_pivots: stop_loss = round(max(relevant_pivots) - (atr * 0.1), 4) # ضریب کمتر
        elif direction == 'SELL':
            relevant_pivots = [p[1] for p in pivots if p[1] > entry_price]
            if relevant_pivots: stop_loss = round(min(relevant_pivots) + (atr * 0.1), 4) # ضریب کمتر
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Pivot Reversion"}

    def _generate_trend_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        atr = self.indicators.get("atr", 0)
        if atr == 0 or entry_price == 0: return {}
        stop_loss = None
        # ✨ بهینه‌سازی: ضریب ATR برای حد ضرر کمی کاهش یافت تا در نوسانات بالا منطقی‌تر باشد
        if direction == 'BUY':
            stop_loss = round(entry_price - (atr * 1.2), 4) 
        elif direction == 'SELL':
            stop_loss = round(entry_price + (atr * 1.2), 4)
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Trend Hunter"}

    def _generate_volatility_breakout_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        atr = self.indicators.get("atr", 0)
        if atr == 0 or entry_price == 0: return {}
        stop_loss = None
        # ✨ بهینه‌سازی: در شکست‌های ناشی از نوسان، حد ضرر باید نزدیک‌تر باشد
        if direction == 'BUY':
            stop_loss = round(entry_price - (atr * 0.8), 4)
        elif direction == 'SELL':
            stop_loss = round(entry_price + (atr * 0.8), 4)
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Volatility Breakout"}

    def _generate_range_strategy(self) -> Dict[str, Any]:
        pivots = self.market_structure.get("pivots", [])
        if len(pivots) < 4: return {}
        recent_pivots = sorted(pivots, key=lambda x: x[0], reverse=True)[:4]
        highs = sorted([p[1] for p in recent_pivots], reverse=True)
        lows = sorted([p[1] for p in recent_pivots])
        if len(highs) < 2 or len(lows) < 2: return {}
        resistance, support = highs[0], lows[0]
        entry_price = self.indicators.get("close", 0)
        atr = self.indicators.get("atr", 0)
        if atr == 0 or entry_price == 0: return {}
        if abs(entry_price - support) < (atr * 0.3): # کمی انعطاف‌پذیری بیشتر
            direction, stop_loss = "BUY", round(support - (atr * 0.3), 4)
            targets = self._calculate_targets(direction, entry_price, stop_loss, custom_target=resistance)
            return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Range Hunter"}
        elif abs(entry_price - resistance) < (atr * 0.3):
            direction, stop_loss = "SELL", round(resistance + (atr * 0.3), 4)
            targets = self._calculate_targets(direction, entry_price, stop_loss, custom_target=support)
            return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Range Hunter"}
        return {}

    def generate_strategy(self, signal_type: str) -> Dict[str, Any]:
        trend_signal = self.trend.get("signal", "Neutral")
        is_breakout = self.trend.get("breakout", False)
        is_volatility_spike = self.trend.get("volatility_spike", False)
        strategy_plan = {}

        if is_breakout or is_volatility_spike:
            logger.info(f"Condition: Volatility/Breakout detected. Trying Volatility Breakout strategy.")
            strategy_plan = self._generate_volatility_breakout_strategy(signal_type)
        elif "Strong" in trend_signal:
            logger.info(f"Condition: Strong trend detected ({trend_signal}). Trying Trend Hunter strategy.")
            strategy_plan = self._generate_trend_strategy(signal_type)
        elif "Ranging" in trend_signal:
            logger.info(f"Condition: Ranging market detected. Trying Range Hunter strategy.")
            strategy_plan = self._generate_range_strategy()
        else: 
            logger.info(f"Condition: Weak/Uncertain market ({trend_signal}). Trying Pivot Reversion strategy.")
            strategy_plan = self._generate_pivot_strategy(signal_type)
        
        entry_price = strategy_plan.get("entry_price")
        if not entry_price: return {}

        strategy_plan["entry_zone"] = self._calculate_entry_zone(entry_price)
        risk_reward_ratio = 0
        targets, stop_loss = strategy_plan.get("targets"), strategy_plan.get("stop_loss")
        if targets and stop_loss and (entry_price - stop_loss) != 0:
            reward, risk = abs(targets[0] - entry_price), abs(entry_price - stop_loss)
            if risk > 0: risk_reward_ratio = round(reward / risk, 2)
        
        strategy_plan["risk_reward_ratio"] = risk_reward_ratio
        return strategy_plan

    def is_strategy_valid(self, strategy: Dict[str, Any]) -> bool:
        if not strategy: return False
        has_stop_loss = strategy.get("stop_loss") is not None
        has_targets = strategy.get("targets") is not None and len(strategy["targets"]) > 0
        # اضافه کردن یک فیلتر ریسک به ریوارد
        has_good_rr = strategy.get("risk_reward_ratio", 0) >= 1.2 
        return has_stop_loss and has_targets and has_good_rr
