# engines/strategy_engine.py (نسخه نهایی 14.2 - با استراتژی پروفایل حجم)

import logging
from typing import Dict, Any, List, Optional
from .config import StrategyConfig

logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self, analysis_data: Dict[str, Any], config: StrategyConfig):
        self.data = analysis_data; self.config = config
        self.indicators = self.data.get("indicators", {})
        self.market = self.data.get("market_structure", {})
        self.trend = self.data.get("trend", {})
        self.entry_price = self.indicators.get("close", 0)
        self.atr = self.indicators.get("atr", 0)

    def _is_valid(self, strategy: Dict) -> bool:
        if not strategy: return False
        is_complete = (strategy.get("stop_loss") is not None and strategy.get("targets"))
        has_good_rr = strategy.get("risk_reward_ratio", 0) >= self.config.min_risk_reward_ratio
        is_sl_safe = self.atr > 0 and abs(self.entry_price - strategy.get("stop_loss", self.entry_price)) > self.atr * 0.3
        return is_complete and has_good_rr and is_sl_safe

    def _calculate_sl_tp(self, direction: str, sl_price: float) -> Optional[Dict]:
        if sl_price is None or self.entry_price == sl_price: return None
        risk_amount = abs(self.entry_price - sl_price)
        if risk_amount == 0: return None
        rr = self.config.min_risk_reward_ratio
        targets = [round(self.entry_price + (risk_amount * (rr + i*0.8)), 5) for i in range(3)] if direction == 'BUY' else \
                  [round(self.entry_price - (risk_amount * (rr + i*0.8)), 5) for i in range(3)]
        return {"stop_loss": sl_price, "targets": targets, "risk_reward_ratio": rr}

    def _try_trend_strategy(self) -> Optional[Dict]:
        confirmations, score = [], 0
        direction = "BUY" if "Uptrend" in self.trend.get("signal", "") else "SELL" if "Downtrend" in self.trend.get("signal", "") else None
        if not direction: return None
        score += 3; confirmations.append("Primary Trend Signal")
        if self.config.trend_macd_confirmation:
            macd_hist = self.indicators.get("macd_hist", 0)
            if (direction == 'BUY' and macd_hist < 0) or (direction == 'SELL' and macd_hist > 0): return None
            score += 2; confirmations.append("MACD Confirmed")
        rsi = self.indicators.get("rsi", 50)
        if (direction == 'BUY' and rsi > self.config.trend_rsi_max_buy) or \
           (direction == 'SELL' and rsi < self.config.trend_rsi_min_sell): return None
        score += 1; confirmations.append("RSI Zone OK")
        sl_price = self.entry_price - (self.atr * self.config.atr_multiplier_trend) if direction == 'BUY' else self.entry_price + (self.atr * self.config.atr_multiplier_trend)
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None
        return {**sl_tp_data, "strategy_name": "Trend Hunter", "direction": direction, "score": score, "confirmations": confirmations}

    def _try_ichimoku_strategy(self) -> Optional[Dict]:
        last = self.indicators
        price, senkou_a, senkou_b, kijun = self.entry_price, last.get("senkou_a"), last.get("senkou_b"), last.get("kijun")
        if not all([price, senkou_a, senkou_b, kijun]): return None
        direction = "BUY" if price > senkou_a and price > senkou_b else "SELL" if price < senkou_a and price < senkou_b else None
        if not direction: return None
        sl_price = kijun - self.atr * self.config.ichimoku_kijun_sl_multiplier if direction == "BUY" else kijun + self.atr * self.config.ichimoku_kijun_sl_multiplier
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None
        return {**sl_tp_data, "strategy_name": "Ichimoku Breakout", "direction": direction, "score": 6.0, "confirmations": ["Kumo Breakout"]}

    def _try_volume_profile_reversion(self) -> Optional[Dict]:
        """جدید: استراتژی بازگشت به میانگین بر اساس نقاط کلیدی پروفایل حجم."""
        vp = self.market.get("volume_profile", {})
        poc = vp.get("point_of_control")
        val = vp.get("value_area_low")
        vah = vp.get("value_area_high")
        if not all([poc, val, vah]): return None

        direction, target, sl_base = None, None, None
        # اگر به کف محدوده ارزشمند نزدیکیم، به دنبال خرید هستیم
        if abs(self.entry_price - val) < self.atr * 0.5:
            direction, target, sl_base = "BUY", poc, val
        # اگر به سقف محدوده ارزشمند نزدیکیم، به دنبال فروش هستیم
        elif abs(self.entry_price - vah) < self.atr * 0.5:
            direction, target, sl_base = "SELL", poc, vah
        
        if not direction: return None

        sl_price = sl_base - self.atr if direction == "BUY" else sl_base + self.atr
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None
        # افزودن تارگت POC به لیست تارگت‌ها
        sl_tp_data['targets'].insert(0, target)
        sl_tp_data['targets'] = sorted(list(set(sl_tp_data['targets'])), reverse=(direction=="SELL"))

        return {**sl_tp_data, "strategy_name": "Volume Profile Reversion", "direction": direction, "score": 8.0, "confirmations": ["Near Value Area Edge"]}

    def generate_all_valid_strategies(self) -> List[Dict[str, Any]]:
        strategies = [
            self._try_trend_strategy(),
            self._try_ichimoku_strategy(),
            self._try_volume_profile_reversion(),
        ]
        valid_strategies = [s for s in strategies if s and self._is_valid(s)]
        for s in valid_strategies:
            s["entry_price"] = self.entry_price
            if self.atr > 0:
                s["entry_zone"] = sorted([round(self.entry_price - self.atr * 0.15, 5), round(self.entry_price + self.atr * 0.15, 5)])
        return valid_strategies
