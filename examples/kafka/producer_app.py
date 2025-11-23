#!/usr/bin/env python3
"""
Stock Price Producer Application.

Fetches live stock prices from Yahoo Finance and publishes them to Kafka.
"""

import json
import os
import time
from datetime import datetime
from typing import List

import yfinance as yf
from kafka import KafkaProducer
from kafka.errors import KafkaError


def get_stock_price(symbol: str) -> dict:
    """
    Fetch current stock price for a given symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')

    Returns:
        Dictionary with symbol, price, and timestamp
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.history(period="1d", interval="1m")
        if not info.empty:
            # Get the latest price
            latest = info.iloc[-1]
            price = float(latest["Close"])
        else:
            # Fallback to current info if history is not available
            info_dict = ticker.info
            price = float(info_dict.get("currentPrice", 0.0))

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return {
            "symbol": symbol,
            "price": 0.0,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": str(e),
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
