# Changelog

All notable changes to health-tracker are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/) — see
[docs/release.md](docs/release.md) for the release process.

## Unreleased

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
- Release process documented in `docs/release.md`; version is tracked in
  `VERSION` (kept in sync with `api/pyproject.toml` by CI).

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
