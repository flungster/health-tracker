-- M14a: per-user unit-system setting (metric vs imperial display).
--   * ``user_profiles`` gains a nullable timestamp that expresses the user's
--     display preference as "imperial has been in effect since" instead of a
--     boolean: NULL = metric (the default), set = imperial, and the value is
--     when it was enabled. Toggling back to metric clears the column (the last
--     enable instant is intentionally dropped — the setting has two states).
--   * Display-only: activity data stays stored in SI units; conversion to the
--     user's display system happens at the API view layer (M14b), so no
--     activity rows are touched by this migration.

-- migrate:up

ALTER TABLE user_profiles
    ADD COLUMN imperial_units_enabled_at timestamptz NULL;

COMMENT ON COLUMN user_profiles.imperial_units_enabled_at IS
    'When the user enabled imperial display units (UTC). NULL means metric, the default; a set value means imperial is in effect from that instant. Toggling back to metric clears the column. Display-only: activity data is always stored in SI units and converted at the API view layer.';

-- migrate:down

ALTER TABLE user_profiles
    DROP COLUMN imperial_units_enabled_at;
