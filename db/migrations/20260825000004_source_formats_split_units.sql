-- Reference tables for the remaining enum-like columns:
-- activities.source_format and activity_splits.split_type.

-- migrate:up

CREATE TABLE source_formats (
    value         text PRIMARY KEY,
    description   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE source_formats IS
    'Reference table of the file formats activities can be imported from. Seeded and immutable.';
COMMENT ON COLUMN source_formats.value IS
    'Canonical format code; the public API value and the FK target (e.g. gpx).';
COMMENT ON COLUMN source_formats.description IS
    'Human-readable label for UI display (e.g. GPX).';

INSERT INTO source_formats (value, description) VALUES
    ('gpx',          'GPX'),
    ('tcx',          'TCX'),
    ('fit',          'FIT'),
    ('apple_health', 'Apple Health export');

ALTER TABLE activities
    DROP CONSTRAINT activities_source_format_check,
    ADD CONSTRAINT activities_source_format_fkey
        FOREIGN KEY (source_format) REFERENCES source_formats (value);

CREATE TABLE split_units (
    value         text PRIMARY KEY,
    description   text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE split_units IS
    'Reference table of the distance units splits are precomputed in. Seeded and immutable.';
COMMENT ON COLUMN split_units.value IS
    'Canonical unit code; the public API value and the FK target (km or mi).';
COMMENT ON COLUMN split_units.description IS
    'Human-readable label for UI display (e.g. Kilometres).';

INSERT INTO split_units (value, description) VALUES
    ('km', 'Kilometres'),
    ('mi', 'Miles');

ALTER TABLE activity_splits
    DROP CONSTRAINT activity_splits_split_type_check,
    ADD CONSTRAINT activity_splits_split_type_fkey
        FOREIGN KEY (split_type) REFERENCES split_units (value);

COMMENT ON COLUMN activity_splits.split_type IS
    'Unit of the split distance; FK to split_units.value (km or mi).';

-- migrate:down

ALTER TABLE activity_splits
    DROP CONSTRAINT activity_splits_split_type_fkey,
    ADD CONSTRAINT activity_splits_split_type_check
        CHECK (split_type IN ('km', 'mi'));

COMMENT ON COLUMN activity_splits.split_type IS
    'Unit of the split distance: km or mi.';

DROP TABLE split_units;

ALTER TABLE activities
    DROP CONSTRAINT activities_source_format_fkey,
    ADD CONSTRAINT activities_source_format_check
        CHECK (source_format IN ('gpx', 'tcx', 'fit', 'apple_health'));

DROP TABLE source_formats;
