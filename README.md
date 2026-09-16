# Crypto Real-Time Streaming Pipeline

A real-time data pipeline for crypto markets: live trades come in off
Binance's public WebSocket feed, get queued in Kafka, aggregated by Spark
Structured Streaming, and land in Postgres a few seconds later. A
Streamlit dashboard reads that warehouse and shows 20 coins updating
live.

This started from a real freelance brief asking for exactly this stack
(Kafka, Spark Streaming, Postgres, Docker). The data isn't simulated.
Every price on the dashboard is a real trade happening on Binance right
now, pulled from their public market-data stream, which needs no API key
and no account.

## What it does

```
Binance WebSocket (real trades)
        |
        v
   producer.py  --publishes JSON-->  Kafka topic "crypto_trades"
                                              |
                                              v
                                  Spark Structured Streaming
                                  (raw pass-through + 1-min
                                   windowed aggregation)
                                              |
                                              v
                                        Postgres
                                    raw_trades / price_metrics_1m
                                              |
                                              v
                                    Streamlit dashboard
```

- **Producer** (`producer/producer.py`) opens one WebSocket connection to
  Binance, subscribed to 20 symbols' live trade feeds, and publishes each
  trade to Kafka as it happens. Reconnects automatically if the
  connection drops.
- **Kafka** (`apache/kafka`, KRaft mode) is the buffer between the
  producer and Spark. A single broker, one topic, auto-created on first
  publish.
- **Spark** (`spark_consumer/streaming_job.py`) runs two streaming
  queries off the same Kafka topic: one writes every trade straight
  through to `raw_trades`, the other groups trades into 1-minute
  per-symbol windows (avg/min/max price, total volume, trade count) and
  writes those to `price_metrics_1m` once each window's watermark closes.
- **Postgres** is the warehouse both the Spark job writes to and the
  dashboard reads from.
- **Dashboard** (`dashboard/app.py`) is a Streamlit app: a card grid of
  all 20 coins with sparklines, and a detail panel for whichever one is
  selected, with a full price/volume chart and its recent trades.
  Refreshes every 5 seconds through a Streamlit fragment, not a full page
  reload, so only the numbers move, not the whole layout.

## Running it

Requires Docker Desktop.

```bash
docker compose up -d --build
```

This pulls Kafka, builds the Spark image (the biggest one, takes a few
minutes the first time), and starts everything. Once it's up:

- `localhost:8501` -- the dashboard
- `localhost:29092` -- Kafka, if you want to inspect the topic directly
- `localhost:5432` -- Postgres (`warehouse` db, `postgres`/`postgres`)

Give it a minute or two after startup: the first 1-minute aggregation
window needs to close (plus a 2-minute watermark) before
`price_metrics_1m` has its first rows and the dashboard has anything to
chart. `raw_trades` fills immediately.

### If Binance isn't reachable directly

Some networks can't reach Binance without a proxy. If yours can't, set
`WS_PROXY_HOST` / `WS_PROXY_PORT` in `docker-compose.yml` under the
`producer` service to a SOCKS5 proxy reachable from inside the container
(`host.docker.internal` reaches a proxy running on the host itself). Leave
them unset if you don't need one.

## Deploying it for real

`terraform/` provisions a single EC2 instance that runs this whole
stack. See [terraform/README.md](terraform/README.md) for usage and
cost. It validates in CI (`terraform fmt`/`validate` on every push) but
hasn't been applied against a live AWS account.

## Design decisions worth explaining

- **Binance's public stream, not a paid data vendor.** The trade stream
  (`<symbol>@trade`) needs no API key and no account, which keeps this
  runnable by anyone who clones the repo. A production system trading
  real money would want a paid, SLA-backed feed instead.
- **One Kafka broker, one partition per topic.** Plenty for a demo at
  this message rate. A production deployment would run a multi-broker
  cluster with more partitions, both for throughput and so a single
  broker dying doesn't take the pipeline down.
- **Spark in local mode, not a real cluster.** `spark-submit --master
  local[*]` runs the whole job in one container. It's genuinely Spark
  Structured Streaming, same APIs, same semantics, just not distributed
  across worker nodes. Twenty symbols' worth of trades doesn't need a
  cluster to keep up; a much higher-volume feed would.
- **The Kafka/Postgres JDBC packages are baked into the Spark image at
  build time** (see `spark_consumer/Dockerfile`), not fetched via
  `--packages` at every container start. Resolving them from Maven on
  every restart is slow and, on a bad connection, unreliable. Building
  them in once means the container never needs network access just to
  start the streaming job.
- **`st.fragment(run_every=...)` instead of a sleep-and-rerun loop.** An
  earlier version auto-refreshed by looping `time.sleep()` +
  `st.rerun()` at the top level, which reruns the entire script every
  cycle. That visibly flashes the whole page on every refresh, and
  because it rebuilds every chart from scratch, a click landing mid-flash
  reliably got lost. Scoping the refresh to a fragment means only that
  fragment's contents redraw, and interactions inside it stay
  responsive.

## What I'd add before calling this production-ready

- A real Kafka cluster (multiple brokers, replication factor > 1) so one
  broker failing doesn't stop the pipeline
- Schema validation on the producer side (a malformed Binance message
  right now would just fail JSON parsing silently in Spark)
- Alerting if the producer's WebSocket disconnects for longer than a few
  reconnect cycles
- A real Spark cluster if the symbol list or trade volume grew
  significantly
- Retention/compaction policy on the Kafka topic and on `raw_trades` --
  right now both grow forever

## License

MIT. See [LICENSE](LICENSE).
