import sqlite3
from pathlib import Path
import pandas as pd

from crypto_data_cache.configurations import DATA_TYPES, get_schema, get_table_name
from crypto_data_cache.exceptions import DatabaseError
from crypto_data_cache.logging_config import get_logger


logger = get_logger(__name__)


def get_db_connection(
    db_file: Path,
) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_file)
        logger.info(f"Connected to SQLite database @ {db_file}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database {db_file}: {e}")
        raise DatabaseError(f"Failed to connect to database: {e}") from e


def create_table_if_not_exists(
    conn: sqlite3.Connection, symbol: str, data_type: DATA_TYPES, interval: str | None = None
):
    """
    Creates an SQLite table based on the predefined schema if it does not exist.
    """
    table_name = get_table_name(symbol, data_type, interval)
    schema_config = get_schema(data_type)
    cursor = conn.cursor()

    columns_sql = ", ".join(
        f"{col_name} {schema_config['sqlite_types'][col_name]}"
        for col_name in schema_config["columns"]
    )
    primary_key_sql = (
        f"PRIMARY KEY ({schema_config['primary_key']})"
        if schema_config["primary_key"]
        else ""
    )

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS "{table_name}" (
        {columns_sql},
        {primary_key_sql}
    );
    """
    try:
        cursor.execute(create_table_sql)
        # Check if table exists after attempt (more reliable than just executing)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        if cursor.fetchone():
            logger.info(f"Table '{table_name}' ensured to exist.")
            pass
        else:
            # This case should ideally not happen if CREATE TABLE IF NOT EXISTS worked
            logger.warning(
                f"Warning: Table '{table_name}' might not have been created."
            )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error creating table {table_name}: {e}")
        raise DatabaseError(f"Failed to create table {table_name}: {e}") from e


def store_dataframe(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    symbol: str,
    data_type: DATA_TYPES,
    interval: str | None = None,
):
    """
    Stores the DataFrame into the appropriate SQLite table with duplicate prevention.
    Assumes DataFrame columns match the schema's order and types are compatible.
    """
    table_name = get_table_name(symbol, data_type, interval)
    schema_config = get_schema(data_type)
    cursor = conn.cursor()

    if df.empty:
        logger.warning(f"Skipping storage for {table_name}: DataFrame is empty.")
        return 0  # Return 0 rows inserted

    # Ensure columns match schema order for insertion
    try:
        df = df[schema_config["columns"]]
    except KeyError as e:
        logger.error(f"DataFrame columns mismatch schema for {table_name}. Error: {e}")
        logger.error(f"Expected: {schema_config['columns']}")
        logger.error(f"Got: {df.columns.tolist()}")
        raise DatabaseError("DataFrame columns do not match target table schema.")

    # Prepare SQL insert statement
    placeholders = ", ".join(["?"] * len(schema_config["columns"]))
    insert_sql = f"""
    INSERT OR IGNORE INTO "{table_name}" ({", ".join(schema_config["columns"])})
    VALUES ({placeholders});
    """

    try:
        # Convert boolean columns to 0/1 for SQLite if they exist
        for col, dtype in schema_config["dtypes"].items():
            if dtype == "bool" and col in df.columns:
                df[col] = df[col].astype(int)

        # Execute insert
        cursor.executemany(insert_sql, df.values.tolist())
        inserted_rows = cursor.rowcount
        conn.commit()
        logger.info(
            f"Stored {inserted_rows} new rows into '{table_name}' (duplicates ignored)."
        )
        return inserted_rows
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Error storing data into {table_name}: {e}")
        raise DatabaseError(f"Failed to store data in {table_name}: {e}") from e
    except Exception as e:  # Catch other potential errors like type conversion
        conn.rollback()
        logger.error(f"Unexpected error storing data into {table_name}: {e}")
        raise DatabaseError(f"Unexpected error during data storage: {e}") from e


def get_db_date_range(
    conn: sqlite3.Connection, symbol: str, data_type: DATA_TYPES, interval: str | None = None
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """
    Gets the min and max date (as UTC pandas Timestamps) stored in the table.
    Assumes timestamps are stored as UTC microseconds.
    """
    table_name = get_table_name(symbol, data_type, interval)
    schema_config = get_schema(data_type)
    time_col = schema_config["primary_key"] if data_type == DATA_TYPES.KLINE else "time"

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,),
        )
        if not cursor.fetchone():
            return None, None

        query = f'SELECT MIN({time_col}), MAX({time_col}) FROM "{table_name}";'
        cursor.execute(query)
        result = cursor.fetchone()

        if result and result[0] is not None and result[1] is not None:
            # Timestamps are stored as microseconds. Convert to pandas Timestamp (UTC).
            min_ts_us = result[0]
            max_ts_us = result[1]
            # unit='us' for microseconds
            min_pd_ts = pd.Timestamp(min_ts_us, unit="us", tz="UTC")
            max_pd_ts = pd.Timestamp(max_ts_us, unit="us", tz="UTC")
            return min_pd_ts, max_pd_ts
        else:
            return None, None
    except sqlite3.Error as e:
        if "no such table" in str(e).lower():
            return None, None
        logger.warning(f"Error querying date range for {table_name}: {e}")
        return None, None
