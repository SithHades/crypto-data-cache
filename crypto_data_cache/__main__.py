"""
Command-line interface for crypto-data-cache.

Usage:
    python -m crypto_data_cache --help
"""

import sys


def main():
    """Main CLI entry point."""
    print("Crypto Data Cache - CLI interface")
    print("For API usage, import the CryptoDataCache class:")
    print("  from crypto_data_cache import CryptoDataCache")
    print()
    print("Example:")
    print("  cache = CryptoDataCache()")
    print(
        "  df = cache.fetch_data('BTCUSDT', DATA_TYPES.KLINE, '2024-01-01', '2024-01-31', '1h')"
    )

    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print()
        print("For detailed documentation, see the README at:")
        print("https://github.com/yourusername/crypto-data-cache")


if __name__ == "__main__":
    main()
