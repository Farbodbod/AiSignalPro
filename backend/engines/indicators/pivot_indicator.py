import pandas as pd
import logging
from .base import BaseIndicator

logger = logging.getLogger(__name__)

class PivotPointIndicator(BaseIndicator):
    """
    ✨ UPGRADE v2.0 ✨
    - Constructor standardized to use **kwargs.
    """
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        if len(df) < 2:
            raise ValueError("Pivot Points require at least 2 data points.")
        self.method = self.params.get('method', 'standard')
        self.pivots = {}

    def calculate(self) -> pd.DataFrame:
        prev_candle = self.df.iloc[-2]
        high = prev_candle['high']; low = prev_candle['low']; close = prev_candle['close']
        pivot = (high + low + close) / 3
        
        if self.method == 'fibonacci':
            r = high - low
            self.pivots = {'R3': pivot + r, 'R2': pivot + (r*0.618), 'R1': pivot + (r*0.382), 'P': pivot, 'S1': pivot - (r*0.382), 'S2': pivot - (r*0.618), 'S3': pivot - r}
        elif self.method == 'camarilla':
            r = high - low
            self.pivots = {'R4': close + (r*1.1/2), 'R3': close + (r*1.1/4), 'R2': close + (r*1.1/6), 'R1': close + (r*1.1/12), 'P': pivot, 'S1': close - (r*1.1/12), 'S2': close - (r*1.1/6), 'S3': close - (r*1.1/4), 'S4': close - (r*1.1/2)}
        else: # standard
            r1 = (2*pivot) - low; s1 = (2*pivot) - high; r2 = pivot + (high-low); s2 = pivot - (high-low); r3 = high + 2*(pivot-low); s3 = low - 2*(high-pivot)
            self.pivots = {'R3': r3, 'R2': r2, 'R1': r1, 'P': pivot, 'S1': s1, 'S2': s2, 'S3': s3}
        return self.df

    def analyze(self) -> dict:
        if not self.pivots: self.calculate()
        current_price = self.df.iloc[-1]['close']
        position = "Unknown"
        sorted_levels = sorted(self.pivots.items(), key=lambda item: item[1])
        above = next((item for item in sorted_levels if item[1] > current_price), None)
        below = next((item for item in reversed(sorted_levels) if item[1] < current_price), None)
        
        if above and below: position = f"Between {below[0]} and {above[0]}"
        elif above: position = f"Below all pivots, approaching {above[0]}"
        elif below: position = f"Above all pivots, testing {below[0]}"
        
        return {"levels": self.pivots, "position": position}
