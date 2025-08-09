# This file makes the 'strategies' directory a Python package
# and defines the standard, world-class names for all strategy classes,
# importing them from the correct filenames as per the final project structure.

from .base_strategy import BaseStrategy

# Import all strategy classes from their respective files using their final, upgraded names
# The module names MUST EXACTLY MATCH the python filenames.

from .breakout import BreakoutHunter
from .chandelier_trend import ChandelierTrendRider
from .divergence_sniper import DivergenceSniperPro
from .ema_crossover import EmaCrossoverStrategy
from .fib_structure import ConfluenceSniper
from .ichimoku_pro import IchimokuHybridPro  # ✨ FIX: Corrected filename from ichimoku_hybrid to ichimoku_pro
from .keltner_breakout import KeltnerMomentumBreakout
from .mean_reversion import MeanReversionStrategy # Assuming this is a separate, older strategy
from .pivot_reversal import PivotConfluenceSniper
from .trend_rider import TrendRiderPro
from .volume_catalyst import VolumeCatalystPro
from .volume_reversal import WhaleReversal
from .vwap_reversion import VwapMeanReversion # ✨ REFINEMENT: Sourcing the world-class version from the correct file

# __all__ variable defines the public API of this package for 'from .strategies import *'
__all__ = [
    'BaseStrategy',
    'BreakoutHunter',
    'ChandelierTrendRider',
    'ConfluenceSniper',
    'DivergenceSniperPro',
    'EmaCrossoverStrategy',
    'IchimokuHybridPro',
    'KeltnerMomentumBreakout',
    'MeanReversionStrategy',
    'PivotConfluenceSniper',
    'TrendRiderPro',
    'VolumeCatalystPro',
    'WhaleReversal',
    'VwapMeanReversion',
]
