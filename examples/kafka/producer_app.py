#!/usr/bin/env python3
"""
Stock Price Producer Application.

Generates mock stock prices and publishes them to Kafka.
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Dict

from kafka import KafkaProducer
from kafka.errors import KafkaError

# Base prices for each symbol (starting prices)
BASE_PRICES: Dict[str, float] = {
    "AAPL": 175.00,
    "GOOGL": 140.00,
    "MSFT": 380.00,
    "TSLA": 250.00,
}

# Track current prices for each symbol
current_prices: Dict[str, float] = {}


def get_stock_price(symbol: str) -> dict:
    """
    Generate a mock stock price for a given symbol with realistic variation.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')

    Returns:
        Dictionary with symbol, price, and timestamp
    """
    # Initialize base price if not set
    if symbol not in current_prices:
        current_prices[symbol] = BASE_PRICES.get(symbol, 100.0)

    # Generate price variation (-2% to +2% per update)
    variation = random.uniform(-0.02, 0.02)
    current_prices[symbol] = current_prices[symbol] * (1 + variation)

    # Ensure price doesn't go below $1
    current_prices[symbol] = max(current_prices[symbol], 1.0)

    return {
        "symbol": symbol,
        "price": round(current_prices[symbol], 2),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def main():
    """Main producer loop."""
    # Get configuration from environment variables
    stock_symbols = os.getenv("STOCK_SYMBOLS", "AAPL,GOOGL,MSFT,TSLA").split(",")
    stock_symbols = [s.strip().upper() for s in stock_symbols if s.strip()]

    kafka_broker = os.getenv("KAFKA_BROKER", "localhost:9092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "stock-prices")
    fetch_interval = int(os.getenv("FETCH_INTERVAL", "5"))

    print(f"Starting Stock Price Producer")
    print(f"  Symbols: {stock_symbols}")
    print(f"  Kafka Broker: {kafka_broker}")
    print(f"  Kafka Topic: {kafka_topic}")
    print(f"  Fetch Interval: {fetch_interval}s")

    # Initialize Kafka producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=[kafka_broker],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=5,
            acks="all",
        )
        print(f"Connected to Kafka broker at {kafka_broker}")
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        return

    # Main loop: fetch prices and publish to Kafka
    try:
        while True:
            for symbol in stock_symbols:
                try:
                    # Fetch stock price
                    price_data = get_stock_price(symbol)

                    # Publish to Kafka
                    future = producer.send(kafka_topic, value=price_data)
                    record_metadata = future.get(timeout=10)

                    print(
                        f"[{price_data['timestamp']}] Published {symbol}: "
                        f"${price_data['price']:.2f} "
                        f"(partition: {record_metadata.partition}, "
                        f"offset: {record_metadata.offset})"
                    )
                except KafkaError as e:
                    print(f"Kafka error publishing {symbol}: {e}")
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")

            # Wait before next fetch cycle
            time.sleep(fetch_interval)

    except KeyboardInterrupt:
        print("\nShutting down producer...")
    finally:
        producer.close()
        print("Producer closed")


if __name__ == "__main__":
    main()
