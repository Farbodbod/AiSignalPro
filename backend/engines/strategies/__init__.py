# This file makes the 'strategies' directory a Python package
# and defines the final, world-class names for all strategy classes.

from .base_strategy import BaseStrategy

# Import all strategy classes from their respective files using their final, correct names
from .breakout import BreakoutHunter
from .chandelier_trend import ChandelierTrendRider
from .ema_crossover import EmaCrossoverStrategy
from .fib_structure import ConfluenceSniper
from .ichimoku_pro import IchimokuHybridPro
from .keltner_breakout import KeltnerMomentumBreakout
from .pivot_reversal import PivotConfluenceSniper
from .trend_rider import TrendRiderPro
from .volume_catalyst import VolumeCatalystPro
from .volume_reversal import WhaleReversal
from .vwap_reversion import VwapMeanReversion

# __all__ variable defines the public API of this package.
# This is the definitive list of our world-class strategies.
__all__ = [
    'BaseStrategy',
    'BreakoutHunter',
    'ChandelierTrendRider',
    'ConfluenceSniper',
    'EmaCrossoverStrategy',
    'IchimokuHybridPro',
    'KeltnerMomentumBreakout',
    'PivotConfluenceSniper',
    'TrendRiderPro',
    'VolumeCatalystPro',
    'WhaleReversal',
    'VwapMeanReversion',
]
