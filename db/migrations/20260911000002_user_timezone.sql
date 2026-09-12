-- M23a: per-user display timezone.
--   * ``user_profiles`` gains a nullable IANA time-zone name (e.g.
--     "Europe/Berlin"). NULL = the browser's local timezone, which stays the
--     app default (today's behavior). Display-only: activity data is stored in
--     UTC; the client renders timestamps and day boundaries (feed "Today /
--     Yesterday" grouping, dashboard period edges) in this zone.

-- migrate:up

ALTER TABLE user_profiles
    ADD COLUMN timezone text NULL;

COMMENT ON COLUMN user_profiles.timezone IS
    'IANA time-zone name (e.g. "Europe/Berlin") for rendering timestamps and day boundaries in the UI; NULL means the browser''s local timezone (the default). Display-only: stored data is UTC.';

-- migrate:down

ALTER TABLE user_profiles
    DROP COLUMN timezone;
