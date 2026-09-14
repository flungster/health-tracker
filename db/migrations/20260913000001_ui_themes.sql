-- M25a: per-user UI theme (dark mode first).
--   * ``ui_themes``: reference table of the themes a user can select (light /
--     dark / system). Rows are seeded and immutable, same convention as the
--     other reference tables. "system" means follow the OS color scheme; it is
--     resolved client-side, so no other schema is involved.
--   * ``user_profiles`` gains a nullable theme (FK to ui_themes.value).
--     NULL = the app default, which is light. Display-only: nothing about the
--     stored activity data changes with it.

-- migrate:up

CREATE TABLE ui_themes (
    value         text PRIMARY KEY,
    description   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE ui_themes IS
    'Reference table of the UI themes a user can select. Rows are seeded and immutable.';
COMMENT ON COLUMN ui_themes.value IS
    'Canonical theme code (light, dark, system); the public API value and FK target. "system" follows the OS color scheme (resolved in the browser).';
COMMENT ON COLUMN ui_themes.description IS
    'Human-readable label for UI display (e.g. Dark).';

INSERT INTO ui_themes (value, description) VALUES
    ('light',  'Light'),
    ('dark',   'Dark'),
    ('system', 'System');

ALTER TABLE user_profiles
    ADD COLUMN theme text NULL REFERENCES ui_themes (value);

COMMENT ON COLUMN user_profiles.theme IS
    'Selected UI theme; NULL means the app default (light). Display-only.';

-- migrate:down

ALTER TABLE user_profiles
    DROP COLUMN theme;

DROP TABLE ui_themes;
