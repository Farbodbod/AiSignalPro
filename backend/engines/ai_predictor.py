# engines/ai_predictor.py - نسخه سازگار شده برای سرور

import os
import joblib
import pandas as pd
from xgboost import XGBClassifier
import logging

logger = logging.getLogger(__name__)

class AIEngineProAdvanced:
    def __init__(self):
        self.model = None
        self.data = None
        self.features = None
        self.signal = None
        self.model_file = "ai_model.pkl" # فایل مدل باید در ریشه پروژه باشد
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_file):
            try:
                self.model = joblib.load(self.model_file)
                logger.info("AI model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading AI model: {e}")
        else:
            logger.warning("AI model file 'ai_model.pkl' not found.")

    def load_data(self, df: pd.DataFrame):
        # This class expects a 'price' column, let's ensure it exists.
        df_copy = df.copy()
        if 'price' not in df_copy.columns and 'close' in df_copy.columns:
            df_copy['price'] = df_copy['close']
        self.data = df_copy


    def feature_engineering(self):
        if self.data is None:
            raise ValueError("No data loaded")
        df = self.data.copy()
        df['returns'] = df['price'].pct_change()
        df['volatility'] = df['returns'].rolling(5).std()
        df['momentum'] = df['price'].diff(3)
        df = df.dropna()
        self.features = df

    def infer(self):
        if self.model is None:
            logger.warning("Cannot infer without a loaded model.")
            return # اگر مدل نبود، پیش‌بینی انجام نمی‌شود

        if self.features is None or self.features.empty:
            raise ValueError("Features not prepared or empty")
            
        X = self.features[['returns', 'volatility', 'momentum']]
        self.features['prediction'] = self.model.predict(X)
        self.signal = self.features['prediction'].iloc[-1]

    def _predict_next_price(self):
        if self.features is None or self.features.empty:
            return None
        return self.features['price'].iloc[-1] * (1 + self.features['returns'].mean())

    def generate_advanced_report(self):
        self.infer() # اجرای پیش‌بینی

        if self.signal is None:
            return {
                "signal": "Model Not Available",
                "confidence": 0.0,
                "detail": "ai_model.pkl not found. Please train and deploy the model."
            }

        report = {
            "signal": "Buy" if self.signal == 1 else "Sell",
            "confidence": float(self.features['prediction'].mean()),
            "next_predicted_price": self._predict_next_price()
        }
        return report

