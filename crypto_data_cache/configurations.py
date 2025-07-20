# Base URL template for Binance Vision data
from enum import Enum


BINANCE_DATA_URL = "https://data.binance.vision/data/spot/{frequency}/{data_type}/{symbol}/{interval}/{filename}"
BINANCE_TRADES_URL = "https://data.binance.vision/data/spot/{frequency}/{data_type}/{symbol}/{filename}"  # Trades/AggTrades don't have interval subdir

# Data types supported
DATA_TYPE_KLINE = "klines"
DATA_TYPE_TRADE = "trades"
DATA_TYPE_AGGTRADE = "aggTrades"


class DATA_TYPES(Enum):
    """Enum for supported data types."""

    KLINE = DATA_TYPE_KLINE
    TRADE = DATA_TYPE_TRADE
    AGGTRADE = DATA_TYPE_AGGTRADE


# Frequencies supported
FREQUENCY_DAILY = "daily"
FREQUENCY_MONTHLY = "monthly"

# Schemas definition (column names, pandas dtypes, sqlite types, primary key)
# SQLite types mapping: https://www.sqlite.org/datatype3.html
# Pandas types mapping: https://pandas.pydata.org/docs/user_guide/basics.html#dtypes
SCHEMAS = {
    DATA_TYPES.KLINE: {
        "columns": [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ],
        "dtypes": {
            "open_time": "int64",
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "float64",
            "close_time": "int64",
            "quote_asset_volume": "float64",
            "number_of_trades": "int64",
            "taker_buy_base_asset_volume": "float64",
            "taker_buy_quote_asset_volume": "float64",
            "ignore": "float64",  # Often unused, keep type consistent
        },
        "sqlite_types": {
            "open_time": "INTEGER",
            "open": "REAL",
            "high": "REAL",
            "low": "REAL",
            "close": "REAL",
            "volume": "REAL",
            "close_time": "INTEGER",
            "quote_asset_volume": "REAL",
            "number_of_trades": "INTEGER",
            "taker_buy_base_asset_volume": "REAL",
            "taker_buy_quote_asset_volume": "REAL",
            "ignore": "REAL",
        },
        "primary_key": "open_time",
    },
    DATA_TYPES.TRADE: {
        "columns": [
            "trade_id",
            "price",
            "qty",
            "quote_qty",
            "time",
            "is_buyer_maker",
            "is_best_match",
        ],
        "dtypes": {
            "trade_id": "int64",
            "price": "float64",
            "qty": "float64",
            "quote_qty": "float64",
            "time": "int64",
            "is_buyer_maker": "bool",
            "is_best_match": "bool",
        },
        "sqlite_types": {
            "trade_id": "INTEGER",
            "price": "REAL",
            "qty": "REAL",
            "quote_qty": "REAL",
            "time": "INTEGER",
            "is_buyer_maker": "INTEGER",
            "is_best_match": "INTEGER",  # Store bools as 0/1
        },
        "primary_key": "trade_id",
    },
    DATA_TYPES.AGGTRADE: {
        "columns": [
            "agg_trade_id",
            "price",
            "qty",
            "first_trade_id",
            "last_trade_id",
            "time",
            "is_buyer_maker",
            "is_best_match",
        ],
        "dtypes": {
            "agg_trade_id": "int64",
            "price": "float64",
            "qty": "float64",
            "first_trade_id": "int64",
            "last_trade_id": "int64",
            "time": "int64",
            "is_buyer_maker": "bool",
            "is_best_match": "bool",
        },
        "sqlite_types": {
            "agg_trade_id": "INTEGER",
            "price": "REAL",
            "qty": "REAL",
            "first_trade_id": "INTEGER",
            "last_trade_id": "INTEGER",
            "time": "INTEGER",
            "is_buyer_maker": "INTEGER",
            "is_best_match": "INTEGER",  # Store bools as 0/1
        },
        "primary_key": "agg_trade_id",
    },
}


def get_schema(data_type: DATA_TYPES) -> dict:
    """Retrieves the schema configuration for a given data type."""
    if data_type not in SCHEMAS:
        raise ValueError(
            f"Unsupported data type: {data_type}. Supported types: {list(SCHEMAS.keys())}"
        )
    return SCHEMAS[data_type]


def get_table_name(
    symbol: str, data_type: DATA_TYPES, interval: str | None = None
) -> str:
    """Generates the standard table name."""
    if data_type == DATA_TYPES.KLINE:
        if not interval:
            raise ValueError("Interval is required for Kline data type.")
        return f"{symbol}_{interval}_{data_type}"  # e.g., SOLUSDC_5m_klines
    elif data_type in [DATA_TYPES.TRADE, DATA_TYPES.AGGTRADE]:
        return f"{symbol}_{data_type}"  # e.g., SOLUSDC_trades
    else:
        raise ValueError(
            f"Cannot generate table name for unknown data type: {data_type}"
        )


def get_filename(
    symbol: str, data_type: DATA_TYPES, date_str: str, interval: str | None = None
) -> str:
    """Generates the standard filename for daily/monthly data."""
    if data_type == DATA_TYPES.KLINE:
        if not interval:
            raise ValueError("Interval is required for Kline data type.")
        return f"{symbol}-{interval}-{date_str}.zip"  # e.g., SOLUSDC-5m-2023-01-01.zip or SOLUSDC-5m-2023-01.zip
    elif data_type in [DATA_TYPES.TRADE, DATA_TYPES.AGGTRADE]:
        # Trades/AggTrades filenames don't include interval
        return f"{symbol}-{data_type}-{date_str}.zip"  # e.g., SOLUSDC-TRADES-2023-01-01.zip or SOLUSDC-AGGTRADES-2023-01.zip
    else:
        raise ValueError(f"Cannot generate filename for unknown data type: {data_type}")


def build_download_url(
    symbol: str,
    data_type: DATA_TYPES,
    frequency: str,
    date_str: str,
    interval: str | None = None,
) -> str:
    """Constructs the download URL."""
    filename = get_filename(symbol, data_type, date_str, interval)

    if data_type == DATA_TYPES.KLINE:
        if not interval:
            raise ValueError("Interval is required for Kline data type.")
        url = BINANCE_DATA_URL.format(
            frequency=frequency,
            data_type=data_type,
            symbol=symbol,
            interval=interval,
            filename=filename,
        )
    elif data_type in [DATA_TYPES.TRADE, DATA_TYPES.AGGTRADE]:
        # Trades/AggTrades URL structure is slightly different (no interval folder)
        url = BINANCE_TRADES_URL.format(
            frequency=frequency, data_type=data_type, symbol=symbol, filename=filename
        )
    else:
        raise ValueError(f"Cannot build URL for unknown data type: {data_type}")

    return url
