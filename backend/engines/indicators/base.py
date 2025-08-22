# backend/engines/indicators/base.py (v5.0 - The Identity Protocol)
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    Abstract Base Class for all AiSignalPro indicators (v5.0 - The Identity Protocol).
    ----------------------------------------------------------------------------------
    This version introduces a critical architectural upgrade: each indicator instance
    is now initialized with its own `unique_key`. This makes each indicator
    self-aware of its official identity, eliminating the need for re-calculating
    keys and creating a cleaner, more robust and truly professional architecture.
    """

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], unique_key: str, dependencies: Optional[Dict[str, 'BaseIndicator']] = None, **kwargs):
        """
        Initializes the indicator.
        
        Args:
            df (pd.DataFrame): The main OHLCV DataFrame.
            params (Dict[str, Any]): Indicator-specific parameters.
            unique_key (str): The official, system-wide unique key for this instance.
            dependencies (Optional[Dict[str, 'BaseIndicator']]): A dictionary of dependency instances.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df
        self.params = params
        # ✅ THE IDENTITY PROTOCOL: Each indicator now knows its own official ID.
        self.unique_key = unique_key
        self.dependencies = dependencies or {}
        
        logger.debug(f"Initialized {self.__class__.__name__} ({self.unique_key}) with params: {self.params} and {len(self.dependencies)} dependencies.")

    @abstractmethod
    def calculate(self) -> 'BaseIndicator':
        pass

    @abstractmethod
    def analyze(self) -> Dict[str, Any]:
        pass
