# Changelog

All notable changes to health-tracker are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/) — see
[docs/release.md](docs/release.md) for the release process.

## Unreleased

- Provider integrations (opt-in, read-only, your own account only): connect a
  Strava account from Profile → Connected accounts (OAuth 2.0, signed
  state-bound callback) and disconnect it again. Activity sync from a
  connected provider is still in progress. New API: `GET /providers`,
  `GET /providers/{p}/connect`, `GET /providers/{p}/oauth/callback`,
  `GET|DELETE /providers/{p}/connection`; new `PROVIDER_ERROR` (502) error
  code. Configure with `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` (see
  docs/installation.md); without them the stack runs exactly as before.
- Identifier convention: every non-reference table has an int `id` primary
  key; publicly identified rows additionally carry a `uuid` column that the
  API exposes as the public `"id"` (API contract and URLs unchanged).
- `activities` provenance: `source_format` is now nullable and describes the
  file/export format only; provider-fetched rows carry `provider` +
  `external_activity_id` (deduped by a partial unique index).

## 0.2.0 — 2026-08-25

Hardening, operations, and schema conventions:

- Hardening: per-IP rate limits on login (10/min) and register (5/min),
  returned as 429 `RATE_LIMITED` with a `Retry-After` header.
- Import safety: files with more than `MAX_TRACKPOINTS` trackpoints
  (default 100,000) are rejected; oversized uploads are rejected without
  being fully buffered.
- `GET /api/v1/health` now reports the deployed API `version`.
- Backup tooling: `make backup` / `make restore BACKUP=<dir>` (pg_dump custom
  format + uploads tarball).
- CI (GitHub Actions): lint, API tests, image builds, and an end-to-end smoke
  test on every push/PR.
- Reference tables for enum-like values: `activity_types`, `source_formats`,
  and `split_units` are now seeded reference tables referenced by foreign key
  (replacing `text` + `CHECK`), with matching Python enums; `GET /sports`
  returns `{value, description}` pairs and the web sport picker shows the
  display labels.
- Release process documented in `docs/release.md`; version is tracked in
  `VERSION` (kept in sync with `api/pyproject.toml` by CI).
- README now notes the project is built with AI, with a development log of
  the agent and open-source models used.

## 0.1.0 — 2026-08-24

Initial release (MVP):

- Accounts: register, login, profile (name, email, password, heart-rate
  settings), JWT sessions, argon2id password hashing.
- Activity import: GPX, TCX, FIT; derived splits (km/mi), heart-rate zones,
  and per-sport metrics; original file stored per user.
- Activities API: paginated feed, detail, trackpoints, splits, rename,
  soft delete; canonical sport list.
- Web UI: day-grouped feed, drag-and-drop upload, activity detail (route map,
  splits, heart-rate chart + zones, sport-specific metrics), profile page.
- Docker deployment (Postgres 16, dbmate migrations, multi-stage images,
  non-root API) and full documentation set.
