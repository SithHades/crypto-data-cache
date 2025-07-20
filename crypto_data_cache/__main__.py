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
            db_path = os.getenv('CRYPTO_CACHE_DB_PATH', os.path.expanduser('~/.crypto_cache/db.sqlite'))

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = Path(db_path)

    def fetch_data(self, symbol: str, data_type: DATA_TYPES, interval: str, start_date_str: str, end_date_str: str, prefer_monthly: Optional[bool] = None):
        """
        """
        return fetch_historical_data(
            symbol,
            data_type,
            start_date_str,
            end_date_str,
            db_file=self.db_path,
            interval=interval,
            prefer_monthly=prefer_monthly
        )