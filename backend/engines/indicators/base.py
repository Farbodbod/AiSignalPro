from abc import ABC, abstractmethod
import pandas as pd
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    Abstract Base Class for all AiSignalPro indicators (v3.0 - Dependency-Aware).
    This version introduces a `dependencies` attribute to enable the legendary
    IndicatorAnalyzer to dynamically resolve the calculation order.
    """
    # ✨ LEGENDARY UPGRADE: Each indicator class can now declare its prerequisites.
    # The IndicatorAnalyzer will use this to build a dynamic dependency graph.
    # Example in a child class: dependencies = ['atr', 'zigzag']
    dependencies: List[str] = []

    def __init__(self, df: pd.DataFrame, **kwargs):
        """
        Initializes the indicator.
        
        Args:
            df (pd.DataFrame): The main OHLCV DataFrame.
            **kwargs: Indicator-specific parameters.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df
        # This pattern allows parameters to be passed directly or nested in a 'params' dict.
        self.params = kwargs.get('params', kwargs)
        
        logger.debug(f"Initialized {self.__class__.__name__} with params: {self.params}")

    @abstractmethod
    def calculate(self) -> 'BaseIndicator':
        """
        Abstract method for the indicator's calculation logic.
        Must be implemented by each child class and should return `self`.
        """
        pass

    @abstractmethod
    def analyze(self) -> Dict[str, Any]:
        """
        Abstract method for analyzing the indicator's latest values.
        Must return a standardized dictionary and be designed to be bias-free.
        """
        pass
