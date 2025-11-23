#!/usr/bin/env python3
"""
Stock Price Consumer Application.

Consumes stock prices from Kafka and processes them.
"""

import json
import os
from datetime import datetime
from typing import Dict, List

from kafka import KafkaConsumer
from kafka.errors import KafkaError


def process_stock_price(price_data: Dict) -> None:
    """
    Process a stock price message.

    Args:
        price_data: Dictionary containing symbol, price, and timestamp
    """
    symbol = price_data.get("symbol", "UNKNOWN")
    price = price_data.get("price", 0.0)
    timestamp = price_data.get("timestamp", "")

    print(f"[{timestamp}] Processed {symbol}: ${price:.2f}")


def main():
    """Main consumer loop."""
    kafka_broker = os.getenv("KAFKA_BROKER", "localhost:9092")
    kafka_topic = os.getenv("KAFKA_TOPIC", "stock-prices")
    consumer_group = os.getenv("CONSUMER_GROUP", "stock-price-processors")

    print(f"Starting Stock Price Consumer")
    print(f"  Kafka Broker: {kafka_broker}")
    print(f"  Kafka Topic: {kafka_topic}")
    print(f"  Consumer Group: {consumer_group}")

    try:
        consumer = KafkaConsumer(
            kafka_topic,
            bootstrap_servers=[kafka_broker],
            group_id=consumer_group,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",  # Start from beginning if no offset
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
        )
        print(f"Connected to Kafka broker at {kafka_broker}")
        print(f"Subscribed to topic: {kafka_topic}")
        print("Waiting for messages...")
    except Exception as e:
        print(f"Failed to connect to Kafka: {e}")
        return

    try:
        for message in consumer:
            try:
                price_data = message.value
                process_stock_price(price_data)
            except json.JSONDecodeError as e:
                print(f"Error decoding message: {e}")
            except Exception as e:
                print(f"Error processing message: {e}")

    except KeyboardInterrupt:
        print("\nShutting down consumer...")
    except KafkaError as e:
        print(f"Kafka error: {e}")
    finally:
        consumer.close()
        print("Consumer closed")


if __name__ == "__main__":
    main()
