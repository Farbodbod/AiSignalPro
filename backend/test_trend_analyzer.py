# test_trend_analyzer.py

import pandas as pd
import numpy as np
import os
import django

# راه‌اندازی اولیه برای دسترسی به موتورها
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_app.settings')
django.setup()

# وارد کردن موتور تحلیل روند از پروژه شما
from engines.trend_analyzer import analyze_trend

def create_market_data(trend_type: str, num_candles: int = 100) -> pd.DataFrame:
    """یک دیتافریم شبیه‌سازی شده برای تست ایجاد می‌کند."""
    base_price = 1000
    data = []
    
    for i in range(num_candles):
        timestamp = int(pd.Timestamp.now().timestamp() * 1000) - (num_candles - i) * 3600 * 1000 # کندل‌های ۱ ساعته
        noise = np.random.uniform(-5, 5)
        
        if trend_type == 'uptrend':
            open_price = base_price + i * 2 + noise
            close_price = open_price + np.random.uniform(1, 10)
        elif trend_type == 'downtrend':
            open_price = base_price - i * 2 + noise
            close_price = open_price - np.random.uniform(1, 10)
        else: # neutral
            open_price = base_price + np.random.uniform(-20, 20)
            close_price = open_price + noise

        high_price = max(open_price, close_price) + np.random.uniform(0, 5)
        low_price = min(open_price, close_price) - np.random.uniform(0, 5)
        volume = np.random.uniform(100, 1000)
        
        data.append([timestamp, open_price, high_price, low_price, close_price, volume])

    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def run_tests():
    """تست‌ها را اجرا کرده و نتایج را نمایش می‌دهد."""
    print("--- Running Trend Analyzer Tests ---")
    
    # ۱. تست بازار صعودی (Uptrend)
    print("\n[TEST 1] Analyzing a strong UPTREND...")
    uptrend_df = create_market_data('uptrend')
    uptrend_result = analyze_trend(uptrend_df.copy(), timeframe='1h')
    print("Result:", uptrend_result)
    if 'Uptrend' in uptrend_result.get('signal', ''):
        print("✅ PASSED: Correctly identified Uptrend.")
    else:
        print("❌ FAILED: Did not identify Uptrend.")

    # ۲. تست بازار نزولی (Downtrend)
    print("\n[TEST 2] Analyzing a strong DOWNTREND...")
    downtrend_df = create_market_data('downtrend')
    downtrend_result = analyze_trend(downtrend_df.copy(), timeframe='1h')
    print("Result:", downtrend_result)
    if 'Downtrend' in downtrend_result.get('signal', ''):
        print("✅ PASSED: Correctly identified Downtrend.")
    else:
        print("❌ FAILED: Did not identify Downtrend.")
        
    # ۳. تست بازار خنثی (Neutral)
    print("\n[TEST 3] Analyzing a NEUTRAL market...")
    neutral_df = create_market_data('neutral')
    neutral_result = analyze_trend(neutral_df.copy(), timeframe='1h')
    print("Result:", neutral_result)
    if 'Neutral' in neutral_result.get('signal', ''):
        print("✅ PASSED: Correctly identified Neutral market.")
    else:
        print("❌ FAILED: Did not identify Neutral market.")
        
    print("\n--- Tests Finished ---")


if __name__ == "__main__":
    run_tests()
