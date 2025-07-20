# aitrade/utils/data/download_utils.py

import requests
import zipfile
from io import BytesIO
import pandas as pd
import time

from crypto_data_cache.exceptions import DownloadFailedError
from crypto_data_cache.configurations import DATA_TYPES, build_download_url
from crypto_data_cache.logging_config import get_logger

logger = get_logger(__name__)


def download_zip_and_extract_csv(
    symbol: str,
    data_type: DATA_TYPES,
    frequency: str,
    date_str: str,  # YYYY-MM-DD or YYYY-MM
    interval: str | None = None,
    retries: int = 3,
    delay: int = 5,
) -> pd.DataFrame | None:
    """
    Downloads a zip file from Binance Vision, extracts the CSV, and returns a DataFrame.

    Args:
        symbol (str): Trading pair (e.g., SOLUSDC).
        data_type (str): Type of data (e.g., klines, trades, aggTrades).
        frequency (str): Data frequency (daily or monthly).
        date_str (str): Date string (YYYY-MM-DD for daily, YYYY-MM for monthly).
        interval (str | None): Kline interval (e.g., "1s", "5m"), required only for klines.
        retries (int): Number of download attempts.
        delay (int): Delay in seconds between retries.

    Returns:
        pd.DataFrame | None: DataFrame with raw data (no headers) or None if download/extraction fails.
    """
    url = build_download_url(symbol, data_type, frequency, date_str, interval)
    attempt = 0

    while attempt < retries:
        attempt += 1
        logger.info(
            f"Attempt {attempt}/{retries}: Downloading {frequency} {data_type} for {symbol} ({date_str}) from {url}",
        )
        try:
            response = requests.get(url, stream=True, timeout=60)

            if response.status_code == 200:
                # Download successful
                try:
                    with zipfile.ZipFile(BytesIO(response.content), "r") as zip_ref:
                        if not zip_ref.namelist():
                            logger.warning(
                                f"Warning: Downloaded zip file is empty: {url}",
                            )
                            return None  # Treat empty zip as failure for this file

                        csv_filename = zip_ref.namelist()[
                            0
                        ]  # Assume first file is the CSV
                        # Extract to memory or temp file if needed, here directly read
                        with zip_ref.open(csv_filename) as csv_file:
                            # Read CSV with error handling
                            try:
                                df = pd.read_csv(csv_file, header=None)
                                logger.debug(
                                    f"Successfully read {len(df)} rows from {csv_filename}"
                                )
                                if df.empty:
                                    logger.warning(f"CSV file {csv_filename} is empty")
                                return df
                            except Exception as e:
                                logger.error(
                                    f"Error reading CSV from {csv_filename}: {str(e)}"
                                )
                                # Try to read the file line by line for debugging
                                try:
                                    csv_file.seek(0)
                                    first_few_lines = [next(csv_file) for _ in range(5)]
                                    logger.debug(
                                        f"First few lines of {csv_filename}: {first_few_lines}"
                                    )
                                except Exception as debug_e:
                                    logger.error(
                                        f"Could not read file contents for debugging: {debug_e}"
                                    )
                                raise

                except zipfile.BadZipFile:
                    logger.error(
                        f"Error: Downloaded file is not a valid zip file: {url}",
                    )
                    # Don't retry bad zip files immediately, might be a server issue
                    # If it persists across retries, it will eventually fail.
                    # If it's a one-off, the next retry might get a good file.
                    # return None # Or continue to retry logic
                except pd.errors.EmptyDataError:
                    logger.warning(
                        f"Warning: Extracted CSV file is empty: {csv_filename}",
                    )
                    return pd.DataFrame()  # Return empty dataframe for empty CSV
                except Exception as e:
                    logger.error(f"Error extracting zip file {url}: {e}")
                    # Decide if retry makes sense for generic extraction errors
                    # return None # Or continue to retry logic

            elif response.status_code == 404:
                logger.warning(
                    f"Warning: Data not found (404) for {url}. Might not exist for this period.",
                )
                return None  # Data doesn't exist, no need to retry

            else:
                logger.error(
                    f"Error: Download failed for {url}. Status code: {response.status_code}",
                )
                # Retry for other server errors (e.g., 5xx)

            # If code reaches here, it means download failed (non-200, non-404) or extraction failed and we retry
            if attempt < retries:
                logger.warning(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(
                    f"Download failed after {retries} attempts for {url}.",
                    attrs=["bold"],
                )
                raise DownloadFailedError(
                    url, response.status_code
                )  # Raise specific error after retries

        except requests.exceptions.RequestException as e:
            logger.error(f"Error during download request for {url}: {e}")
            if attempt < retries:
                logger.warning(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(
                    f"Download failed after {retries} attempts due to network error: {url}."
                )
                raise DownloadFailedError(
                    url, message=f"Network error: {e}"
                ) from e  # Raise specific error

    # Should not be reached if exceptions are raised correctly, but as a fallback
    return None
