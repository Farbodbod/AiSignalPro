# core/utils.py (نسخه نهایی و کامل)

import numpy as np
import pandas as pd # <-- اضافه کردن import پانداز برای pd.isna

def convert_numpy_types(obj):
    """
    یک تابع کمکی قوی برای تبدیل انواع داده NumPy به انواع داده استاندارد پایتون
    تا در هنگام تبدیل به JSON با خطا مواجه نشویم.
    """
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(element) for element in obj]
    elif isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                          np.int16, np.int32, np.int64, np.uint8,
                          np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    return obj
