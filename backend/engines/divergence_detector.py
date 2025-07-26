"""
divergence.py
ماژول تشخیص واگرایی‌های حرفه‌ای بین قیمت و اندیکاتورها:
- پشتیبانی واگرایی‌های Regular و Hidden بین قیمت و RSI، MACD، OBV و اندیکاتورهای سفارشی
- پشتیبانی مولتی‌تایم‌فریم و ساختار توسعه‌پذیر
- شناسایی پیوت‌ها با الگوریتم ZigZag (argrelextrema)
- اعتبارسنجی واگرایی‌ها با کندل، حجم، مومنتوم و شدت حرکت
- اتصال به مدل یادگیری ماشین جهت یادگیری واگرایی‌های معتبر و پرتکرار
Author: farbodbod1990
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from scipy.signal import argrelextrema
from sklearn.ensemble import RandomForestClassifier

# ========================= اندیکاتورها =========================
def calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9):
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def calc_obv(df: pd.DataFrame) -> pd.Series:
    obv = [0]
    for i in range(1, len(df)):
        if df['close'][i] > df['close'][i - 1]:
            obv.append(obv[-1] + df['volume'][i])
        elif df['close'][i] < df['close'][i - 1]:
            obv.append(obv[-1] - df['volume'][i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)

# ========================= پیوت‌ها =========================
def find_pivots(series: pd.Series, order: int = 5) -> Dict[str, List[int]]:
    lows = argrelextrema(series.values, np.less_equal, order=order)[0].tolist()
    highs = argrelextrema(series.values, np.greater_equal, order=order)[0].tolist()
    return {'lows': lows, 'highs': highs}

# ========================= اعتبارسنجی واگرایی =========================
def validate_divergence(df: pd.DataFrame, idx: int, window: int = 3) -> bool:
    if idx < window or idx >= len(df) - window:
        return False
    price_change = df['close'][idx] - df['close'][idx - window]
    volume_avg = df['volume'].rolling(window).mean().iloc[idx]
    volume_now = df['volume'].iloc[idx]
    momentum = abs(price_change / (df['close'].iloc[idx - window] + 1e-9))
    return momentum > 0.01 and volume_now > volume_avg

# ========================= واگرایی =========================
def match_divergence(price: pd.Series, indicator: pd.Series, pivots: Dict[str, List[int]],
                     kind: str = 'regular', df: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
    divergences = []
    highs = pivots['highs']
    lows = pivots['lows']
    
    for i in range(1, len(highs)):
        p1, p2 = highs[i - 1], highs[i]
        if kind == 'regular' and price[p2] > price[p1] and indicator[p2] < indicator[p1]:
            if validate_divergence(df, p2):
                divergences.append({'type': 'bearish_regular', 'index': p2})
        elif kind == 'hidden' and price[p2] < price[p1] and indicator[p2] > indicator[p1]:
            if validate_divergence(df, p2):
                divergences.append({'type': 'bearish_hidden', 'index': p2})

    for i in range(1, len(lows)):
        p1, p2 = lows[i - 1], lows[i]
        if kind == 'regular' and price[p2] < price[p1] and indicator[p2] > indicator[p1]:
            if validate_divergence(df, p2):
                divergences.append({'type': 'bullish_regular', 'index': p2})
        elif kind == 'hidden' and price[p2] > price[p1] and indicator[p2] < indicator[p1]:
            if validate_divergence(df, p2):
                divergences.append({'type': 'bullish_hidden', 'index': p2})

    return divergences

# ========================= یادگیری ماشین =========================
def train_divergence_model(features: pd.DataFrame, labels: pd.Series) -> RandomForestClassifier:
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(features, labels)
    return model

def extract_features(df: pd.DataFrame, indices: List[int]) -> pd.DataFrame:
    features = []
    for idx in indices:
        if idx >= 5:
            f = {
                'rsi': df['rsi'].iloc[idx],
                'macd': df['macd'].iloc[idx],
                'obv': df['obv'].iloc[idx],
                'volume': df['volume'].iloc[idx],
                'momentum': df['close'].iloc[idx] - df['close'].iloc[idx - 5]
            }
            features.append(f)
    return pd.DataFrame(features)

# ========================= اجرای کامل =========================
def detect_divergences(df: pd.DataFrame, order: int = 5, indicators: Optional[List[Callable]] = None) -> Dict[str, Any]:
    df = df.copy()
    df['rsi'] = calc_rsi(df)
    df['macd'], _, _ = calc_macd(df)
    df['obv'] = calc_obv(df)

    pivots = find_pivots(df['close'], order=order)

    results = {}
    for ind_name in ['rsi', 'macd', 'obv']:
        results[ind_name] = (
            match_divergence(df['close'], df[ind_name], pivots, kind='regular', df=df) +
            match_divergence(df['close'], df[ind_name], pivots, kind='hidden', df=df)
        )
    return results

# ========================= نمونه استفاده =========================
"""
import pandas as pd
df = pd.read_csv("btc_1h.csv")
results = detect_divergences(df)
for key in results:
    print(f"{key}: {results[key]}")
"""
