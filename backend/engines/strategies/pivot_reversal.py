# engines/strategies/pivot_reversal.py

import logging
from typing import Dict, Any, Optional
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class PivotReversalStrategy(BaseStrategy):
    """
    استراتژی تک‌تیرانداز پیوت "The Pivot Sniper".
    این استراتژی به دنبال شکار نقاط بازگشتی در سطوح کلیدی پیوت پوینت است که
    توسط یک نوسانگر مانند استوکاستیک تایید شده باشند.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "PivotSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض و قابل بازنویسی این استراتژی."""
        return {
            "proximity_percent": self.config.get("proximity_percent", 0.002), # 0.2%
            "stoch_oversold": self.config.get("stoch_oversold", 25),
            "stoch_overbought": self.config.get("stoch_overbought", 75),
            "pivot_levels_to_check": self.config.get("pivot_levels_to_check", ['R2', 'R1', 'S1', 'S2']),
        }

    def check_signal(self) -> Optional[Dict[str, Any]]:
        pivots_data = self.analysis.get('pivots')
        stoch_data = self.analysis.get('stochastic')
        price_data = self.analysis.get('price_data')

        if not all([pivots_data, stoch_data, price_data]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data.")
            return None

        cfg = self._get_signal_config()
        current_price = price_data['close']
        pivot_levels = pivots_data.get('levels', {})
        signal_direction = None
        trigger_level_name = None

        for level_name in cfg['pivot_levels_to_check']:
            level_price = pivot_levels.get(level_name)
            if not level_price: continue

            # محاسبه فاصله قیمت از سطح به درصد
            proximity = abs(current_price - level_price) / current_price

            # ۱. بررسی ماشه ورود (نزدیکی به سطح پیوت)
            if proximity < cfg['proximity_percent']:
                # بررسی شرایط خرید در سطوح حمایتی (S1, S2)
                if level_name.startswith('S') and stoch_data['position'] == "Oversold" and stoch_data['percent_k'] < cfg['stoch_oversold']:
                    signal_direction = "BUY"
                    trigger_level_name = level_name
                    break
                # بررسی شرایط فروش در سطوح مقاومتی (R1, R2)
                elif level_name.startswith('R') and stoch_data['position'] == "Overbought" and stoch_data['percent_k'] > cfg['stoch_overbought']:
                    signal_direction = "SELL"
                    trigger_level_name = level_name
                    break
        
        if not signal_direction:
            return None

        logger.info(f"✨ [{self.strategy_name}] Valid signal! {signal_direction} near {trigger_level_name}")

        # ۳. محاسبه مدیریت ریسک
        stop_loss = None
        atr_val = self.analysis.get('atr', {}).get('value', current_price * 0.01)
        if signal_direction == "BUY":
            stop_loss = level_price - atr_val # حد ضرر کمی پایین‌تر از سطح حمایتی
        else: # SELL
            stop_loss = level_price + atr_val # حد ضرر کمی بالاتر از سطح مقاومتی
        
        risk_params = self._calculate_risk_management(current_price, signal_direction, stop_loss)
        # هدف اول را پیوت اصلی (P) قرار می‌دهیم که هدف منطقی این استراتژی است
        risk_params['targets'][0] = pivot_levels.get('P')

        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": current_price,
            "stop_loss": risk_params.get("stop_loss"),
            "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": {
                "trigger_pivot_level": trigger_level_name,
                "stochastic_k": stoch_data['percent_k']
            }
        }
