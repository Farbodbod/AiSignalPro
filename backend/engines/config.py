# engines/config.py (نسخه نهایی 2.3 - کاملاً بی‌نقص و بازبینی شده)

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class BonusScores:
    """ امتیازات پاداش برای تاییدهای جانبی از تحلیلگرهای دیگر. """
    bullish_divergence: float = 3.0
    bearish_divergence: float = 3.0
    bullish_pattern: float = 2.0
    bearish_pattern: float = 2.0
    whale_activity_spike: float = 4.0

@dataclass
class StrategyConfig:
    """ پیکربندی دقیق برای تمام استراتژی‌های رقیب در StrategyEngine. """
    # پارامتر عمومی
    min_risk_reward_ratio: float = 1.5
    
    # پارامترهای استراتژی روند (Trend Hunter)
    trend_rsi_max_buy: int = 75
    trend_rsi_min_sell: int = 25
    trend_macd_confirmation: bool = True
    atr_multiplier_trend: float = 1.8
    
    # پارامترهای استراتژی ایچیموکو (Ichimoku Breakout)
    ichimoku_kijun_sl_multiplier: float = 0.5
    
    # پارامترهای استراتژی بازگشتی (Mean Reversion)
    reversion_rsi_overbought: int = 70
    reversion_rsi_oversold: int = 30
    reversion_divergence_confirmation: bool = True
    atr_multiplier_reversion: float = 1.2

    # پارامترهای استراتژی رنج (Range Hunter) - (این بخش در نسخه قبلی جا افتاده بود)
    range_stoch_overbought: int = 80
    range_stoch_oversold: int = 20
    atr_multiplier_range: float = 0.6
    
    # پارامترهای استراتژی شکست باند بولینگر (Bollinger Squeeze) - (این بخش در نسخه قبلی جا افتاده بود)
    bollinger_squeeze_atr_multiplier: float = 1.5
    bollinger_squeeze_period: int = 20
    bollinger_squeeze_threshold: float = 0.8

@dataclass
class EngineConfig:
    """ پیکربندی کلی و جامع برای کل موتور تحلیلی. """
    timeframe_weights: Dict[str, float] = field(default_factory=lambda: {'1d': 3.0, '4h': 2.5, '1h': 2.0, '15m': 1.5, '5m': 1.0})
    min_strategy_score_threshold: float = 10.0 # آستانه امتیاز را به دلیل وجود پاداش‌ها بالاتر می‌بریم
    gemini_cooldown_seconds: int = 300
    
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    bonus_scores: BonusScores = field(default_factory=BonusScores)
    market_structure_config: Dict[str, Any] = field(default_factory=lambda: {"sensitivity": 7, "atr_multiplier": 1.5, "sr_cluster_strength": 0.02})

