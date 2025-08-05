# engines/trend_analyzer.py (نسخه نهایی 2.1 - اصلاحیه دقیق و امن)

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# --- این توابع محاسباتی از کد اصلی شما هستند و بدون تغییر باقی می‌مانند ---
def calc_ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return df['close'].ewm(span=period, adjust=False).mean()

def calc_sma(df: pd.DataFrame, period: int = 50) -> pd.Series:
    return df['close'].rolling(window=period).mean()

def calc_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> (pd.Series, pd.Series):
    sma = calc_sma(df, period)
    std = df['close'].rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, lower

def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df_copy = df.copy()  # برای جلوگیری از تغییر در دیتافریم اصلی
    df_copy['tr'] = pd.concat([
        (df_copy['high'] - df_copy['low']).abs(),
        (df_copy['high'] - df_copy['close'].shift()).abs(),
        (df_copy['low'] - df_copy['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df_copy['+DM'] = np.where(
        (df_copy['high'] - df_copy['high'].shift()) > (df_copy['low'].shift() - df_copy['low']),
        np.maximum(df_copy['high'] - df_copy['high'].shift(), 0), 0
    )
    df_copy['-DM'] = np.where(
        (df_copy['low'].shift() - df_copy['low']) > (df_copy['high'] - df_copy['high'].shift()),
        np.maximum(df_copy['low'].shift() - df_copy['low'], 0), 0
    )

    tr14 = df_copy['tr'].rolling(window=period).sum().replace(0, np.nan)
    plus_dm14 = df_copy['+DM'].rolling(window=period).sum()
    minus_dm14 = df_copy['-DM'].rolling(window=period).sum()

    plus_di = 100 * plus_dm14 / tr14
    minus_di = 100 * minus_dm14 / tr14

    dx_denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * np.abs(plus_di - minus_di) / dx_denominator
    adx = dx.rolling(window=period).mean()

    return pd.DataFrame({
        'adx': adx,
        'plus_di': plus_di,
        'minus_di': minus_di
    })

def analyze_trend(df: pd.DataFrame, timeframe: str) -> Dict[str, Any]:
    # کپی کردن دیتافریم برای جلوگیری از تغییرات ناخواسته
    df_copy = df.copy()
    if len(df_copy) < 50:
        return {
            'error': 'Not enough data for trend analysis',
            'signal': 'Neutral',
            'adx': 0,
            'breakout': False,
            'volatility_spike': False
        }

    # محاسبات اندیکاتورها
    df_copy['ema20'] = calc_ema(df_copy, 20)
    df_copy['sma50'] = calc_sma(df_copy, 50)
    df_copy['upper_bb'], df_copy['lower_bb'] = calc_bollinger_bands(df_copy, 20)
    adx_df = calc_adx(df_copy, 14)
    df_copy = pd.concat([df_copy, adx_df], axis=1)

    df_copy['atr'] = calc_atr(df_copy, 14)
    df_copy['atr_sma'] = df_copy['atr'].rolling(window=20).mean()
    df_copy['volatility_spike'] = df_copy['atr'] > (df_copy['atr_sma'] * 2.5)
    df_copy['breakout'] = (
        (df_copy['close'] > df_copy['upper_bb'].shift(1)) &
        (df_copy['volume'] > df_copy['volume'].rolling(window=10).mean() * 1.5)
    )

    last = df_copy.iloc[-1]

    # --- ✨ اصلاح کلیدی و دقیق برای رفع خطا ✨ ---
    adx_series = df_copy['adx'].dropna()
    adx_value = adx_series.iloc[-1] if not adx_series.empty else 0

    # تشخیص فاز روند
    signal = "Neutral"
    is_uptrend = (last['close'] > last['ema20']) and (last['ema20'] > last['sma50'])
    is_downtrend = (last['close'] < last['ema20']) and (last['ema20'] < last['sma50'])

    # ترکیب ADX با تشخیص روند
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
        'volatility_spike': bool(last.get('volatility_spike', False)),
    }
