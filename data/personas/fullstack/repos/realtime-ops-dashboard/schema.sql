-- synthetic: true
CREATE TABLE IF NOT EXISTS system_telemetry (
    id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(64) NOT NULL,
    cpu_percent NUMERIC(5, 2) NOT NULL,
    memory_mb INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_telemetry_node_time ON system_telemetry(node_id, recorded_at DESC);
