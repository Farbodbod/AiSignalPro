# engines/strategy_engine.py (نسخه نهایی 16.0 - با استراتژی سوپرایچیموکو)

import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from .config import StrategyConfig

logger = logging.getLogger(__name__)

class StrategyEngine:
    def __init__(self, analysis_data: Dict[str, Any], config: StrategyConfig):
        self.data = analysis_data
        self.config = config
        self.indicators_df = analysis_data.get("full_dataframe") # نیازمند پاس دادن دیتافریم کامل
        self.indicators = self.data.get("indicators", {})
        self.market = self.data.get("market_structure", {})
        self.trend = self.data.get("trend", {})
        self.entry_price = self.indicators.get("close", 0)
        self.atr = self.indicators.get("atr", 0)

    def _is_valid(self, strategy: Dict) -> bool:
        if not strategy: return False
        is_complete = (strategy.get("stop_loss") is not None and strategy.get("targets"))
        has_good_rr = strategy.get("risk_reward_ratio", 0) >= self.config.min_risk_reward_ratio
        is_sl_safe = self.atr and self.atr > 0 and abs(self.entry_price - strategy.get("stop_loss", self.entry_price)) > self.atr * 0.3
        return is_complete and has_good_rr and is_sl_safe

    def _calculate_sl_tp(self, direction: str, sl_price: float) -> Optional[Dict]:
        if sl_price is None or self.entry_price == sl_price or self.entry_price == 0: return None
        risk_amount = abs(self.entry_price - sl_price)
        if risk_amount == 0: return None
        min_rr = self.config.min_risk_reward_ratio
        targets = [round(self.entry_price + (risk_amount * (min_rr + i * 0.8)), 5) for i in range(3)] if direction == 'BUY' else \
                  [round(self.entry_price - (risk_amount * (min_rr + i * 0.8)), 5) for i in range(3)]
        reward_amount_tp1 = abs(targets[0] - self.entry_price)
        actual_rr = round(reward_amount_tp1 / risk_amount, 2)
        return {"stop_loss": sl_price, "targets": targets, "risk_reward_ratio": actual_rr}

    def _try_trend_strategy(self) -> Optional[Dict]:
        # این استراتژی در حال حاضر کامل و صحیح است و بدون تغییر باقی می‌ماند
        confirmations, score = [], 0
        direction = "BUY" if "Uptrend" in self.trend.get("signal", "") else "SELL" if "Downtrend" in self.trend.get("signal", "") else None
        if not direction: return None
        score += 3; confirmations.append("Primary Trend Signal")
        if self.config.trend_macd_confirmation:
            macd_hist = self.indicators.get("macd_hist", 0)
            if (direction == 'BUY' and macd_hist < 0) or (direction == 'SELL' and macd_hist > 0): return None
            score += 2; confirmations.append("MACD Confirmed")
        rsi = self.indicators.get("rsi", 50)
        if (direction == 'BUY' and rsi > self.config.trend_rsi_max_buy) or (direction == 'SELL' and rsi < self.config.trend_rsi_min_sell): return None
        score += 1; confirmations.append("RSI Zone OK")
        sl_price = self.entry_price - (self.atr * self.config.atr_multiplier_trend) if direction == 'BUY' else self.entry_price + (self.atr * self.config.atr_multiplier_trend)
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None
        return {**sl_tp_data, "strategy_name": "Trend Hunter", "direction": direction, "score": score, "confirmations": confirmations}

    # --- ✨ بازنویسی کامل استراتژی ایچیموکو بر اساس طرح جامع شما (نسخه سوپرایچیموکو) ✨ ---
    def _try_ichimoku_strategy(self) -> Optional[Dict]:
        last = self.indicators
        price, tenkan, kijun, senkou_a, senkou_b, chikou = (last.get(k) for k in ["close", "tenkan", "kijun", "senkou_a", "senkou_b", "chikou"])
        if not all([price, tenkan, kijun, senkou_a, senkou_b, chikou, self.indicators_df is not None]): return None
        
        adx = self.data.get("trend", {}).get("adx", 0)
        score = 0
        confirmations = []
        direction = None
        sl_base = None

        # --- بررسی شرایط پایه (کراس تازه) ---
        df_last3 = self.indicators_df.iloc[-3:]
        is_fresh_bullish_cross = (df_last3['tenkan'] > df_last3['kijun']).any() and df_last3['tenkan'].iloc[-1] > df_last3['kijun'].iloc[-1]
        is_fresh_bearish_cross = (df_last3['tenkan'] < df_last3['kijun']).any() and df_last3['tenkan'].iloc[-1] < df_last3['kijun'].iloc[-1]

        # --- سناریوی خرید (LONG) ---
        if is_fresh_bullish_cross:
            direction = "BUY"
            score += 5; confirmations.append("Fresh TK Cross")
            sl_base = kijun # حد ضرر اولیه بر اساس کیجون
            
            # --- بررسی تاییدهای چندلایه ---
            # موقعیت قیمت نسبت به ابر
            if price > max(senkou_a, senkou_b):
                score += 4; confirmations.append("Price Above Kumo (Strong)")
            elif price > min(senkou_a, senkou_b):
                score += 2; confirmations.append("Price Inside Kumo")
                sl_base = min(senkou_a, senkou_b) # کف ابر به عنوان حمایت قوی‌تر
            else: # قیمت زیر ابر است، سیگنال خرید ضعیف و پرریسک
                score -= 5; confirmations.append("Price Below Kumo (Conflict)")

            # تایید چیکو اسپن
            if chikou > self.indicators_df['high'].iloc[-27]: # قیمت باید بالاتر از سقف کندل ۲۶ دوره قبل باشد
                score += 3; confirmations.append("Chikou Confirmed")

            # جهت ابر آینده
            if senkou_a > senkou_b:
                score += 2; confirmations.append("Future Kumo is Bullish")
            
            # ضخامت ابر
            cloud_thickness = abs(senkou_a - senkou_b) / price
            if cloud_thickness < 0.005: # ابر نازک
                score -= 2; confirmations.append("Thin Kumo (Weak S/R)")

            # تایید قیمت با کیجون
            if price > kijun:
                score += 1; confirmations.append("Price Above Kijun")

        # --- سناریوی فروش (SHORT) ---
        elif is_fresh_bearish_cross:
            direction = "SELL"
            score += 5; confirmations.append("Fresh TK Cross")
            sl_base = kijun

            if price < min(senkou_a, senkou_b):
                score += 4; confirmations.append("Price Below Kumo (Strong)")
            elif price < max(senkou_a, senkou_b):
                score += 2; confirmations.append("Price Inside Kumo")
                sl_base = max(senkou_a, senkou_b) # سقف ابر به عنوان مقاومت قوی‌تر
            else:
                score -= 5; confirmations.append("Price Above Kumo (Conflict)")
            
            if chikou < self.indicators_df['low'].iloc[-27]:
                score += 3; confirmations.append("Chikou Confirmed")
            
            if senkou_a < senkou_b:
                score += 2; confirmations.append("Future Kumo is Bearish")

            cloud_thickness = abs(senkou_a - senkou_b) / price
            if cloud_thickness < 0.005:
                score -= 2; confirmations.append("Thin Kumo (Weak S/R)")
            
            if price < kijun:
                score += 1; confirmations.append("Price Below Kijun")
        
        if not direction: return None

        # فیلتر نهایی ADX
        if adx > 25: score += 2; confirmations.append("ADX Trend Confirmed")
        if score < 8: return None # آستانه امتیاز سخت‌گیرانه‌تر برای سیگنال‌های باکیفیت

        sl_price = sl_base - self.atr if direction == "BUY" else sl_base + self.atr
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None

        return {**sl_tp_data, "strategy_name": "Ichimoku Master", "direction": direction, "score": score, "confirmations": confirmations}

    def _try_volume_profile_reversion(self) -> Optional[Dict]:
        # این استراتژی در حال حاضر کامل و صحیح است و بدون تغییر باقی می‌ماند
        vp = self.market.get("volume_profile", {})
        poc, val, vah = vp.get("point_of_control"), vp.get("value_area_low"), vp.get("value_area_high")
        if not all([poc, val, vah]): return None
        direction, target, sl_base = None, None, None
        if abs(self.entry_price - val) < self.atr * 0.5: direction, target, sl_base = "BUY", poc, val
        elif abs(self.entry_price - vah) < self.atr * 0.5: direction, target, sl_base = "SELL", poc, vah
        if not direction: return None
        sl_price = sl_base - self.atr if direction == "BUY" else sl_base + self.atr
        sl_tp_data = self._calculate_sl_tp(direction, sl_price)
        if not sl_tp_data: return None
        sl_tp_data['targets'].insert(0, target)
        sl_tp_data['targets'] = sorted(list(set(sl_tp_data['targets'])), reverse=(direction=="SELL"))
        return {**sl_tp_data, "strategy_name": "Volume Profile Reversion", "direction": direction, "score": 8.0, "confirmations": confirmations}

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
