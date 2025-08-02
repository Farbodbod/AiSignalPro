# engines/trend_analyzer.py (نسخه نهایی با تشخیص دقیق بازار رنج)

import pandas as pd
import numpy as np
from typing import Dict, Any
from scipy.fft import fft
import joblib

import logging
logger = logging.getLogger(__name__)

def calc_ema(df, period=20):
    return df['close'].ewm(span=period, adjust=False).mean()

def calc_sma(df, period=50):
    return df['close'].rolling(window=period).mean()

def calc_bollinger_bands(df, period=20, std_dev=2):
    sma = calc_sma(df, period)
    std = df['close'].rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, lower

def calc_adx(df, period=14):
    df = df.copy()
    df['tr'] = pd.concat([
        abs(df['high'] - df['low']),
        abs(df['high'] - df['close'].shift()),
        abs(df['low'] - df['close'].shift())
    ], axis=1).max(axis=1)
    df['+DM'] = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']),
                         np.maximum(df['high'] - df['high'].shift(), 0), 0)
    df['-DM'] = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()),
                         np.maximum(df['low'].shift() - df['low'], 0), 0)

    tr14 = df['tr'].rolling(period).sum()
    plus_dm14 = df['+DM'].rolling(period).sum()
    minus_dm14 = df['-DM'].rolling(period).sum()
    
    tr14 = tr14.replace(0, np.nan)
    plus_di = 100 * plus_dm14 / tr14
    minus_di = 100 * minus_dm14 / tr14
    
    dx_denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * abs(plus_di - minus_di) / dx_denominator
    
    adx = dx.rolling(period).mean()
    return pd.DataFrame({'adx': adx, 'plus_di': plus_di, 'minus_di': minus_di})

def analyze_trend(df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    df = df.copy()
    if len(df) < 50: return {'error': 'Not enough data for trend analysis'}

    df['ema20'] = calc_ema(df, 20)
    df['sma50'] = calc_sma(df, 50)
    df['upper_bb'], df['lower_bb'] = calc_bollinger_bands(df, 20)
    adx_df = calc_adx(df, 14)
    df = pd.concat([df, adx_df], axis=1)
    df['breakout'] = (df['close'] > df['upper_bb'].shift(1)) & (df['volume'] > df['volume'].rolling(10).mean() * 1.5)
    
    last = df.iloc[-1]
    
    signal = "Neutral"
    adx_value = last.get('adx', 0)
    
    is_uptrend = last['close'] > last['ema20'] and last['ema20'] > last['sma50']
    is_downtrend = last['close'] < last['ema20'] and last['ema20'] < last['sma50']

    if adx_value > 25:
        if is_uptrend:
            signal = "StrongUptrend"
        elif is_downtrend:
            signal = "StrongDowntrend"
    elif adx_value < 20:
        signal = "RangingMarket"
    else:
        if is_uptrend:
            signal = "WeakUptrend"
        elif is_downtrend:
            signal = "WeakDowntrend"

    return {
        'timeframe': timeframe,
        'signal': signal,
        'adx': round(adx_value, 2) if pd.notna(adx_value) else 0,
        'breakout': bool(last.get('breakout', False)),
    }
