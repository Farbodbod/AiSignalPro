# core/utils.py (نسخه نهایی 1.2 - سازگار با Pandas)

import numpy as np
import pandas as pd

def convert_numpy_types(obj):
    """
    تابع کمکی قوی برای تبدیل انواع داده NumPy و Pandas به انواع داده استاندارد پایتون.
    این نسخه به طور ایمن از پس دیتافریم‌ها و سری‌های Pandas نیز برمی‌آید.
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(element) for element in obj]
    # ✅ FIX: Added a check for pandas objects to prevent ValueError.
    # We return None because we don't intend to save huge dataframes in the JSON field.
    elif isinstance(obj, (pd.DataFrame, pd.Series)):
        return None
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj
