# This file makes the 'strategies' directory a Python package
# and defines the standard, world-class names for all strategy classes.

from .base_strategy import BaseStrategy

# Import all strategy classes from their respective files using their final, upgraded names
from .breakout import BreakoutHunter
from .chandelier_trend import ChandelierTrendRider
from .confluence_sniper import ConfluenceSniper
from .divergence_sniper import DivergenceSniperPro
from .ema_cross import EmaCrossoverStrategy # نام این استراتژی از قبل مناسب بود
from .fib_structure import FibStructureStrategy # نام این استراتژی از قبل مناسب بود
from .ichimoku_hybrid import IchimokuHybridPro
from .keltner_breakout import KeltnerMomentumBreakout
from .mean_reversion import MeanReversionStrategy # این نام می‌تواند باقی بماند یا ارتقا یابد
from .pivot_reversal import PivotReversalStrategy, PivotConfluenceSniper
from .trend_rider import TrendRiderPro
from .volume_catalyst import VolumeCatalystPro
from .vwap_reversion import VwapReversionPro, VwapBouncer
from .whale_reversal import WhaleReversal

# __all__ variable defines the public API of this package
__all__ = [
    'BaseStrategy',
    'BreakoutHunter',
    'ChandelierTrendRider',
    'ConfluenceSniper',
    'DivergenceSniperPro',
    'EmaCrossoverStrategy',
    'FibStructureStrategy',
    'IchimokuHybridPro',
    'KeltnerMomentumBreakout',
    'MeanReversionStrategy',
    'PivotReversalStrategy',
    'PivotConfluenceSniper',
    'TrendRiderPro',
    'VolumeCatalystPro',
    'VwapReversionPro',
    'VwapBouncer',
    'WhaleReversal',
]
