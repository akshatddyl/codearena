BEGIN;

CREATE TABLE IF NOT EXISTS contests (
    id          BIGSERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    start_time  TIMESTAMPTZ NOT NULL,
    end_time    TIMESTAMPTZ NOT NULL,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_contests_time ON contests(start_time);

COMMENT ON TABLE contests IS 'Timed programming contests';

-- Insert a dummy contest starting in 2 days
INSERT INTO contests (title, description, start_time, end_time, is_published)
VALUES (
    'Weekly Contest 1',
    'Compete against other users in a timed 90-minute contest.',
    NOW() + INTERVAL '2 days',
    NOW() + INTERVAL '2 days' + INTERVAL '90 minutes',
    TRUE
) ON CONFLICT DO NOTHING;

COMMIT;
