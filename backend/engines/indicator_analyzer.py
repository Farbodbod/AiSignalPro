# engines/indicator_analyzer.py (نسخه نهایی 3.1 - بازبینی شده)

import pandas as pd
import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """ تمام اندیکاتورهای مورد نیاز برای استراتژی‌های مختلف را محاسبه می‌کند. """
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def calculate_all(self) -> pd.DataFrame:
        try:
            # --- اندیکاتورهای اصلی ---
            self.df['atr'] = self._calc_atr()
            self.df['rsi'] = self._calc_rsi()
            self.df['macd_line'], self.df['macd_signal'], self.df['macd_hist'] = self._calc_macd()
            self.df['stoch_k'], self.df['stoch_d'] = self._calc_stochastic()
            self.df['ema_50'] = self.df['close'].ewm(span=50, adjust=False).mean()
            self.df['sma_200'] = self.df['close'].rolling(window=200).mean()

            # --- اندیکاتورهای تخصصی ---
            self.df['boll_upper'], self.df['boll_middle'], self.df['boll_lower'] = self._calc_bollinger()
            self.df['boll_width'] = (self.df['boll_upper'] - self.df['boll_lower']) / self.df['boll_middle']
            (self.df['tenkan'], self.df['kijun'], self.df['senkou_a'], 
             self.df['senkou_b'], self.df['chikou']) = self._calc_ichimoku()
            self.df['vwap'] = self._calc_vwap()
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
        return self.df

    def _calc_atr(self, period: int = 14) -> pd.Series:
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift())
        low_close = np.abs(self.df['low'] - self.df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calc_rsi(self, period: int = 14) -> pd.Series:
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / (loss + 1e-12)
        return 100 - (100 / (1 + rs))

    def _calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist
        
    def _calc_stochastic(self, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        low_min = self.df['low'].rolling(window=k_period).min()
        high_max = self.df['high'].rolling(window=k_period).max()
        k = 100 * ((self.df['close'] - low_min) / (high_max - low_min + 1e-12))
        d = k.rolling(window=d_period).mean()
        return k, d
        
    def _calc_bollinger(self, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ma = self.df['close'].rolling(window=period).mean()
        std = self.df['close'].rolling(window=period).std()
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        return upper, ma, lower
        
    def _calc_ichimoku(self) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        high_9 = self.df['high'].rolling(window=9).max()
        low_9 = self.df['low'].rolling(window=9).min()
        tenkan = (high_9 + low_9) / 2
        high_26 = self.df['high'].rolling(window=26).max()
        low_26 = self.df['low'].rolling(window=26).min()
        kijun = (high_26 + low_26) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((self.df['high'].rolling(window=52).max() + self.df['low'].rolling(window=52).min()) / 2).shift(26)
        chikou = self.df['close'].shift(-26)
        return tenkan, kijun, senkou_a, senkou_b, chikou
        
    def _calc_vwap(self) -> pd.Series:
        q = self.df['volume'] * (self.df['high'] + self.df['low'] + self.df['close']) / 3
        return q.cumsum() / self.df['volume'].cumsum()
