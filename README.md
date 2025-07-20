# Crypto Data Cache

A Python library for efficiently downloading, caching, and managing cryptocurrency market data from Binance. This package provides a robust solution for fetching historical kline (candlestick), trade, and aggregate trade data with automatic retry mechanisms and local SQLite caching.

## Features

- **Efficient Data Fetching**: Download historical cryptocurrency data from Binance
- **Local Caching**: SQLite-based storage for fast local access
- **Multiple Data Types**: Support for klines, trades, and aggregate trades
- **Automatic Gap Detection**: Identifies and fills missing data automatically
- **Monthly/Daily Downloads**: Optimized download strategy using monthly files when possible
- **Robust Error Handling**: Comprehensive error handling and logging
- **Type Safety**: Full type hints for better development experience

## Installation

```bash
pip install crypto-data-cache
```

## Quick Start

```python
from crypto_data_cache import CryptoDataCache, DATA_TYPES

# Initialize the client (uses default database location)
cache = CryptoDataCache()

# Fetch Bitcoin 1-hour kline data
df = cache.fetch_data(
    symbol="BTCUSDT",
    data_type=DATA_TYPES.KLINE,
    start_date_str="2024-01-01",
    end_date_str="2024-01-31",
    interval="1h"
)

print(f"Loaded {len(df)} rows of data")
print(df.head())
```

### Advanced Usage (Direct Functions)

```python
from crypto_data_cache.fetch_utils import fetch_historical_data
from crypto_data_cache.configurations import DATA_TYPES
from pathlib import Path

# Direct function usage with custom database path
df = fetch_historical_data(
    symbol="BTCUSDT",
    data_type=DATA_TYPES.KLINE,
    start_date_str="2024-01-01",
    end_date_str="2024-01-31",
    db_file=Path("custom_crypto_data.db"),
    interval="1h"
)
```

## Supported Data Types

- **KLINE**: Candlestick/OHLCV data with various intervals (1m, 5m, 1h, 1d, etc.)
- **TRADE**: Individual trade data
- **AGGTRADE**: Aggregate trade data

## Configuration

The library automatically handles:
- Database schema creation
- Data type validation
- Timestamp conversion (UTC microseconds)
- Missing data detection and download

## API Reference

### CryptoDataCache Class

The main client class providing a high-level interface:

#### `CryptoDataCache(db_path=None)`
Initialize the client with optional custom database path.

#### `fetch_data()`
Primary method for fetching historical data.

### Direct Functions

#### `fetch_historical_data()`
Lower-level function for direct access.

**Parameters:**
- `symbol` (str): Trading pair symbol (e.g., "BTCUSDT")
- `data_type` (DATA_TYPES): Type of data to fetch
- `start_date_str` (str): Start date in "YYYY-MM-DD" format
- `end_date_str` (str): End date in "YYYY-MM-DD" format
- `db_file` (Path): Path to SQLite database file
- `interval` (str, optional): Required for KLINE data (e.g., "1h", "1d")
- `prefer_monthly` (bool): Whether to prefer monthly downloads (default: True)

**Returns:**
- `pd.DataFrame`: Historical data with properly typed columns

### Data Types

```python
from crypto_data_cache.configurations import DATA_TYPES

# Available data types
DATA_TYPES.KLINE      # Candlestick data
DATA_TYPES.TRADE      # Individual trades
DATA_TYPES.AGGTRADE   # Aggregate trades
```

## Database Storage

Data is stored in SQLite with the following features:
- Automatic table creation with proper schemas
- UTC timestamp storage (microsecond precision)
- Efficient querying and indexing
- Duplicate data prevention

## Error Handling

The library includes comprehensive error handling:
- Network timeouts and retries
- Data validation
- Missing file handling (404 errors)
- Database connection management

## Logging

Built-in logging provides detailed information about:
- Download progress
- Missing data detection
- Error conditions
- Performance metrics

## Examples

### Fetch Multiple Intervals

```python
from crypto_data_cache import CryptoDataCache, DATA_TYPES

# Initialize once, reuse for multiple requests
cache = CryptoDataCache()

# Fetch different intervals
intervals = ["1h", "4h", "1d"]

for interval in intervals:
    df = cache.fetch_data(
        symbol="ETHUSDT",
        data_type=DATA_TYPES.KLINE,
        start_date_str="2024-01-01",
        end_date_str="2024-01-31",
        interval=interval
    )
    print(f"{interval}: {len(df)} rows")
```

### Fetch Trade Data

```python
# Fetch individual trade data
cache = CryptoDataCache()
trades_df = cache.fetch_data(
    symbol="BTCUSDT",
    data_type=DATA_TYPES.TRADE,
    start_date_str="2024-01-01",
    end_date_str="2024-01-02"
)
```

### Custom Database Location

```python
# Use custom database path
cache = CryptoDataCache(db_path="/path/to/my/crypto_data.db")
df = cache.fetch_data("ETHUSDT", DATA_TYPES.KLINE, "2024-01-01", "2024-01-31", "1d")
```

## Requirements

- Python e 3.13
- pandas e 2.3.1
- requests e 2.32.4
- rich e 14.0.0

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Support

If you encounter any issues or have questions, please file an issue on the GitHub repository.