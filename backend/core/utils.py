# core/utils.py

import numpy as np

def convert_numpy_types(obj):
    """
    انواع داده‌های NumPy را به انواع استاندارد پایتون تبدیل می‌کند تا برای سریال‌سازی
    به JSON مناسب باشند. این تابع به صورت بازگشتی روی دیکشنری‌ها و لیست‌ها کار می‌کند.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_types(i) for i in obj]
    return obj
