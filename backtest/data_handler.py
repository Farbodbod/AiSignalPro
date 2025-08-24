# backtest/data_handler.py (v1.0 - The Data Refinery)

import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple
from copy import deepcopy

logger = logging.getLogger(__name__)

class DataHandler:
    """
    Handles the loading, cleaning, validation, and caching of historical market data.
    It acts as a robust and high-performance "Data Refinery" for the backtesting
    engine, ensuring all downstream modules receive flawless, analysis-ready data.
    """

    def __init__(self, data_directory: str):
        """
        Initializes the DataHandler with the path to the historical data.

        Args:
            data_directory (str): The root directory where data files are stored.
                                  Example: 'historical_data/'
        """
        self.data_path = Path(data_directory)
        if not self.data_path.is_dir():
            logger.error(f"Data directory not found at: {self.data_path}")
            raise FileNotFoundError(f"The specified data directory does not exist: {self.data_path}")
        
        # ✅ UPGRADE 3: Caching Layer to boost performance.
        self._cache: Dict[Tuple[str, str], pd.DataFrame] = {}
        logger.info(f"DataHandler (v1.0 - The Data Refinery) initialized. Data source: '{self.data_path}'")

    def load_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Loads, validates, cleans, and caches historical OHLCV data.

        Args:
            symbol (str): The trading symbol (e.g., 'BTC/USDT').
            timeframe (str): The timeframe (e.g., '5m', '1h').

        Returns:
            Optional[pd.DataFrame]: A clean, validated, and analysis-ready DataFrame,
                                    or None if the data is not found or invalid.
        """
        cache_key = (symbol, timeframe)
        # ✅ UPGRADE 3: Check cache first to avoid redundant disk I/O.
        if cache_key in self._cache:
            logger.debug(f"Loading {symbol}@{timeframe} from cache.")
            return deepcopy(self._cache[cache_key]) # Return a copy to prevent downstream mutation

        # ✅ UPGRADE 1: Standardized File Naming Convention.
        # Replaces '/' with '-' for safer filenames (e.g., BTC/USDT -> BTC-USDT).
        safe_symbol_name = symbol.replace('/', '-')
        file_path = self.data_path / f"{safe_symbol_name}_{timeframe}.csv"

        if not file_path.exists():
            logger.error(f"Data file not found for {symbol}@{timeframe} at expected path: {file_path}")
            return None

        try:
            logger.info(f"Loading {symbol}@{timeframe} from disk: {file_path}")
            df = pd.read_csv(
                file_path,
                parse_dates=['timestamp'],
                index_col='timestamp'
            )

            # ✅ UPGRADE 2: Data Validation & Cleaning Shield.
            # 1. Check for required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"Data integrity failed: Missing columns {missing_cols} in {file_path}")
                return None

            # 2. Ensure correct data types, coercing errors to NaN
            for col in required_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 3. Drop any rows with NaN values resulting from coercion
            initial_rows = len(df)
            df.dropna(inplace=True)
            if len(df) < initial_rows:
                logger.warning(f"Data integrity: Dropped {initial_rows - len(df)} rows with invalid numeric data from {file_path}")

            # 4. Sort by timestamp and remove duplicates to ensure data integrity
            df.sort_index(inplace=True)
            if df.index.has_duplicates:
                rows_before_dedupe = len(df)
                df = df[~df.index.duplicated(keep='first')]
                logger.warning(f"Data integrity: Removed {rows_before_dedupe - len(df)} duplicate timestamps from {file_path}")
            
            if df.empty:
                logger.error(f"Dataframe for {symbol}@{timeframe} is empty after cleaning.")
                return None

            # ✅ UPGRADE 3: Store the clean DataFrame in the cache.
            self._cache[cache_key] = df
            logger.info(f"Successfully loaded and cached {len(df)} candles for {symbol}@{timeframe}.")
            
            return deepcopy(df) # Return a copy

        except Exception as e:
            logger.error(f"Failed to load or process data file {file_path}: {e}", exc_info=True)
            return None

