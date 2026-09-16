"""
Kafka producer fed by Binance's public trade stream.

What this file does, step by step:
  1. Opens one WebSocket connection to Binance, subscribed to the live
     "trade" feed for a list of symbols (BTCUSDT, ETHUSDT, ...). This is
     real market data, public, no API key needed.
  2. Every time Binance pushes a trade event down that socket, we pull out
     the fields we care about and publish them as a JSON message to a
     Kafka topic.
  3. If the connection drops for any reason (network blip, Binance
     restarting the socket, etc.), we reconnect automatically after a
     short pause instead of letting the whole producer die.

This is the "producer" half of the Kafka pipeline: it only writes to
Kafka. The Spark job in spark_consumer/ is what reads from Kafka.
"""
import json
import os
import time

import websocket
from kafka import KafkaProducer

# All of these can be overridden via docker-compose environment variables
# instead of editing the code.
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:29092")
TOPIC = os.getenv("KAFKA_TOPIC", "crypto_trades")
SYMBOLS = [s.strip().lower() for s in os.getenv("SYMBOLS", "btcusdt,ethusdt").split(",")]

# Binance isn't reachable directly from inside this container on this
# network, only through the SOCKS5 proxy already running on the host
# (the same one Docker Desktop itself uses to pull images). Leave these
# unset to connect directly, which is what most networks need.
WS_PROXY_HOST = os.getenv("WS_PROXY_HOST")
WS_PROXY_PORT = os.getenv("WS_PROXY_PORT")

# Binance lets you subscribe to several symbols on one connection by
# combining them into a single stream URL, e.g.
# wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade
STREAM_URL = "wss://stream.binance.com:9443/stream?streams=" + "/".join(f"{s}@trade" for s in SYMBOLS)

# One producer instance, reused for every message (creating a new one per
# message would be slow and would open a new connection to Kafka each time).
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    # Batch up to 50ms of messages before sending, instead of one network
    # round-trip per trade. At thousands of trades/minute this matters.
    linger_ms=50,
)

sent_count = 0


def on_message(ws, message):
    """Called by the websocket library for every message Binance sends."""
    global sent_count
    payload = json.loads(message)
    trade = payload.get("data")
    # The combined-stream wrapper can also carry non-trade control
    # messages; skip anything that isn't an actual trade event.
    if not trade or trade.get("e") != "trade":
        return

    # Binance's field names are single letters (s=symbol, t=trade id,
    # p=price, q=quantity, T=trade time, m=was the buyer the maker).
    # We rename them here so everything downstream (Spark, Postgres,
    # the dashboard) works with readable column names instead.
    # Price and quantity are kept as strings on purpose: Binance sends
    # them as strings, and converting to float here would silently lose
    # precision before the data even reaches Spark.
    event = {
        "symbol": trade["s"],
        "trade_id": trade["t"],
        "price": trade["p"],
        "quantity": trade["q"],
        "trade_time": trade["T"],
        "is_buyer_maker": trade["m"],
    }
    producer.send(TOPIC, value=event)

    sent_count += 1
    if sent_count % 500 == 0:
        print(f"[producer] sent {sent_count} trades so far")


def on_error(ws, error):
    print(f"[producer] websocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"[producer] websocket closed: {close_status_code} {close_msg}")


def on_open(ws):
    print(f"[producer] connected, streaming: {SYMBOLS}")


def run():
    """
    Keep the WebSocket connection alive forever. run_forever() blocks
    until the connection closes (for any reason); when that happens we
    just open a fresh one after a short delay, so a dropped connection
    at 3am doesn't quietly stop the whole pipeline.
    """
    while True:
        try:
            ws = websocket.WebSocketApp(
                STREAM_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            proxy_kwargs = {}
            if WS_PROXY_HOST and WS_PROXY_PORT:
                proxy_kwargs = {
                    "http_proxy_host": WS_PROXY_HOST,
                    "http_proxy_port": int(WS_PROXY_PORT),
                    "proxy_type": "socks5h",  # the "h" makes DNS resolution happen through the proxy too
                }
            ws.run_forever(ping_interval=20, ping_timeout=10, **proxy_kwargs)
        except Exception as exc:
            print(f"[producer] crashed: {exc}")
        print("[producer] reconnecting in 5s...")
        time.sleep(5)


if __name__ == "__main__":
    run()
