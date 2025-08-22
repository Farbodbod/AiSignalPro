# backend/engines/indicators/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

# This is a standard Python practice for handling circular type hints
if TYPE_CHECKING:
    from .base import BaseIndicator

logger = logging.getLogger(__name__)

class BaseIndicator(ABC):
    """
    Abstract Base Class for all AiSignalPro indicators (v4.0 - Dependency Injection Ready).
    This version is designed to directly accept pre-calculated dependency instances
    from the v15.0+ IndicatorAnalyzer, enabling a robust, error-proof architecture.
    """
    
    # NOTE: The old `dependencies: List[str]` class attribute is now obsolete and removed.
    # The config.json file is the single source of truth for dependency mapping,
    # and the IndicatorAnalyzer handles the resolution.

    def __init__(self, df: pd.DataFrame, params: Dict[str, Any], dependencies: Optional[Dict[str, 'BaseIndicator']] = None, **kwargs):
        """
        Initializes the indicator with its data, parameters, and direct dependencies.
        
        Args:
            df (pd.DataFrame): The main OHLCV DataFrame.
            params (Dict[str, Any]): Indicator-specific parameters.
            dependencies (Optional[Dict[str, 'BaseIndicator']]): A dictionary of pre-calculated 
                                                                 dependency indicator instances.
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")
        
        self.df = df
        self.params = params
        
        # ✅ CORE UPGRADE: Directly store the injected dependency instances.
        self.dependencies = dependencies or {}
        
        logger.debug(f"Initialized {self.__class__.__name__} with params: {self.params} and {len(self.dependencies)} dependencies.")

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
