"""
Crypto Data Cache - A Python library for efficiently downloading, caching, and managing cryptocurrency market data from Binance.
"""

__version__ = "0.1.0"
__author__ = "Luca B. Knaack"

from .fetch_utils import fetch_historical_data, download_and_store_data
from .configurations import DATA_TYPES, get_schema, get_table_name
from .exceptions import DownloadFailedError, DatabaseError

__all__ = [
    "fetch_historical_data",
    "download_and_store_data", 
    "DATA_TYPES",
    "get_schema",
    "get_table_name",
    "DownloadFailedError",
    "DatabaseError",
]