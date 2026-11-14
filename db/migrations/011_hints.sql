BEGIN;

CREATE TABLE IF NOT EXISTS problem_hints (
    id          BIGSERIAL PRIMARY KEY,
    problem_id  BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
    ordinal     INTEGER NOT NULL,
    content     TEXT NOT NULL,
    UNIQUE(problem_id, ordinal)
);

COMMENT ON TABLE problem_hints IS 'Progressive hints for a problem';

COMMIT;
