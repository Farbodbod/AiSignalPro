# This file makes the 'strategies' directory a Python package
# and defines the final, world-class names for all strategy classes.

from .base_strategy import BaseStrategy

# Import all strategy classes from their respective files using their final names
from .breakout import BreakoutHunter
from .chandelier_trend import ChandelierTrendRider
from .ema_cross import EmaCrossoverStrategy
from .fib_structure import ConfluenceSniper
from .ichimoku_hybrid import IchimokuHybridPro
from .keltner_breakout import KeltnerMomentumBreakout
from .mean_reversion import VwapMeanReversion
from .pivot_reversal import PivotConfluenceSniper
from .trend_rider import TrendRiderPro
from .volume_catalyst import VolumeCatalystPro
from .volume_reversal import WhaleReversal

# __all__ variable defines the public API of this package for 'from .strategies import *'
__all__ = [
    'BaseStrategy',
    'BreakoutHunter',
    'ChandelierTrendRider',
    'EmaCrossoverStrategy',
    'ConfluenceSniper',
    'IchimokuHybridPro',
    'KeltnerMomentumBreakout',
    'VwapMeanReversion',
    'PivotConfluenceSniper',
    'TrendRiderPro',
    'VolumeCatalystPro',
    'WhaleReversal',
]
