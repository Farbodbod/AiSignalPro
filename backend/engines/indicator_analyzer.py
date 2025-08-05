# engines/indicator_analyzer.py (نسخه نهایی 4.0 - جهانی)

import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    """ 
    موتور جامع و بهینه برای محاسبه تمام اندیکاتورهای تکنیکال مورد نیاز 
    در سطح حرفه‌ای و جهانی برای پروژه AiSignalPro.
    طراحی شده بر اساس نقشه راه و بازبینی کارشناسی.
    """
    def __init__(self, df: pd.DataFrame):
        # اطمینان از وجود ستون‌های لازم
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame must contain all required columns: {required_cols}")
        self.df = df.copy()

    def calculate_all(self) -> pd.DataFrame:
        """ تمام اندیکاتورهای تعریف‌شده را محاسبه و به دیتافریم اضافه می‌کند. """
        try:
            # --- اندیکاتورهای اصلی و پراستفاده ---
            self.df['atr'] = self._calc_atr()
            self.df['rsi'] = self._calc_rsi()
            self.df['macd_line'], self.df['macd_signal'], self.df['macd_hist'] = self._calc_macd()
            self.df['stoch_k'], self.df['stoch_d'] = self._calc_stochastic()
            
            # --- ✨ جدید: اندیکاتورهای قدرت روند ---
            self.df['adx'], self.df['di_plus'], self.df['di_minus'] = self._calc_adx_dmi()
            
            # --- ✨ جدید: اندیکاتورهای حجمی ---
            self.df['obv'] = self._calc_obv()

            # --- میانگین‌های متحرک ---
            self.df['ema_50'] = self._calc_ema(50)
            self.df['sma_200'] = self._calc_ma(200)

            # --- کانال‌های نوسان ---
            self.df['boll_upper'], self.df['boll_middle'], self.df['boll_lower'] = self._calc_bollinger()
            
            # --- ✨ ایچیموکو با محاسبات اصلاح شده ---
            (self.df['tenkan'], self.df['kijun'], self.df['senkou_a'], 
             self.df['senkou_b'], self.df['chikou']) = self._calc_ichimoku()
             
            # --- سایر اندیکاتورها ---
            self.df['vwap'] = self._calc_vwap()
            fib_levels = self._calc_fibonacci_levels()
            for name, series in fib_levels.items():
                self.df[name] = series

            # --- ✨ جدید: حذف ردیف‌های ناقص برای اطمینان از سلامت داده ---
            # این کار باعث می‌شود که فقط کندل‌هایی که تمام داده‌های اندیکاتور را دارند باقی بمانند.
            initial_rows = len(self.df)
            self.df.dropna(inplace=True)
            logger.info(f"Indicator calculation complete. Dropped {initial_rows - len(self.df)} rows with NaN values.")

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
        
        return self.df

    # --- توابع محاسبه پایه (کامل و بازبینی شده) ---

    def _calc_ma(self, period: int) -> pd.Series:
        return self.df['close'].rolling(window=period, min_periods=period).mean()

    def _calc_ema(self, period: int) -> pd.Series:
        return self.df['close'].ewm(span=period, adjust=False).mean()

    def _calc_atr(self, period: int = 14) -> pd.Series:
        high_low = self.df['high'] - self.df['low']
        high_close = np.abs(self.df['high'] - self.df['close'].shift())
        low_close = np.abs(self.df['low'] - self.df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calc_rsi(self, period: int = 14) -> pd.Series:
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / (avg_loss + 1e-12)
        return 100 - (100 / (1 + rs))

    def _calc_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = self._calc_ema(fast)
        ema_slow = self._calc_ema(slow)
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
        ma = self._calc_ma(period)
        std = self.df['close'].rolling(window=period).std()
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        return upper, ma, lower
        
    def _calc_ichimoku(self) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
        # محاسبات پایه
        high_9 = self.df['high'].rolling(window=9).max()
        low_9 = self.df['low'].rolling(window=9).min()
        tenkan = (high_9 + low_9) / 2
        
        high_26 = self.df['high'].rolling(window=26).max()
        low_26 = self.df['low'].rolling(window=26).min()
        kijun = (high_26 + low_26) / 2
        
        high_52 = self.df['high'].rolling(window=52).max()
        low_52 = self.df['low'].rolling(window=52).min()
        
        # --- ✨ اصلاح محاسبات Senkou و Chikou بر اساس استاندارد جهانی ---
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((high_52 + low_52) / 2).shift(26)
        
        # Chikou دیگر به آینده شیفت داده نمی‌شود تا از خطای lookahead جلوگیری شود.
        # در موتور استراتژی، قیمت فعلی با قیمت ۲۶ دوره قبل مقایسه خواهد شد.
        chikou = self.df['close'] 
        return tenkan, kijun, senkou_a, senkou_b, chikou
        
    def _calc_vwap(self) -> pd.Series:
        q = self.df['volume'] * (self.df['high'] + self.df['low'] + self.df['close']) / 3
        return q.cumsum() / self.df['volume'].cumsum()
        
    def _calc_fibonacci_levels(self, period: int = 60) -> Dict[str, pd.Series]:
        rolling_max = self.df['high'].rolling(window=period).max()
        rolling_min = self.df['low'].rolling(window=period).min()
        diff = rolling_max - rolling_min
        return {
            'fib_0.236': rolling_max - 0.236 * diff,
            'fib_0.382': rolling_max - 0.382 * diff,
            'fib_0.500': rolling_max - 0.500 * diff,
            'fib_0.618': rolling_max - 0.618 * diff
        }

    def _calc_obv(self) -> pd.Series:
        obv = np.where(self.df['close'] > self.df['close'].shift(), self.df['volume'], 
              np.where(self.df['close'] < self.df['close'].shift(), -self.df['volume'], 0)).cumsum()
        return pd.Series(obv, index=self.df.index)

    def _calc_adx_dmi(self, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        df = self.df.copy()
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = np.abs(df['high'] - df['close'].shift())
        df['l-pc'] = np.abs(df['low'] - df['close'].shift())
        df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
        
        df['dmp'] = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']), np.maximum(df['high'] - df['high'].shift(), 0), 0)
        df['dmn'] = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()), np.maximum(df['low'].shift() - df['low'], 0), 0)

        atr = df['tr'].ewm(span=period, adjust=False).mean()
        di_plus = 100 * df['dmp'].ewm(span=period, adjust=False).mean() / atr
        di_minus = 100 * df['dmn'].ewm(span=period, adjust=False).mean() / atr
        
        dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus + 1e-12)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx, di_plus, di_minus
