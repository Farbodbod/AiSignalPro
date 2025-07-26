# engines/trend_analyzer.py

import pandas as pd
import numpy as np
from typing import Dict, Any
from scipy.fft import fft
import joblib

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

    # Avoid division by zero
    tr14 = tr14.replace(0, np.nan)

    plus_di = 100 * plus_dm14 / tr14
    minus_di = 100 * minus_dm14 / tr14
    
    # Avoid division by zero
    dx_denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * abs(plus_di - minus_di) / dx_denominator
    
    adx = dx.rolling(period).mean()
    return pd.DataFrame({'adx': adx, 'plus_di': plus_di, 'minus_di': minus_di})

def slope_angle(series, period=5):
    if len(series) < period: return 0
    # ensure we have a non-zero denominator
    dy = series.iloc[-1] - series.iloc[-period]
    dx = period
    return np.degrees(np.arctan(dy / dx))

def fft_cycle_strength(close_series, top_n=3):
    if len(close_series) < top_n: return 0
    y = close_series - close_series.mean()
    fft_vals = np.abs(fft(y))
    fft_power = np.sum(fft_vals[1:top_n+1]) # Exclude the DC component
    return fft_power

def analyze_trend(df: pd.DataFrame, timeframe: str, ml_model: Any = None) -> Dict[str, Any]:
    df = df.copy()
    if len(df) < 200: return {'error': 'Not enough data'}

    df['ema20'] = calc_ema(df, 20)
    df['ema100'] = calc_ema(df, 100)
    df['sma50'] = calc_sma(df, 50)
    df['sma200'] = calc_sma(df, 200)
    df['upper_bb'], df['lower_bb'] = calc_bollinger_bands(df, 20)
    adx_df = calc_adx(df, 14)
    df = pd.concat([df, adx_df], axis=1)
    df['vol_ma'] = df['volume'].rolling(10).mean()
    df['vol_trend'] = df['vol_ma'].diff()
    df['slope_ema'] = df['ema20'].rolling(5).apply(slope_angle, raw=False)
    df['slope_sma'] = df['sma50'].rolling(5).apply(slope_angle, raw=False)
    df['breakout'] = (df['close'] > df['upper_bb']) & (df['adx'] > 25)
    df['fakeout'] = (df['close'] > df['upper_bb']) & (df['adx'] < 20)
    df['fft_strength'] = df['close'].rolling(64).apply(fft_cycle_strength, raw=True)

    def get_trend_label(row):
        if row['adx'] > 25 and row['slope_ema'] > 20:
            if row['ema20'] > row['sma50'] and row['close'] > row['ema20']: return 'StrongConfirmedUptrend'
            elif row['ema20'] < row['sma50'] and row['close'] < row['ema20']: return 'StrongConfirmedDowntrend'
        elif row['adx'] < 20 and abs(row['slope_ema']) < 5: return 'SidewaysLowVol'
        elif row['fakeout']: return 'FakeBreakout'
        return 'Neutral'

    df['trend_label'] = df.apply(get_trend_label, axis=1)

    if ml_model:
        feature_cols = ['adx', 'slope_ema', 'fft_strength', 'vol_trend']
        latest = df[feature_cols].fillna(0).tail(1)
        prediction = ml_model.predict(latest)[0]
        df['ml_forecast'] = prediction
    else:
        df['ml_forecast'] = None

    last = df.iloc[-1].to_dict()
    # Return a dictionary of JSON-serializable types
    return {
        'timeframe': timeframe,
        'signal': last.get('trend_label'),
        'ml_forecast': last.get('ml_forecast'),
        'adx': round(last.get('adx', 0), 2),
        'slope': round(last.get('slope_ema', 0), 2),
        'volume_trend': round(last.get('vol_trend', 0), 2),
        'cycle_strength': round(last.get('fft_strength', 0), 2),
        'breakout': bool(last.get('breakout', False)),
        'fakeout': bool(last.get('fakeout', False)),
    }

def multi_tf_analysis(tf_data: Dict[str, pd.DataFrame], ml_model_path: str = None):
    results = {}
    ml_model = None
    if ml_model_path:
        try:
            ml_model = joblib.load(ml_model_path)
        except FileNotFoundError:
            print(f"Warning: ML model file not found at {ml_model_path}")
        except Exception as e:
            print(f"Warning: Could not load ML model. Error: {e}")

    for tf, df in tf_data.items():
        if not isinstance(df, pd.DataFrame) or len(df) < 100:
            continue
        result = analyze_trend(df, tf, ml_model)
        results[tf] = result
    return results
