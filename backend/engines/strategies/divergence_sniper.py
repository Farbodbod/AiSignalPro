# engines/strategies/divergence_sniper.py

import logging
from typing import Dict, Any, Optional, List
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class DivergenceSniperStrategy(BaseStrategy):
    """
    استراتژی تک‌تیرانداز واگرایی "The Divergence Sniper".
    این استراتژی به دنبال شکار نقاط بازگشتی بازار با استفاده از ترکیب واگرایی‌های قوی،
    الگوهای شمعی بازگشتی و ساختار بازار برای تعیین حد ضرر است.
    """
    def __init__(self, analysis_summary: Dict[str, Any], config: Dict[str, Any] = None):
        super().__init__(analysis_summary, config)
        self.strategy_name = "DivergenceSniper"

    def _get_signal_config(self) -> Dict[str, Any]:
        """تنظیمات پیش‌فرض و قابل بازنویسی این استراتژی را برمی‌گرداند."""
        return {
            "bullish_reversal_patterns": self.config.get("bullish_reversal_patterns", 
                ['HAMMER', 'INVERTEDHAMMER', 'MORNINGSTAR', 'BULLISHENGULFING', 'PIERCING']),
            "bearish_reversal_patterns": self.config.get("bearish_reversal_patterns", 
                ['SHOOTINGSTAR', 'EVENINGSTAR', 'BEARISHENGULFING', 'DARKCLOUDCOVER']),
        }

    def _has_reversal_pattern(self, direction: str) -> bool:
        """بررسی می‌کند آیا یکی از الگوهای شمعی بازگشتی مورد نظر وجود دارد یا خیر."""
        patterns_data = self.analysis.get('patterns', {})
        found_patterns = patterns_data.get('patterns', [])
        if not found_patterns:
            return False

        cfg = self._get_signal_config()
        target_patterns = cfg['bullish_reversal_patterns'] if direction == "BUY" else cfg['bearish_reversal_patterns']

        # بررسی وجود اشتراک بین الگوهای پیدا شده و الگوهای مورد نظر ما
        return any(pattern.upper() in target_patterns for pattern in found_patterns)

    def check_signal(self) -> Optional[Dict[str, Any]]:
        """
        منطق اصلی استراتژی را برای یافتن سیگنال بازگشتی پیاده‌سازی می‌کند.
        """
        divergence_data = self.analysis.get('divergence')
        structure_data = self.analysis.get('structure')
        price_data = self.analysis.get('price_data')

        if not all([divergence_data, structure_data, price_data]):
            logger.warning(f"[{self.strategy_name}] Missing required analysis data.")
            return None

        signal_direction = None
        
        # ۱. بررسی ماشه ورود (واگرایی قوی)
        if divergence_data['type'] == "Bullish" and divergence_data['strength'] == "Strong":
            signal_direction = "BUY"
        elif divergence_data['type'] == "Bearish" and divergence_data['strength'] == "Strong":
            signal_direction = "SELL"
        
        if not signal_direction:
            return None

        # ۲. بررسی فیلتر تایید (الگوی شمعی بازگشتی)
        if not self._has_reversal_pattern(signal_direction):
            logger.info(f"[{self.strategy_name}] Divergence found but no confirmation reversal pattern.")
            return None
            
        logger.info(f"✨ [{self.strategy_name}] Valid signal found! Direction: {signal_direction}")

        # ۳. محاسبه مدیریت ریسک بر اساس ساختار بازار
        entry_price = price_data['close']
        key_levels = structure_data.get('key_levels', {})
        
        stop_loss = None
        if signal_direction == "BUY":
            # حد ضرر را زیر آخرین کف حمایتی قرار می‌دهیم
            supports = key_levels.get('supports', [])
            if supports:
                stop_loss = supports[0] * 0.998 # کمی پایین‌تر برای اطمینان
        else: # SELL
            # حد ضرر را بالای آخرین سقف مقاومتی قرار می‌دهیم
            resistances = key_levels.get('resistances', [])
            if resistances:
                stop_loss = resistances[0] * 1.002 # کمی بالاتر برای اطمینان

        if stop_loss is None:
            logger.warning(f"[{self.strategy_name}] Could not determine a valid Stop-Loss from market structure.")
            return None

        risk_params = self._calculate_risk_management(entry_price, signal_direction, stop_loss)

        return {
            "strategy_name": self.strategy_name,
            "direction": signal_direction,
            "entry_price": entry_price,
            "stop_loss": risk_params.get("stop_loss"),
            "targets": risk_params.get("targets"),
            "risk_reward_ratio": risk_params.get("risk_reward_ratio"),
            "confirmations": {
                "divergence_type": f"{divergence_data['strength']} {divergence_data['type']}",
                "reversal_patterns": self.analysis.get('patterns', {}).get('patterns', [])
            }
        }

    def _calculate_risk_management(self, entry_price: float, direction: str, stop_loss: float) -> Dict[str, Any]:
        """
        نسخه بازنویسی شده برای استفاده از حد ضرر دقیق ساختار بازار.
        """
        if entry_price == stop_loss: return {}
        risk_amount = abs(entry_price - stop_loss)
        if risk_amount == 0: return {}
        
        reward_ratios = [1.5, 2.5, 4.0] # نسبت‌های ریسک به ریوارد مناسب برای استراتژی‌های بازگشتی
        
        if direction == 'BUY':
            targets = [entry_price + (risk_amount * r) for r in reward_ratios]
        else: # SELL
            targets = [entry_price - (risk_amount * r) for r in reward_ratios]

        actual_rr = round(abs(targets[0] - entry_price) / risk_amount, 2)

        return {
            "stop_loss": round(stop_loss, 5),
            "targets": [round(t, 5) for t in targets],
            "risk_reward_ratio": actual_rr
        }
