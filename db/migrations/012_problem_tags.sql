BEGIN;

ALTER TABLE problems
    ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_problems_tags ON problems USING GIN (tags);

COMMENT ON COLUMN problems.tags IS 'Array of topic tags (e.g. arrays, dp, strings)';

-- Optionally update your existing problems with tags (you can do this via SQL or UI)
UPDATE problems SET tags = ARRAY['math'] WHERE title = 'Sum Two Numbers';
UPDATE problems SET tags = ARRAY['math', 'dp'] WHERE title = 'Fibonacci Sequence';
UPDATE problems SET tags = ARRAY['strings', 'two-pointers'] WHERE title = 'Palindrome Check';
UPDATE problems SET tags = ARRAY['strings', 'two-pointers'] WHERE title = 'Reverse a String';
UPDATE problems SET tags = ARRAY['arrays', 'iteration'] WHERE title = 'Maximum in Array';
UPDATE problems SET tags = ARRAY['strings', 'iteration'] WHERE title = 'Count Vowels';
UPDATE problems SET tags = ARRAY['arrays', 'hash-table'] WHERE title = 'Two Sum';
UPDATE problems SET tags = ARRAY['strings', 'stack'] WHERE title = 'Balanced Parentheses';
UPDATE problems SET tags = ARRAY['arrays', 'dp', 'binary-search'] WHERE title = 'Longest Increasing Subsequence';
UPDATE problems SET tags = ARRAY['strings', 'dp'] WHERE title = 'Edit Distance';

COMMIT;
