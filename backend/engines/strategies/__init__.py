# This file makes the 'strategies' directory a Python package
# and defines the final, world-class names for all strategy classes,
# importing them from the correct filenames as per the final project audit.

from .base_strategy import BaseStrategy

# Import all strategy classes from their respective files using their final, correct names
# This list is now 100% synchronized with your final, verified file structure.
from .breakout import BreakoutHunter
from .chandelier_trend import ChandelierTrendRider
from .divergence_sniper import DivergenceSniperPro
from .ema_crossover import EmaCrossoverStrategy
from .fib_structure import ConfluenceSniper
from .ichimoku_pro import IchimokuHybridPro
from .keltner_breakout import KeltnerMomentumBreakout
from .pivot_reversal import PivotConfluenceSniper
from .pullback_sniper import PullbackSniperPro
from .range_hunter import RangeHunterPro # ✅ ADDED: The new Range Hunter is now imported.
from .trend_rider import TrendRiderPro
from .volume_catalyst import VolumeCatalystPro
from .volume_reversal import WhaleReversal
from .vwap_reversion import VwapMeanReversion

# This is the definitive list of our world-class strategies.
__all__ = [
    'BaseStrategy',
    'BreakoutHunter',
    'ChandelierTrendRider',
    'DivergenceSniperPro',
    'EmaCrossoverStrategy',
    'ConfluenceSniper',
    'IchimokuHybridPro',
    'KeltnerMomentumBreakout',
    'PivotConfluenceSniper',
    'PullbackSniperPro',
    'RangeHunterPro', # ✅ ADDED: The new Range Hunter is now registered.
    'TrendRiderPro',
    'VolumeCatalystPro',
    'WhaleReversal',
    'VwapMeanReversion',
]
