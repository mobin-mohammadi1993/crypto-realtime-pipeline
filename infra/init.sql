-- Raw trade ticks, one row per trade event off Binance's stream.
CREATE TABLE IF NOT EXISTS raw_trades (
    trade_id        BIGINT,
    symbol          VARCHAR(20) NOT NULL,
    price           NUMERIC(20, 8) NOT NULL,
    quantity        NUMERIC(20, 8) NOT NULL,
    trade_time      BIGINT NOT NULL,
    is_buyer_maker  BOOLEAN,
    event_time      TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_trades_symbol_time ON raw_trades(symbol, event_time);

-- 1-minute tumbling-window aggregates, written by the Spark job once each
-- window's watermark closes.
CREATE TABLE IF NOT EXISTS price_metrics_1m (
    window_start    TIMESTAMP NOT NULL,
    window_end      TIMESTAMP NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    avg_price       NUMERIC(20, 8) NOT NULL,
    min_price       NUMERIC(20, 8) NOT NULL,
    max_price       NUMERIC(20, 8) NOT NULL,
    total_volume    NUMERIC(20, 8) NOT NULL,
    trade_count     BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_metrics_symbol_window ON price_metrics_1m(symbol, window_start);
