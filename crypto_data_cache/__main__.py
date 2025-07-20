import os
from pathlib import Path
from typing import Optional

from crypto_data_cache.configurations import DATA_TYPES
from crypto_data_cache.fetch_utils import fetch_historical_data


class CryptoDataCache:
    """
    Main class for the Crypto Data Cache application.
    This class serves as the entry point for the application.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
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
        interval: str,
        start_date_str: str,
        end_date_str: str,
        prefer_monthly: Optional[bool] = True,
    ):
        """
        Fetches historical data for a given cryptocurrency symbol and data type within a specified date range and interval.

        Args:
            symbol (str): The cryptocurrency symbol (e.g., 'BTCUSDT', 'ETHUSDT').
            data_type (DATA_TYPES): The type of data to fetch (e.g., KLINES, AGG_TRADES etc.).
            interval (str): The data interval (e.g., '1d', '1h').
            start_date_str (str): The start date for data retrieval in string format (e.g., '2023-01-01').
            end_date_str (str): The end date for data retrieval in string format (e.g., '2023-12-31').
            prefer_monthly (Optional[bool], optional): If True, prefers monthly data granularity when available. Defaults to None.

        Returns:
            Any: The historical data fetched, as returned by `fetch_historical_data`.

        """
        return fetch_historical_data(
            symbol,
            data_type,
            start_date_str,
            end_date_str,
            db_file=self.db_path,
            interval=interval,
            prefer_monthly=prefer_monthly if prefer_monthly is not None else True,
        )
