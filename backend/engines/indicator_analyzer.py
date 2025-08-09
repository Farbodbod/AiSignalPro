import pandas as pd
import logging

logger = logging.getLogger(__name__)

class IndicatorAnalyzer:
    def __init__(self, df: pd.DataFrame, config: dict, indicator_classes: dict):
        self.df = df.copy()
        self.config = config
        self._indicator_classes = indicator_classes
        self._indicator_instances = {}

    def calculate_all(self) -> pd.DataFrame:
        """
        اجرای محاسبه همه اندیکاتورهای فعال بر اساس config.
        هر اندیکاتور باید یا یک DataFrame برگردونه یا df داخلی داشته باشه.
        """
        logger.info("Starting calculation for all enabled indicators.")
        for name, params in self.config.items():
            if params.get('enabled', False):
                indicator_class = self._indicator_classes.get(name)
                if indicator_class:
                    try:
                        # حذف کلید 'enabled' قبل از ارسال به کلاس
                        params_without_enabled = {
                            k: v for k, v in params.items() if k != 'enabled'
                        }
                        instance = indicator_class(self.df, **params_without_enabled)
                        result_df = instance.calculate()

                        # اگر نتیجه محاسبه DataFrame نبود، از df داخلی instance استفاده کن
                        if not isinstance(result_df, pd.DataFrame):
                            result_df = getattr(instance, "df", None)
                            if not isinstance(result_df, pd.DataFrame):
                                raise TypeError(
                                    f"Indicator '{name}' did not return a DataFrame."
                                )

                        # ذخیره نتیجه برای مرحله بعد
                        self.df = result_df
                        self._indicator_instances[name] = instance

                    except Exception as e:
                        logger.error(
                            f"Failed to calculate indicator '{name}': {e}", exc_info=True
                        )
        return self.df

    def get_indicator_instance(self, name: str):
        """
        گرفتن نمونه اندیکاتور برای دسترسی به متدها یا داده‌های داخلی
        """
        return self._indicator_instances.get(name)

    def get_all_results(self) -> pd.DataFrame:
        """
        گرفتن آخرین DataFrame که همه اندیکاتورها روی آن محاسبه شده‌اند
        """
        return self.df
