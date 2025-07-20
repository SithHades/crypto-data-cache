# aitrade/data/downloader.py

from datetime import datetime, timedelta, date, timezone
from pathlib import Path
import pandas as pd
import sqlite3
import time

from crypto_data_cache.configurations import (
    DATA_TYPES,
    get_schema,
    get_table_name,
    FREQUENCY_DAILY,
    FREQUENCY_MONTHLY,
)
from crypto_data_cache.db_utils import (
    get_db_connection,
    create_table_if_not_exists,
    store_dataframe,
)
from .download_utils import download_zip_and_extract_csv
from crypto_data_cache.exceptions import DownloadFailedError, DatabaseError

from crypto_data_cache.logging_config import get_logger


logger = get_logger(__name__)
logger.setLevel("DEBUG")


def _parse_date(date_str: str) -> date:
    """Helper to parse YYYY-MM-DD date string."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.")


def _generate_date_ranges(
    start_date_str: str, end_date_str: str
) -> tuple[date, date, pd.DatetimeIndex, pd.DatetimeIndex]:
    """Parses dates and generates daily and monthly ranges."""
    start_date = _parse_date(start_date_str)
    end_date = _parse_date(end_date_str)

    if start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    all_days = pd.date_range(start=start_date, end=end_date, freq="D", tz=None)

    start_month = start_date.replace(day=1)
    end_month_year = end_date.year
    end_month_month = end_date.month
    all_months = pd.date_range(
        start=start_month,
        end=f"{end_month_year}-{end_month_month:02d}-01",
        freq="MS",
        tz=None,
    )

    return start_date, end_date, all_days, all_months


def download_and_store_data(
    symbol: str,
    data_type: DATA_TYPES,
    frequency: str,
    date_str: str,  # YYYY-MM-DD or YYYY-MM
    db_file: Path,
    interval: str | None = None,
) -> int:
    """
    Downloads a single data file (daily or monthly), processes, and stores it.
    Timestamps are converted to UTC microseconds before storage.
    Returns:
        Number of new rows inserted. Returns -1 if download failed.
    """
    conn = get_db_connection(db_file)
    try:
        create_table_if_not_exists(conn, symbol, data_type, interval)

        logger.info(
            f"Starting download for {symbol} {data_type} {frequency} {date_str}"
        )
        try:
            df_raw = download_zip_and_extract_csv(
                symbol, data_type, frequency, date_str, interval
            )
        except DownloadFailedError as e:
            if "404" in str(e):
                logger.warning(
                    f"Data not found (404) for {symbol} {data_type} {frequency} {date_str}"
                )
                return 0
            logger.error(
                f"Download failed for {symbol} {data_type} {frequency} {date_str}: {str(e)}",
                exc_info=True,
            )
            return -1
        except Exception as e:
            logger.error(
                f"Unexpected error during download for {symbol} {data_type} {frequency} {date_str}: {str(e)}",
                exc_info=True,
            )
            return -1

        if df_raw is None or df_raw.empty:
            logger.warning(
                f"No data available or downloaded for {symbol} {data_type} {frequency} {date_str}"
            )
            return 0

        logger.debug(
            f"Downloaded {len(df_raw)} rows of data for {symbol} {data_type} {date_str}"
        )

        schema_config = get_schema(data_type)
        expected_columns = schema_config["columns"]

        if all(isinstance(col, int) for col in df_raw.columns):
            if len(df_raw.columns) == len(expected_columns):
                df_raw.columns = expected_columns
            else:
                logger.error(
                    f"Column count mismatch. Expected {len(expected_columns)}, got {len(df_raw.columns)}. Data for {date_str} may be corrupted."
                )
                return 0  # Treat as no valid data

        missing_columns = set(expected_columns) - set(df_raw.columns)
        if missing_columns:
            logger.warning(
                f"Missing expected columns: {missing_columns} in data for {date_str}. Proceeding with available."
            )
            # Allow processing if critical time columns are present, otherwise it might fail later

        df_processed = df_raw.copy()
        columns_to_keep = [
            col for col in expected_columns if col in df_processed.columns
        ]
        df_processed = df_processed[columns_to_keep]

        # Timestamp conversion and type handling
        # Assume Binance raw CSV timestamps are in microseconds UTC
        # Convert to pandas datetime, then to UTC microsecond integers for storage
        time_cols_to_convert_to_us = []
        if data_type == DATA_TYPES.KLINE:
            time_cols_to_convert_to_us = ["open_time", "close_time"]
        elif data_type in [
            DATA_TYPES.TRADE,
            DATA_TYPES.AGGTRADE,
        ]:  # Assuming 'time' is the column for these
            time_cols_to_convert_to_us = ["time"]

        for col_name in time_cols_to_convert_to_us:
            if col_name in df_processed.columns:
                try:
                    # Ensure original is numeric (microseconds)
                    df_processed[col_name] = pd.to_numeric(
                        df_processed[col_name], errors="raise"
                    )
                except Exception as e:
                    logger.error(
                        f"Error converting timestamp column '{col_name}' to microseconds for {date_str}: {e}. Skipping file."
                    )
                    logger.debug(
                        f"Problematic data for column {col_name}:\n{df_processed[col_name].head()}"
                    )
                    return 0  # Treat as no valid data to store

        # Apply other dtypes from schema
        for col, dtype_str in schema_config["dtypes"].items():
            if (
                col in df_processed.columns and col not in time_cols_to_convert_to_us
            ):  # Avoid re-processing time cols
                try:
                    if dtype_str == "bool":  # SQLite stores bools as 0 or 1
                        df_processed[col] = df_processed[col].astype(int)
                    else:
                        df_processed[col] = df_processed[col].astype(dtype_str)
                except Exception as e:
                    logger.warning(
                        f"Could not convert column '{col}' to {dtype_str} for {date_str}: {e}. Trying pd.to_numeric."
                    )
                    try:
                        df_processed[col] = pd.to_numeric(
                            df_processed[col], errors="coerce"
                        )
                        if (
                            dtype_str != "float"
                        ):  # If target is not float, attempt final conversion
                            df_processed[col] = df_processed[col].astype(
                                dtype_str
                            )  # This might fail if NaNs present in int col
                    except Exception as e2:
                        logger.error(
                            f"Failed to convert column '{col}' to {dtype_str} (attempt 2) for {date_str}: {e2}. Skipping file."
                        )
                        return 0  # Treat as no valid data

        logger.debug(f"Processed data types for {date_str}:\n{df_processed.dtypes}")
        logger.debug(
            f"Processed data sample (first 2 rows) for {date_str}:\n{df_processed.head(2).to_string()}"
        )

        try:
            inserted_count = store_dataframe(
                conn, df_processed, symbol, data_type, interval
            )
            if inserted_count > 0:
                logger.info(
                    f"Successfully stored {inserted_count} rows for {symbol} {data_type} {frequency} {date_str}"
                )
            else:
                logger.info(  # Changed from warning to info, as 0 new rows is common for existing data
                    f"No new data was stored for {symbol} {data_type} {frequency} {date_str}. "
                    "This is expected if data already exists or no valid rows were processed."
                )
            return inserted_count
        except DatabaseError as e:  # Catch specific DatabaseError from store_dataframe
            logger.error(
                f"Database error storing data for {symbol} {data_type} {frequency} {date_str}: {e}",
                exc_info=True,
            )
            return 0  # Treat as failed storage for this file, but not a global download failure for -1
        except Exception as e:
            logger.error(
                f"Unexpected error storing data for {symbol} {data_type} {frequency} {date_str}: {e}",
                exc_info=True,
            )
            return 0  # Treat as failed storage for this file

    except (DownloadFailedError, DatabaseError) as e:  # These are more critical
        logger.error(
            f"Failed to download/store {frequency} {data_type} for {symbol} ({date_str}): {e}",
        )
        return -1
    except Exception as e:
        logger.error(
            f"Unexpected error during download/store for {symbol} {data_type} ({date_str}): {e}",
            exc_info=True,
        )
        return -1
    finally:
        if conn:
            conn.close()


def check_missing_dates(
    conn: sqlite3.Connection,
    symbol: str,
    data_type: DATA_TYPES,
    required_days: pd.DatetimeIndex,  # Expects naive DatetimeIndex representing UTC days
    interval: str | None = None,
) -> pd.DatetimeIndex:
    """
    Checks the database for existing data (stored as UTC microsecond timestamps)
    and returns a DatetimeIndex of missing UTC days.
    """
    table_name = get_table_name(symbol, data_type, interval)
    schema_config = get_schema(data_type)
    # This is the primary timestamp column we query for existence, stored in microseconds.
    time_col = schema_config["primary_key"] if data_type == DATA_TYPES.KLINE else "time"

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        if not cursor.fetchone():
            logger.warning(
                f"Table '{table_name}' does not exist. All requested dates are considered missing.",
            )
            return required_days  # All days are missing if table doesn't exist

        if required_days.empty:
            return pd.DatetimeIndex([])

        # Convert required_days (which are pd.Timestamp objects representing midnight UTC)
        # to microsecond epoch timestamps for the query range.
        # The query will find any record within the specified days.
        min_req_dt = datetime.combine(
            required_days.min().date(), datetime.min.time(), tzinfo=timezone.utc
        )
        # Max date end of day: take the max day, add 1 day, then it's the midnight of the day AFTER the last required day
        max_req_dt_exclusive = datetime.combine(
            required_days.max().date() + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        min_req_ts_us = int(min_req_dt.timestamp() * 1_000_000)
        max_req_ts_us_exclusive = int(max_req_dt_exclusive.timestamp() * 1_000_000)

        # Query for distinct dates based on the microsecond timestamp column.
        # SQLite's strftime can format Unix epoch (seconds) directly.
        # We divide by 1,000,000 to convert microseconds to seconds for strftime.
        # Using julianday and then converting might be safer for broader SQLite version compatibility
        # with large integer timestamps if direct division in DATE/strftime is an issue.
        # However, `strftime('%Y-%m-%d', {time_col} / 1000000.0, 'unixepoch')` is standard.
        # For very large numbers, ensure floating point division for unixepoch.
        query = f"""
            SELECT DISTINCT strftime('%Y-%m-%d', ROUND({time_col} / 1000000.0), 'unixepoch')
            FROM "{table_name}"
            WHERE {time_col} >= ? AND {time_col} < ?
        """
        logger.debug(
            f"Executing check_missing_dates query on {table_name}: {query} with params ({min_req_ts_us}, {max_req_ts_us_exclusive})"
        )
        cursor.execute(query, (min_req_ts_us, max_req_ts_us_exclusive))

        existing_dates_str = {row[0] for row in cursor.fetchall() if row[0]}
        if not existing_dates_str:
            logger.info(
                f"No existing dates found in range for {table_name}. All required days are missing."
            )
            return required_days

        # Convert string dates from DB ('YYYY-MM-DD') to pandas datetime objects (naive, representing UTC dates)
        existing_dates = pd.to_datetime(
            list(existing_dates_str), format="%Y-%m-%d", errors="coerce"
        ).dropna()
        existing_dates_set = set(existing_dates.date)  # Compare using date objects

        # required_days is already a DatetimeIndex of naive Timestamps (representing UTC dates)
        required_dates_set = set(required_days.date)
        missing_dates_list = sorted(list(required_dates_set - existing_dates_set))

        if not missing_dates_list:
            return pd.DatetimeIndex([])

        # Return as DatetimeIndex (naive, representing UTC dates)
        return pd.to_datetime(missing_dates_list)

    except sqlite3.Error as e:
        logger.error(f"Database error checking missing dates for {table_name}: {e}")
        raise DatabaseError(f"Failed to check missing dates: {e}") from e


def fetch_historical_data(
    symbol: str,
    data_type: DATA_TYPES,
    start_date_str: str,
    end_date_str: str,
    db_file: Path,
    interval: str | None = None,
    prefer_monthly: bool = True,
) -> pd.DataFrame:
    """
    Main function to load historical data. Downloads missing data using daily/monthly strategy.
    Timestamps in the database are expected to be UTC microseconds.
    Returned DataFrame will have datetime columns converted to pandas UTC Timestamps.
    """
    if data_type == DATA_TYPES.KLINE and not interval:
        raise ValueError("Interval must be specified for data_type 'klines'")
    if data_type != DATA_TYPES.KLINE and interval:
        logger.warning(
            f"Warning: Interval '{interval}' provided but not used for data_type '{data_type}'.",
        )
        interval = None

    start_time_total = time.time()

    # --- 1. Setup and Date Range (expect naive dates, will be treated as UTC) ---
    (
        _start_date_naive,
        _end_date_naive,
        all_required_days_naive,
        all_required_months_naive,
    ) = _generate_date_ranges(start_date_str, end_date_str)

    # Clamp end_date to yesterday if it's today or in the future, as data is usually for previous periods
    # Use naive dates for this comparison
    today_naive = date.today()
    if _end_date_naive >= today_naive:
        logger.warning(
            f"End date {_end_date_naive} is today or in the future. Clamping to yesterday {today_naive - timedelta(days=1)} for data availability."
        )
        _end_date_naive = today_naive - timedelta(days=1)
        if _start_date_naive > _end_date_naive:  # If start date was also today/future
            logger.error(
                f"Start date {_start_date_naive} is after clamped end date {_end_date_naive}. No data to fetch."
            )
            return pd.DataFrame()  # Return empty DataFrame

        # Regenerate date ranges with clamped end date
        (
            _start_date_naive,
            _end_date_naive,
            all_required_days_naive,
            all_required_months_naive,
        ) = _generate_date_ranges(
            _start_date_naive.strftime("%Y-%m-%d"), _end_date_naive.strftime("%Y-%m-%d")
        )

    if (
        _start_date_naive > _end_date_naive
    ):  # Should be caught by clamping or initial check
        logger.info(
            f"Start date {_start_date_naive} is after end date {_end_date_naive}. No data to fetch."
        )
        return pd.DataFrame()

    logger.info(
        f"Requesting {data_type} for {symbol} ({interval or 'N/A'}) from {_start_date_naive} to {_end_date_naive}",
    )

    conn = get_db_connection(db_file)
    try:
        create_table_if_not_exists(conn, symbol, data_type, interval)

        # all_required_days_naive is a DatetimeIndex of naive Timestamps representing UTC days
        missing_days_naive = check_missing_dates(
            conn, symbol, data_type, all_required_days_naive, interval
        )

        if not missing_days_naive.empty:
            logger.warning(
                f"Found {len(missing_days_naive)} missing day(s) of data. Attempting download...",
            )
            missing_days_date_objects = set(
                missing_days_naive.date
            )  # Work with date objects

            downloaded_something = False
            dates_to_download_daily = set(missing_days_date_objects)

            if prefer_monthly:
                # Create months based on the actual missing days' range
                if not missing_days_naive.empty:
                    # Ensure months_to_check are naive, representing UTC months
                    months_to_check = pd.date_range(
                        start=missing_days_naive.min(),
                        end=missing_days_naive.max(),
                        freq="MS",
                        tz=None,
                    )
                    current_month_start_naive = date.today().replace(day=1)

                    for (
                        month_start_naive_ts
                    ) in months_to_check:  # month_start_naive_ts is a Timestamp
                        month_start_naive = (
                            month_start_naive_ts.date()
                        )  # Convert to date object
                        month_str = month_start_naive.strftime("%Y-%m")

                        # Skip monthly download for the current actual month as it's incomplete
                        if month_start_naive >= current_month_start_naive:
                            logger.info(
                                f"Skipping monthly download for current/future month {month_str}."
                            )
                            continue

                        # Days in this specific month (naive, representing UTC days)
                        days_in_month_pd = pd.date_range(
                            start=month_start_naive,
                            end=month_start_naive + pd.offsets.MonthEnd(0),
                            freq="D",
                            tz=None,
                        )
                        # Filter to only those within the original requested range [_start_date_naive, _end_date_naive]
                        relevant_days_in_month_dates = {
                            d.date()
                            for d in days_in_month_pd
                            if _start_date_naive <= d.date() <= _end_date_naive
                        }

                        if relevant_days_in_month_dates.issubset(
                            missing_days_date_objects
                        ):
                            logger.info(
                                f"Attempting monthly download for {symbol} {month_str}..."
                            )
                            result = download_and_store_data(
                                symbol,
                                data_type,
                                FREQUENCY_MONTHLY,
                                month_str,
                                db_file,
                                interval,
                            )
                            if result != -1:  # Download didn't fatally fail
                                downloaded_something = (
                                    True  # even if 0 rows from this file
                                )
                                # If monthly download succeeded (or returned 0 new rows meaning data is there or file empty)
                                # we assume it covered these days.
                                # Re-check missing after monthly might be more robust but adds DB calls.
                                # For now, optimistically remove.
                                if (
                                    result >= 0
                                ):  # Success or empty file or data already present
                                    dates_to_download_daily -= (
                                        relevant_days_in_month_dates
                                    )
                                    logger.info(
                                        f"Processed monthly file for {month_str}. Removed {len(relevant_days_in_month_dates)} day(s) from daily queue.",
                                    )
                            else:  # result == -1, download failed critically
                                logger.warning(
                                    f"Monthly download failed critically for {month_str}. These days will be attempted daily.",
                                )
                        # else: Month is only partially missing, or some days already exist, handle daily

            if dates_to_download_daily:
                logger.info(
                    f"Attempting daily download for {len(dates_to_download_daily)} remaining/failed day(s)...",
                )
                # Sort for chronological downloads
                for day_date_obj in sorted(list(dates_to_download_daily)):
                    day_str = day_date_obj.strftime("%Y-%m-%d")
                    # Do not download for "today" for daily files, it's usually not available
                    if day_date_obj >= today_naive:
                        logger.info(
                            f"Skipping daily download for {day_str} as it is today or in the future."
                        )
                        continue
                    result = download_and_store_data(
                        symbol, data_type, FREQUENCY_DAILY, day_str, db_file, interval
                    )
                    if result != -1:  # Download didn't fatally fail
                        downloaded_something = True

            if not downloaded_something and not missing_days_naive.empty:
                logger.warning(
                    "Some data was missing, but no new data could be downloaded or stored (all downloads may have failed or returned empty/duplicate).",
                )
            elif downloaded_something:
                logger.info("Download attempts completed.")
            elif (
                not missing_days_naive.empty and not downloaded_something
            ):  # Missing but nothing was flagged for download (e.g. all future)
                logger.info(
                    "Missing data was identified, but no downloads were attempted (e.g., dates are in the future)."
                )

        else:
            logger.info(
                "No missing data found in the specified range according to database state."
            )

        # --- 5. Load Data from Database ---
        logger.info(
            f"Loading data from database for {_start_date_naive} to {_end_date_naive}..."
        )
        table_name = get_table_name(symbol, data_type, interval)
        schema_config = get_schema(data_type)
        db_time_col = (
            schema_config["primary_key"] if data_type == DATA_TYPES.KLINE else "time"
        )

        # Query range in UTC microseconds
        start_dt_utc = datetime.combine(
            _start_date_naive, datetime.min.time(), tzinfo=timezone.utc
        )
        start_ts_us = int(start_dt_utc.timestamp() * 1_000_000)
        end_dt_exclusive_utc = datetime.combine(
            _end_date_naive + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        end_ts_us_exclusive = int(end_dt_exclusive_utc.timestamp() * 1_000_000)

        select_cols_list = []
        cols_for_datetime_conversion = []
        time_cols_in_db_us = (
            ["open_time", "close_time"] if data_type == DATA_TYPES.KLINE else ["time"]
        )

        for col_name in schema_config["columns"]:
            if col_name in time_cols_in_db_us:
                select_cols_list.append(f'"{col_name}"')
                cols_for_datetime_conversion.append(col_name)
            else:
                select_cols_list.append(f'"{col_name}"')
        select_cols_sql = ", ".join(select_cols_list)

        df_query = f"""
            SELECT {select_cols_sql}
            FROM "{table_name}"
            WHERE "{db_time_col}" >= ? AND "{db_time_col}" < ?
            ORDER BY "{db_time_col}" ASC
        """
        df = pd.read_sql_query(
            df_query, conn, params=(start_ts_us, end_ts_us_exclusive)
        )

        if df.empty:
            logger.info(
                f"No data found in DB for {symbol} in range {_start_date_naive} to {_end_date_naive}."
            )
        else:
            # Convert microsecond integer timestamps to pandas UTC datetime objects
            for col_to_convert in cols_for_datetime_conversion:
                if col_to_convert in df.columns:
                    df[col_to_convert] = pd.to_datetime(
                        df[col_to_convert], unit="us", utc=True, errors="coerce"
                    )

            # Apply boolean types (SQLite stores as int 0/1)
            for col, dtype_str in schema_config["dtypes"].items():
                if dtype_str == "bool" and col in df.columns:
                    if pd.api.types.is_numeric_dtype(df[col]):  # Check if it's 0/1
                        df[col] = df[col].astype(bool)  # Simple bool conversion
                    else:  # If it became object due to NaNs from coerce earlier or other issues
                        logger.warning(
                            f"Column '{col}' for bool conversion is {df[col].dtype}, attempting safe conversion."
                        )
                        # pd.Series.map({1: True, 0: False}) might be safer if mixed types or NaNs present
                        df[col] = (
                            df[col].map({1: True, 0: False}).astype("boolean")
                        )  # Pandas nullable bool

            logger.info(
                f"Successfully loaded {len(df)} rows of {data_type} data for {symbol}."
            )

        end_time_total = time.time()
        logger.info(
            f"Total time for fetch_historical_data: {end_time_total - start_time_total:.2f} seconds."
        )
        return df

    except (DatabaseError, ValueError) as e:
        logger.error(f"Error during data fetch: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")
