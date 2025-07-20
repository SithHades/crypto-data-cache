import os
from pathlib import Path
from typing import Optional
import pandas as pd

from crypto_data_cache.configurations import DATA_TYPES
from crypto_data_cache.fetch_utils import fetch_historical_data


class CryptoDataCache:
    """
    Main client class for the Crypto Data Cache library.

    Provides a high-level interface for fetching and caching cryptocurrency data
    with automatic database management and configuration.

    Example:
        >>> cache = CryptoDataCache()
        >>> df = cache.fetch_data(
        ...     symbol="BTCUSDT",
        ...     data_type=DATA_TYPES.KLINE,
        ...     interval="1h",
        ...     start_date_str="2024-01-01",
        ...     end_date_str="2024-01-31"
        ... )
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        """
        Initialize the CryptoDataCache client.

        Args:
            db_path: Path to the SQLite database file. If None, uses
                    CRYPTO_CACHE_DB_PATH environment variable or
                    default: ~/.crypto_cache/db.sqlite
        """
        if db_path is None:
            db_path = os.getenv(
                "CRYPTO_CACHE_DB_PATH", os.path.expanduser("~/.crypto_cache/db.sqlite")
            )

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = Path(db_path)

    def fetch_data(
        self,
        symbol: str,
        data_type: DATA_TYPES,
        start_date_str: str,
        end_date_str: str,
        interval: Optional[str] = None,
        prefer_monthly: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch historical cryptocurrency data.

        Args:
            symbol: The cryptocurrency symbol (e.g., 'BTCUSDT', 'ETHUSDT')
            data_type: The type of data to fetch (KLINE, TRADE, AGGTRADE)
            start_date_str: Start date in 'YYYY-MM-DD' format
            end_date_str: End date in 'YYYY-MM-DD' format
            interval: Data interval (required for KLINE data, e.g., '1h', '1d')
            prefer_monthly: Whether to prefer monthly downloads when possible

        Returns:
            pandas.DataFrame: Historical data with properly typed columns

        Raises:
            ValueError: If interval is required but not provided
        """
        return fetch_historical_data(
            symbol=symbol,
            data_type=data_type,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            db_file=self.db_path,
            interval=interval,
            prefer_monthly=prefer_monthly,
        )
