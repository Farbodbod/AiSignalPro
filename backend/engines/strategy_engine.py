# engines/strategy_engine.py (نسخه 9.0 با سه استراتژی معاملاتی)

import logging
from typing import Dict, Any, List, Optional

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

    def _calculate_targets(self, direction: str, entry_price: float, stop_loss: float) -> List[float]:
        if stop_loss is None or entry_price == stop_loss: return []
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return []
        targets = []
        if direction == 'BUY':
            targets.append(round(entry_price + (risk_amount * 1.5), 4))
            targets.append(round(entry_price + (risk_amount * 3.0), 4))
        elif direction == 'SELL':
            targets.append(round(entry_price - (risk_amount * 1.5), 4))
            targets.append(round(entry_price - (risk_amount * 3.0), 4))
        return sorted(list(set(targets)))

    # --- استراتژی شماره ۱: مبتنی بر سطوح (Pivot Reversion) ---
    def _generate_pivot_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        pivots = self.market_structure.get("pivots", [])
        atr = self.indicators.get("atr", 0)
        if not pivots or atr == 0: return {}
        stop_loss = None
        if direction == 'BUY':
            relevant_pivots = [p[1] for p in pivots if p[1] < entry_price]
            if relevant_pivots: stop_loss = round(max(relevant_pivots) - (atr * 0.2), 4)
        elif direction == 'SELL':
            relevant_pivots = [p[1] for p in pivots if p[1] > entry_price]
            if relevant_pivots: stop_loss = round(min(relevant_pivots) + (atr * 0.2), 4)
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Pivot Reversion"}

    # --- استراتژی شماره ۲: شکارچی روند (Trend Hunter) ---
    def _generate_trend_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        atr = self.indicators.get("atr", 0)
        if atr == 0: return {}
        stop_loss = None
        if direction == 'BUY':
            stop_loss = round(entry_price - (atr * 1.5), 4)
        elif direction == 'SELL':
            stop_loss = round(entry_price + (atr * 1.5), 4)
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Trend Hunter"}

    # --- ✨ استراتژی شماره ۳: شکارچی شکست (Breakout Hunter) ✨ ---
    def _generate_breakout_strategy(self, direction: str) -> Dict[str, Any]:
        entry_price = self.indicators.get("close", 0)
        pivots = self.market_structure.get("pivots", [])
        atr = self.indicators.get("atr", 0)
        if not pivots or atr == 0: return {}
        stop_loss = None
        if direction == 'BUY':
            # حد ضرر زیر سطح مقاومتی است که شکسته شده
            broken_resistance = max([p[1] for p in pivots if p[1] < entry_price], default=None)
            if broken_resistance: stop_loss = round(broken_resistance - (atr * 0.2), 4)
        elif direction == 'SELL':
            # حد ضرر بالای سطح حمایتی است که شکسته شده
            broken_support = min([p[1] for p in pivots if p[1] > entry_price], default=None)
            if broken_support: stop_loss = round(broken_support + (atr * 0.2), 4)
        
        targets = self._calculate_targets(direction, entry_price, stop_loss)
        return {"entry_price": entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Breakout Hunter"}

    def generate_strategy(self, signal_type: str) -> Dict[str, Any]:
        if signal_type not in ["BUY", "SELL"]: return {}
        
        # --- ✨ توزیع کننده هوشمند استراتژی ✨ ---
        is_breakout = self.trend.get("breakout", False)
        adx = self.trend.get("adx", 0)
        strategy_plan = {}

        if is_breakout:
            logger.info(f"Breakout detected. Using Breakout Hunter strategy.")
            strategy_plan = self._generate_breakout_strategy(signal_type)
        elif adx > 35:
            logger.info(f"Strong trend detected (ADX: {adx}). Using Trend Hunter strategy.")
            strategy_plan = self._generate_trend_strategy(signal_type)
        else:
            logger.info(f"Normal/Ranging market (ADX: {adx}). Using Pivot Reversion strategy.")
            strategy_plan = self._generate_pivot_strategy(signal_type)
        
        entry_price = strategy_plan.get("entry_price")
        if not entry_price: return {}

        strategy_plan["entry_zone"] = self._calculate_entry_zone(entry_price)
        risk_reward_ratio = 0
        targets = strategy_plan.get("targets")
        stop_loss = strategy_plan.get("stop_loss")
        if targets and stop_loss and (entry_price - stop_loss) != 0:
            reward = abs(targets[0] - entry_price); risk = abs(entry_price - stop_loss)
            if risk > 0: risk_reward_ratio = round(reward / risk, 2)
        
        strategy_plan["risk_reward_ratio"] = risk_reward_ratio
        return strategy_plan

    def is_strategy_valid(self, strategy: Dict[str, Any]) -> bool:
        if not strategy: return False
        has_stop_loss = strategy.get("stop_loss") is not None
        has_targets = strategy.get("targets") is not None and len(strategy["targets"]) > 0
        return has_stop_loss and has_targets
