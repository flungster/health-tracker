-- Reference table for sport/activity types (enum-like values get a
-- reference table + FK instead of text + CHECK, per AGENTS.md).

-- migrate:up

CREATE TABLE activity_types (
    value         text PRIMARY KEY,
    description   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE activity_types IS
    'Reference table of canonical sport/activity types. Rows are seeded and immutable.';
COMMENT ON COLUMN activity_types.value IS
    'Canonical type code; the public API value and the FK target (e.g. running).';
COMMENT ON COLUMN activity_types.description IS
    'Human-readable label for UI display (e.g. Running).';

INSERT INTO activity_types (value, description) VALUES
    ('running',  'Running'),
    ('cycling',  'Cycling'),
    ('rowing',   'Rowing'),
    ('strength', 'Strength'),
    ('yoga',     'Yoga'),
    ('hiking',   'Hiking'),
    ('walking',  'Walking'),
    ('swimming', 'Swimming'),
    ('other',    'Other');

ALTER TABLE activities
    DROP CONSTRAINT activities_sport_type_check,
    ADD CONSTRAINT activities_sport_type_fkey
        FOREIGN KEY (sport_type) REFERENCES activity_types (value);

COMMENT ON COLUMN activities.sport_type IS
    'Sport category; FK to activity_types.value. Drives which <sport>_activity table and detail view apply.';

-- migrate:down

ALTER TABLE activities
    DROP CONSTRAINT activities_sport_type_fkey,
    ADD CONSTRAINT activities_sport_type_check
        CHECK (sport_type IN (
            'running', 'cycling', 'rowing', 'strength',
            'yoga', 'hiking', 'walking', 'swimming', 'other'
        ));

COMMENT ON COLUMN activities.sport_type IS
    'Sport category; drives which <sport>_activity table and detail view apply.';

DROP TABLE activity_types;
