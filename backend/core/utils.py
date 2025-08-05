# core/utils.py (نسخه نهایی 1.1 - سازگار با NumPy 2.0)

import numpy as np
import pandas as pd

def convert_numpy_types(obj):
    """
    تابع کمکی قوی برای تبدیل انواع داده NumPy به انواع داده استاندارد پایتون.
    سازگار با NumPy 2.0 و بالاتر.
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(element) for element in obj]
    # --- ✨ اصلاح کلیدی: استفاده از نام‌های جدید NumPy ---
    elif isinstance(obj, (np.integer)): # پوشش تمام انواع int
        return int(obj)
    elif isinstance(obj, (np.floating)): # پوشش تمام انواع float
        return float(obj)
    # --- پایان اصلاح ---
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj
