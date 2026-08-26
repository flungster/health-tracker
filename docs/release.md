# Releasing

Releases are **git tags**. There is no package registry and no container
registry — users update by pulling a tag and rebuilding their images.

## Versioning

- The root `VERSION` file is the single source of truth for the app version.
  `api/pyproject.toml` must carry the same value; CI fails when they drift.
- The version is visible at runtime in `GET /api/v1/health` (`"version"`
  field) and in the API's OpenAPI docs.
- [Semantic Versioning](https://semver.org/):
  - **major** — breaking changes to the API, database schema, or
    configuration
  - **minor** — new features (additive API endpoints, UI, import formats)
  - **patch** — bug fixes and hardening

## Cutting a release

1. Make sure `main` is green: `make lint && make test` locally, CI passing.
2. Update `CHANGELOG.md`: move the `## Unreleased` entries under a new
   `## X.Y.Z — YYYY-MM-DD` heading.
3. Bump `VERSION` **and** `api/pyproject.toml` to the same value.
4. Commit the three files as `release: vX.Y.Z`.
5. Tag and push:

   ```bash
   git tag vX.Y.Z
   git push origin main vX.Y.Z
   ```

## Updating an installation

```bash
git fetch --tags
git checkout vX.Y.Z      # or: git pull for the latest on main
make up                  # rebuilds changed images, applies new migrations
```

After an update, `curl -s localhost:9090/api/v1/health` shows the new
`version`.

## Rollback

```bash
git checkout <previous-tag>
make up
```

Migrations only move forward. If a rollback crosses a migration boundary,
restore a pre-downgrade database backup instead (`make backup` beforehand;
see [Installation → Backups](installation.md#backups)).
