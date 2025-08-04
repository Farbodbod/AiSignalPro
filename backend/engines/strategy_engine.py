# engines/strategy_engine.py (نسخه 12.1 - اصلاحات جزئی)

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

# اصلاح شد: استفاده صحیح از لاگر
logger = logging.getLogger(__name__)

class StrategyEngine:
    # اصلاح شد: استفاده صحیح از __init__
    def __init__(self, analysis_data: Dict[str, Any]):
        self.data = analysis_data
        self.indicators = self.data.get("indicators", {})
        self.market_structure = self.data.get("market_structure", {})
        self.trend = self.data.get("trend", {})
        self.entry_price = self.indicators.get("close", 0)
        self.atr = self.indicators.get("atr", 0)

    def _calculate_entry_zone(self, entry_price: float) -> List[float]:
        if self.atr > 0 and entry_price > 0:
            offset = self.atr * 0.15
            return sorted([round(entry_price - offset, 4), round(entry_price + offset, 4)])
        return [round(entry_price, 4)]
        
    def _remove_duplicates_preserve_order(self, lst: List[float]) -> List[float]:
        seen = set()
        return [x for x in lst if not (x in seen or seen.add(x))]

    def _calculate_targets(self, direction: str, entry_price: float, stop_loss: float, custom_target: Optional[float] = None) -> List[float]:
        if stop_loss is None or entry_price == stop_loss: return []
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return []
        targets = []
        if custom_target and pd.notna(custom_target):
            targets.append(round(custom_target, 4))
        if direction == 'BUY':
            targets += [round(entry_price + (risk_amount * 1.5), 4), round(entry_price + (risk_amount * 2.5), 4)]
        elif direction == 'SELL':
            targets += [round(entry_price - (risk_amount * 1.5), 4), round(entry_price - (risk_amount * 2.5), 4)]
        return sorted(self._remove_duplicates_preserve_order(targets))

    def _generate_pivot_strategy(self, direction: str) -> Dict[str, Any]:
        if not self.entry_price or not self.atr: return {}
        pivots = self.market_structure.get("pivots", [])
        if not pivots: return {}
        stop_loss = None
        if direction == 'BUY':
            relevant = [p[1] for p in pivots if p[1] < self.entry_price]
            if relevant: stop_loss = round(max(relevant) - (self.atr * 0.1), 4)
        elif direction == 'SELL':
            relevant = [p[1] for p in pivots if p[1] > self.entry_price]
            if relevant: stop_loss = round(min(relevant) + (self.atr * 0.1), 4)
        targets = self._calculate_targets(direction, self.entry_price, stop_loss)
        return {"entry_price": self.entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Pivot Reversion", "meta": {"direction": direction, "source": "pivot"}}

    def _generate_trend_strategy(self, direction: str) -> Dict[str, Any]:
        if not self.entry_price or not self.atr: return {}
        stop_loss = round(self.entry_price - (self.atr * 1.2), 4) if direction == 'BUY' else round(self.entry_price + (self.atr * 1.2), 4)
        targets = self._calculate_targets(direction, self.entry_price, stop_loss)
        return {"entry_price": self.entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Trend Hunter", "meta": {"direction": direction, "source": "trend"}}

    def _generate_volatility_breakout_strategy(self, direction: str) -> Dict[str, Any]:
        if not self.entry_price or not self.atr: return {}
        stop_loss = round(self.entry_price - (self.atr * 0.8), 4) if direction == 'BUY' else round(self.entry_price + (self.atr * 0.8), 4)
        targets = self._calculate_targets(direction, self.entry_price, stop_loss)
        return {"entry_price": self.entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Volatility Breakout", "meta": {"direction": direction, "source": "volatility"}}

    def _generate_range_strategy(self) -> Dict[str, Any]:
        pivots = self.market_structure.get("pivots", [])
        if len(pivots) < 4 or not self.entry_price or not self.atr: return {}
        recent = sorted(pivots, key=lambda x: x[0], reverse=True)[:4]
        highs = sorted([p[1] for p in recent], reverse=True)
        lows = sorted([p[1] for p in recent])
        if len(highs) < 2 or len(lows) < 2: return {}
        resistance = sum(highs[:2]) / 2
        support = sum(lows[:2]) / 2
        if abs(self.entry_price - support) < (self.atr * 0.3):
            direction = "BUY"; stop_loss = round(support - (self.atr * 0.3), 4)
            targets = self._calculate_targets(direction, self.entry_price, stop_loss, custom_target=resistance)
        elif abs(self.entry_price - resistance) < (self.atr * 0.3):
            direction = "SELL"; stop_loss = round(resistance + (self.atr * 0.3), 4)
            targets = self._calculate_targets(direction, self.entry_price, stop_loss, custom_target=support)
        else: return {}
        return {"entry_price": self.entry_price, "stop_loss": stop_loss, "targets": targets, "strategy_name": "Range Hunter", "meta": {"direction": direction, "source": "range"}}

    def generate_strategy(self, signal_type: str) -> Dict[str, Any]:
        trend_signal = self.trend.get("signal", "Neutral"); is_breakout = self.trend.get("breakout", False); is_volatility_spike = self.trend.get("volatility_spike", False)
        if is_breakout or is_volatility_spike:
            logger.info("Volatility/Breakout detected."); strategy = self._generate_volatility_breakout_strategy(signal_type)
        elif "Strong" in trend_signal:
            logger.info(f"Strong trend detected: {trend_signal}"); strategy = self._generate_trend_strategy(signal_type)
        elif "Ranging" in trend_signal:
            logger.info("Ranging market detected."); strategy = self._generate_range_strategy()
        else:
            logger.info(f"Weak/Uncertain market: {trend_signal}"); strategy = self._generate_pivot_strategy(signal_type)
        entry_price = strategy.get("entry_price")
        if not entry_price: return {}
        strategy["entry_zone"] = self._calculate_entry_zone(entry_price)
        risk_reward_ratio = 0
        targets, stop_loss = strategy.get("targets"), strategy.get("stop_loss")
        if targets and stop_loss:
            reward, risk = abs(targets[0] - entry_price), abs(entry_price - stop_loss)
            if reward > 0 and risk > 0: risk_reward_ratio = round(reward / risk, 2)
        strategy["risk_reward_ratio"] = risk_reward_ratio
        return strategy

    def is_strategy_valid(self, strategy: Dict[str, Any]) -> bool:
        if not strategy: return False
        has_stop_loss = strategy.get("stop_loss") is not None
        has_targets = strategy.get("targets") and len(strategy["targets"]) > 0
        has_good_rr = strategy.get("risk_reward_ratio", 0) >= 1.2
        return has_stop_loss and has_targets and has_good_rr
