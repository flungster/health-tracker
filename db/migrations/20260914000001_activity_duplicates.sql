-- M28a: cross-source duplicate linking + soft-delete-aware provider dedup.
--   * ``activities`` gains a self-referencing ``duplicate_of``: when set, the
--     row is a linked duplicate of another (the "primary") one. It stays fully
--     stored and reachable by its own URL, but is excluded from feeds, lists
--     and summaries. Depth is at most one (a linked duplicate cannot itself
--     have duplicates) — enforced by the API, kept simple on purpose. This is
--     a visibility decision, never data loss: unlinking or swapping makes the
--     row live again.
--   * The provider dedup index is rebuilt to be soft-delete-aware, so a
--     "delete + re-import" (overwrite) of a provider activity can insert a
--     fresh row instead of violating the unique constraint.

-- migrate:up

ALTER TABLE activities
    ADD COLUMN duplicate_of uuid NULL REFERENCES activities (uuid);

COMMENT ON COLUMN activities.duplicate_of IS
    'When set, this activity is a linked duplicate of the referenced (primary) one: kept stored and reachable by its own URL, but excluded from feeds/lists/summaries. At most one level deep — a linked duplicate cannot itself have duplicates (enforced by the API). Reversible: clearing it makes this row live again.';

DROP INDEX activities_provider_external_activity_id_key;
CREATE UNIQUE INDEX activities_live_provider_external_activity_id_key
    ON activities (provider, external_activity_id)
    WHERE provider IS NOT NULL AND external_activity_id IS NOT NULL AND deleted_at IS NULL;

COMMENT ON INDEX activities_live_provider_external_activity_id_key IS
    'At most one LIVE row per (provider, external activity id); a soft-deleted history may be re-imported on top of it (overwrite).';

-- migrate:down

DROP INDEX activities_live_provider_external_activity_id_key;
CREATE UNIQUE INDEX activities_provider_external_activity_id_key
    ON activities (provider, external_activity_id)
    WHERE provider IS NOT NULL AND external_activity_id IS NOT NULL;

ALTER TABLE activities
    DROP COLUMN duplicate_of;
