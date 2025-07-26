import pandas as pd
import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# =========================
# اندیکاتورهای پایه
# =========================

def calc_ma(df, period=14):
    return df['close'].rolling(window=period).mean()

def calc_ema(df, period=14):
    return df['close'].ewm(span=period, adjust=False).mean()

def calc_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calc_macd(df):
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist

def calc_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calc_bollinger(df, period=20):
    ma = calc_ma(df, period)
    std = df['close'].rolling(window=period).std()
    upper = ma + (2 * std)
    lower = ma - (2 * std)
    return upper, ma, lower

def calc_ichimoku(df):
    high_9 = df['high'].rolling(window=9).max()
    low_9 = df['low'].rolling(window=9).min()
    tenkan = (high_9 + low_9) / 2

    high_26 = df['high'].rolling(window=26).max()
    low_26 = df['low'].rolling(window=26).min()
    kijun = (high_26 + low_26) / 2

    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((df['high'].rolling(window=52).max() + df['low'].rolling(window=52).min()) / 2).shift(26)
    chikou = df['close'].shift(-26)

    return tenkan, kijun, senkou_a, senkou_b, chikou

def calc_vwap(df):
    return (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()

def calc_keltner(df, period=20):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    ema = typical_price.ewm(span=period, adjust=False).mean()
    atr = calc_atr(df, period)
    upper = ema + 2 * atr
    lower = ema - 2 * atr
    return upper, ema, lower

def calc_donchian(df, period=20):
    upper = df['high'].rolling(window=period).max()
    lower = df['low'].rolling(window=period).min()
    return upper, lower

def calc_fibonacci_levels(df):
    max_price = df['high'].rolling(window=60).max()
    min_price = df['low'].rolling(window=60).min()
    diff = max_price - min_price
    levels = {
        'fib_0.236': max_price - 0.236 * diff,
        'fib_0.382': max_price - 0.382 * diff,
        'fib_0.5': max_price - 0.5 * diff,
        'fib_0.618': max_price - 0.618 * diff,
        'fib_0.786': max_price - 0.786 * diff,
    }
    return levels

def calc_stochastic(df, k_period=14, d_period=3):
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    k = 100 * ((df['close'] - low_min) / (high_max - low_min + 1e-10))
    d = k.rolling(window=d_period).mean()
    return k, d

# =========================
# لیست اندیکاتورها
# =========================

INDICATORS = {
    'ma': lambda df: calc_ma(df),
    'ema': lambda df: calc_ema(df),
    'rsi': lambda df: calc_rsi(df),
    'atr': lambda df: calc_atr(df),
    'vwap': lambda df: calc_vwap(df),
    'boll_upper': lambda df: calc_bollinger(df)[0],
    'boll_middle': lambda df: calc_bollinger(df)[1],
    'boll_lower': lambda df: calc_bollinger(df)[2],
    'donchian_upper': lambda df: calc_donchian(df)[0],
    'donchian_lower': lambda df: calc_donchian(df)[1],
    'keltner_upper': lambda df: calc_keltner(df)[0],
    'keltner_middle': lambda df: calc_keltner(df)[1],
    'keltner_lower': lambda df: calc_keltner(df)[2],
    'fib_0.236': lambda df: calc_fibonacci_levels(df)['fib_0.236'],
    'fib_0.382': lambda df: calc_fibonacci_levels(df)['fib_0.382'],
    'fib_0.5': lambda df: calc_fibonacci_levels(df)['fib_0.5'],
    'fib_0.618': lambda df: calc_fibonacci_levels(df)['fib_0.618'],
    'fib_0.786': lambda df: calc_fibonacci_levels(df)['fib_0.786'],
    'macd_line': lambda df: calc_macd(df)[0],
    'macd_signal': lambda df: calc_macd(df)[1],
    'macd_hist': lambda df: calc_macd(df)[2],
    'tenkan': lambda df: calc_ichimoku(df)[0],
    'kijun': lambda df: calc_ichimoku(df)[1],
    'senkou_a': lambda df: calc_ichimoku(df)[2],
    'senkou_b': lambda df: calc_ichimoku(df)[3],
    'chikou': lambda df: calc_ichimoku(df)[4],
    'stoch_k': lambda df: calc_stochastic(df)[0],
    'stoch_d': lambda df: calc_stochastic(df)[1],
}

# =========================
# تابع محاسبه کلی
# =========================

def calculate_indicators(df: pd.DataFrame, selected: List[str] = None) -> pd.DataFrame:
    df_out = df.copy()
    macd_cache, ichimoku_cache, boll_cache = None, None, None

    for name, func in INDICATORS.items():
        if selected and name not in selected:
            continue
        try:
            if name.startswith('macd_'):
                if macd_cache is None:
                    macd_cache = calc_macd(df_out)
                idx = ['macd_line', 'macd_signal', 'macd_hist'].index(name)
                df_out[name] = macd_cache[idx]
            elif name.startswith('tenkan') or name.startswith('kijun') or name.startswith('senkou') or name.startswith('chikou'):
                if ichimoku_cache is None:
                    ichimoku_cache = calc_ichimoku(df_out)
                ichi_map = {
                    'tenkan': 0,
                    'kijun': 1,
                    'senkou_a': 2,
                    'senkou_b': 3,
                    'chikou': 4
                }
                df_out[name] = ichimoku_cache[ichi_map[name]]
            elif name.startswith('boll_'):
                if boll_cache is None:
                    boll_cache = calc_bollinger(df_out)
                boll_map = {
                    'boll_upper': 0,
                    'boll_middle': 1,
                    'boll_lower': 2,
                }
                df_out[name] = boll_cache[boll_map[name]]
            else:
                df_out[name] = func(df_out)
        except Exception as e:
            logger.warning(f"[!] خطا در محاسبه اندیکاتور {name}: {e}")
    return df_out
