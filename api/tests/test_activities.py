"""API tests for activity import and activity endpoints."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.imports.parsed import ParsedTrackpoint
from app.main import app
from app.services.activity_stats import KM_METERS, ActivityStatistics, SplitUnit
from app.services.zone_reference import AGE_MAX_HR_BASE, current_age

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(
    client: TestClient,
    token: str,
    filename: str,
    data: bytes,
    extra: dict[str, str] | None = None,
) -> dict[str, object]:
    files = {"file": (filename, data, "application/octet-stream")}
    response = client.post("/api/v1/activities", files=files, data=extra, headers=_auth(token))
    body: dict[str, object] = response.json()
    return body


class TestActivityImport:
    def test_imports_gpx_run(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        body = register_user()
        token = str(body["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        detail = response.json()

        assert detail["sport_type"] == "running"  # defaulted: GPX has no sport hint
        assert detail["name"] == "Morning Run"
        assert detail["source_format"] == "gpx"
        assert detail["original_filename"] == "run_sample.gpx"
        assert detail["started_at"] == "2024-06-01T09:00:00Z"
        assert detail["duration_seconds"] == 1480
        assert detail["distance_m"] is not None
        assert 4500 < detail["distance_m"] < 5600
        assert detail["heart_rate_max_bpm"] == 160
        assert detail["heart_rate_min_bpm"] == 120
        # Zones need a profile max heart rate to be relative to; with none
        # set they are None (no misleading fallback to the activity's own max).
        assert detail["heart_rate_zones"] is None
        assert len(detail["splits"]) >= 4
        assert detail["running"] is not None
        assert detail["running"]["avg_pace_s_per_km"] is not None
        assert 250 < detail["running"]["avg_pace_s_per_km"] < 350

        # The original file is stored under uploads/<user_id>/.
        user = body["user"]
        assert isinstance(user, dict)
        user_id = str(user["id"])
        stored = list((uploads_dir / user_id).iterdir())
        assert len(stored) == 1
        assert stored[0].name.endswith(".gpx")

    def test_imports_tcx_cycling_with_power(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={
                "file": ("cycle_sample.tcx", _read("cycle_sample.tcx"), "application/octet-stream")
            },
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        detail = response.json()

        assert detail["sport_type"] == "cycling"
        assert detail["name"] == "Evening Ride"
        assert detail["calories_kcal"] == 320.0
        assert detail["cycling"] is not None
        # Power comes from the trackpoints: 200..240 in steps of 10.
        assert detail["cycling"]["power_avg_w"] == 220
        assert detail["cycling"]["power_max_w"] == 240
        assert len(detail["splits"]) >= 4

    def test_imports_fit_run(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={
                "file": (
                    "run_garmin_fenix5.fit",
                    _read("run_garmin_fenix5.fit"),
                    "application/octet-stream",
                )
            },
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        detail = response.json()

        assert detail["sport_type"] == "running"
        assert detail["source_format"] == "fit"
        assert detail["distance_m"] == pytest.approx(157.56)
        assert detail["heart_rate_max_bpm"] is not None

    def test_sport_and_name_overrides(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            data={"sport_type": "hiking", "name": "Weekend Trail"},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        detail = response.json()
        assert detail["sport_type"] == "hiking"
        assert detail["name"] == "Weekend Trail"

    def test_rejects_unknown_format(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "IMPORT_ERROR"

    def test_rejects_corrupt_fit(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("bad.fit", _read("fit_corrupt_crc.fit"), "application/octet-stream")},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "IMPORT_ERROR"

    def test_rejects_bad_sport_override(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            data={"sport_type": "skydiving"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_oversized_file(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        settings = get_settings().model_copy(
            update={"uploads_dir": str(uploads_dir), "max_upload_mb": 1}
        )
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = client.post(
                "/api/v1/activities",
                files={
                    "file": ("big.gpx", b"\x00" * (1024 * 1024 + 16), "application/octet-stream")
                },
                headers=_auth(token),
            )
        finally:
            app.dependency_overrides.pop(get_settings, None)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "maximum upload size" in error["message"]

    def test_rejects_file_with_too_many_trackpoints(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        # The GPX fixture carries 75 trackpoints; drop the cap well below that.
        settings = get_settings().model_copy(
            update={"uploads_dir": str(uploads_dir), "max_trackpoints": 10}
        )
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = client.post(
                "/api/v1/activities",
                files={
                    "file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")
                },
                headers=_auth(token),
            )
        finally:
            app.dependency_overrides.pop(get_settings, None)
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "IMPORT_ERROR"
        assert "trackpoints" in error["message"]

    def test_requires_authentication(self, client: TestClient, uploads_dir: Path) -> None:
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
        )
        assert response.status_code == 401


class TestActivityEndpoints:
    def _import_two(self, client: TestClient, token: str) -> None:
        for filename in ("run_sample.gpx", "cycle_sample.tcx"):
            response = client.post(
                "/api/v1/activities",
                files={"file": (filename, _read(filename), "application/octet-stream")},
                headers=_auth(token),
            )
            assert response.status_code == 201, response.text

    def test_list_newest_first_with_pagination(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        self._import_two(client, token)

        response = client.get("/api/v1/activities", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        # The ride (2024-06-15) is newer than the run (2024-06-01).
        assert body["items"][0]["sport_type"] == "cycling"
        assert body["items"][1]["sport_type"] == "running"

        page = client.get("/api/v1/activities?limit=1&offset=1", headers=_auth(token)).json()
        assert len(page["items"]) == 1
        assert page["items"][0]["sport_type"] == "running"

    def test_detail_and_trackpoints(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        imported = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        activity_id = imported.json()["id"]

        detail = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token))
        assert detail.status_code == 200
        assert detail.json()["id"] == activity_id

        points = client.get(f"/api/v1/activities/{activity_id}/trackpoints", headers=_auth(token))
        assert points.status_code == 200
        body = points.json()
        assert len(body["items"]) == 75
        assert body["items"][0]["seq"] == 0
        assert body["items"][0]["lat"] == pytest.approx(48.85, abs=1e-5)

        splits = client.get(f"/api/v1/activities/{activity_id}/splits", headers=_auth(token)).json()
        assert len(splits["items"]) >= 4
        assert splits["items"][0]["split_index"] == 1

    def test_unknown_activity_is_404(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        response = client.get(
            "/api/v1/activities/11111111-1111-1111-1111-111111111111",
            headers=_auth(token),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_cannot_access_another_users_activity(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        owner = str(register_user(email="owner@example.com")["token"])
        intruder = str(register_user(email="intruder@example.com")["token"])
        imported = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(owner),
        )
        activity_id = imported.json()["id"]

        response = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(intruder))
        assert response.status_code == 404

    def test_update_name_and_sport(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        imported = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        activity_id = imported.json()["id"]

        response = client.patch(
            f"/api/v1/activities/{activity_id}",
            json={"name": "Renamed Run", "sport_type": "walking"},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Renamed Run"
        assert body["sport_type"] == "walking"

    def test_update_rejects_bad_sport(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        imported = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        activity_id = imported.json()["id"]

        response = client.patch(
            f"/api/v1/activities/{activity_id}",
            json={"sport_type": "skydiving"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_delete_soft_deletes(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        imported = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        activity_id = imported.json()["id"]

        response = client.delete(f"/api/v1/activities/{activity_id}", headers=_auth(token))
        assert response.status_code == 204

        assert (
            client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token)).status_code == 404
        )
        assert client.get("/api/v1/activities", headers=_auth(token)).json()["total"] == 0

    def test_sports_list(self, client: TestClient, register_user: Any) -> None:
        token = str(register_user()["token"])
        response = client.get("/api/v1/sports", headers=_auth(token))
        assert response.status_code == 200
        # Reference-table backed: each entry is {value, description}.
        sports = response.json()["sports"]
        values = [entry["value"] for entry in sports]
        assert "running" in values
        assert "cycling" in values
        assert "strength" in values
        running = next(entry for entry in sports if entry["value"] == "running")
        assert running["description"] == "Running"


class TestActivityStatistics:
    def test_splits_group_and_pace(self) -> None:
        base = datetime(2024, 1, 1, tzinfo=UTC)
        # ~2.1 km straight north at 10 s intervals: 0.001 deg ~ 111 m.
        points: list[ParsedTrackpoint] = []
        for i in range(20):
            points.append(
                ParsedTrackpoint(
                    recorded_at=base + timedelta(seconds=10 * i),
                    lat=48.0 + 0.001 * i,
                    lon=2.0,
                )
            )
        splits = ActivityStatistics().compute_splits(points, SplitUnit.KM, KM_METERS)
        assert len(splits) == 3  # two full km + the ~0.11 km remainder
        assert splits[0].split_index == 1
        # 1 km takes ~9 steps x 10 s = ~90 s.
        assert 80 <= splits[0].duration_seconds <= 100
        assert splits[0].pace_seconds == pytest.approx(splits[0].duration_seconds, rel=0.05)
        assert splits[1].split_index == 2


class TestHeartRateZonesViewTime:
    """Zones are relative to the viewer's profile max heart rate.

    They are computed at view time from the stored trackpoints, so they
    follow the profile — setting or changing the max heart rate later
    changes them without re-importing the activity.
    """

    def _import_run(self, client: TestClient, token: str) -> str:
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    def _zones(self, client: TestClient, token: str, activity_id: str) -> dict[str, object]:
        response = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token))
        assert response.status_code == 200, response.text
        zones = response.json()["heart_rate_zones"]
        assert zones is not None
        return zones

    def test_no_zones_without_a_profile_max_hr(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        response = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token))
        assert response.status_code == 200
        detail = response.json()
        # The activity has HR data (120-160 bpm) but with no reference it is
        # not shown as zones — the old fallback to the activity's own max HR
        # made everything look like zone 5.
        assert detail["heart_rate_max_bpm"] == 160
        assert detail["heart_rate_zones"] is None

    def test_zones_follow_the_profile_max_hr_without_reimport(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        for max_heart_rate, has_zone_5 in ((180, True), (200, False)):
            profile = client.patch(
                "/api/v1/users/me/profile",
                json={"max_heart_rate": max_heart_rate},
                headers=_auth(token),
            )
            assert profile.status_code == 200, profile.text

            zones = self._zones(client, token, activity_id)
            # The fixture's HR is 120-160 bpm: 120 is 60-67% (zone 2-3),
            # so zone 1 (below 56%) stays empty either way.
            assert zones["zone_1_seconds"] == 0
            # 160 bpm is 89% of 180 (zone 5) but exactly 80% of 200
            # (zone 4), so zone 5 empties when the max heart rate changes — for the
            # same imported activity.
            assert (zones["zone_5_seconds"] > 0) is has_zone_5


# A GPX with GPS samples but no heart-rate data at all.
_NO_HR_GPX = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="health-tracker-test" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>No HR Run</name>
    <trkseg>
      <trkpt lat="48.850" lon="2.350"><ele>40</ele><time>2024-06-01T09:00:00Z</time></trkpt>
      <trkpt lat="48.851" lon="2.351"><ele>42</ele><time>2024-06-01T09:05:00Z</time></trkpt>
    </trkseg>
  </trk>
</gpx>"""


@contextmanager
def _direct_session(engine: Engine) -> Iterator[Session]:
    """A session outside the app's request lifecycle (closed on exit)."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


class TestZoneReferenceAndSnapshots:
    """Zones follow the profile's zone reference (custom > max HR > age).

    The result for a reference is kept as one live ``activity_zone_snapshots``
    row per activity: reused while the reference is unchanged, superseded (old
    row soft-deleted for history) when it changes. See M13b.
    """

    def _import_run(self, client: TestClient, token: str) -> str:
        response = client.post(
            "/api/v1/activities",
            files={"file": ("run_sample.gpx", _read("run_sample.gpx"), "application/octet-stream")},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    def _detail_zones(
        self, client: TestClient, token: str, activity_id: str
    ) -> dict[str, object] | None:
        response = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token))
        assert response.status_code == 200, response.text
        return response.json()["heart_rate_zones"]

    def _patch_profile(self, client: TestClient, token: str, body: dict[str, object]) -> None:
        response = client.patch("/api/v1/users/me/profile", json=body, headers=_auth(token))
        assert response.status_code == 200, response.text

    def _snapshot_rows(self, engine: Engine, activity_id: str) -> list[tuple[object, ...]]:
        with _direct_session(engine) as session:
            rows = session.execute(
                text(
                    "SELECT source, max_heart_rate, age,"
                    " custom_zone_1_top_bpm, deleted_at"
                    " FROM activity_zone_snapshots WHERE activity_id = :a ORDER BY id"
                ),
                {"a": activity_id},
            ).all()
        return [tuple(row) for row in rows]

    def test_age_reference_computes_zones(
        self, client: TestClient, register_user: Any, uploads_dir: Path
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        # No manual max HR — only a date of birth (age 42 as of writing).
        self._patch_profile(client, token, {"date_of_birth": "1984-05-01"})

        zones = self._detail_zones(client, token, activity_id)
        assert zones is not None
        # The age-derived max HR (220 - 42 = 178) is below 200, so the
        # trailing-160-bpm samples land in zone 5 — where they would be empty
        # against a manual max HR of exactly 200 (80% = 160, band is
        # inclusive). This proves the age reference drives the bands.
        assert zones["zone_5_seconds"] > 0

    def test_age_snapshot_records_source_and_derived_values(
        self, client: TestClient, register_user: Any, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        date_of_birth = date(1984, 5, 1)
        self._patch_profile(client, token, {"date_of_birth": "1984-05-01"})
        self._detail_zones(client, token, activity_id)

        age = current_age(date_of_birth, date.today())
        rows = self._snapshot_rows(engine, activity_id)
        assert len(rows) == 1
        source, max_hr, stored_age, custom_1, deleted_at = rows[0]
        assert source == "age"
        # The derived max HR and the age at computation time are recorded.
        assert (max_hr, stored_age) == (AGE_MAX_HR_BASE - age, age)
        assert custom_1 is None  # a non-custom reference stores no tops
        assert deleted_at is None

    def test_custom_boundaries_replace_percent_bands(
        self, client: TestClient, register_user: Any, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        # Custom tops win over the manual max HR (200). Against custom
        # boundaries most of the 120-160 ramp sits at or below top 1 (150);
        # against percent-of-200 bands zone 1 would be empty (min HR 120 is
        # above 56% of 200). So zone_1_seconds > 0 proves the custom bands ran.
        self._patch_profile(
            client,
            token,
            {
                "max_heart_rate": 200,
                "custom_zone_1_top_bpm": 150,
                "custom_zone_2_top_bpm": 152,
                "custom_zone_3_top_bpm": 154,
                "custom_zone_4_top_bpm": 160,
            },
        )

        zones = self._detail_zones(client, token, activity_id)
        assert zones is not None
        assert int(zones["zone_1_seconds"]) > 0  # would be 0 under percent-of-200
        assert int(zones["zone_5_seconds"]) == 0  # nothing above top 4 (160)
        total = sum(int(zones[f"zone_{i}_seconds"]) for i in range(1, 6))
        assert total == 1480  # the whole HR timeline is distributed

        rows = self._snapshot_rows(engine, activity_id)
        assert len(rows) == 1
        source, max_hr, _age, custom_1, deleted_at = rows[0]
        assert source == "custom"
        assert max_hr is None  # a custom reference stores no effective max HR
        assert custom_1 == 150
        assert deleted_at is None

    def test_snapshot_reused_until_reference_changes(
        self, client: TestClient, register_user: Any, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        activity_id = self._import_run(client, token)

        self._patch_profile(client, token, {"max_heart_rate": 180})
        first = self._detail_zones(client, token, activity_id)

        # Repeated views under the same reference reuse the snapshot: no new
        # rows are written and the zones do not change.
        for _ in range(2):
            assert self._detail_zones(client, token, activity_id) == first
        rows = self._snapshot_rows(engine, activity_id)
        assert len(rows) == 1

        # Changing the reference supersedes: a fresh computation is stored and
        # the old row kept (soft-deleted) for history.
        self._patch_profile(client, token, {"max_heart_rate": 200})
        second = self._detail_zones(client, token, activity_id)

        # 160 bpm is exactly 80% of 200 (zone 4), so zone 5 empties.
        assert int(second["zone_5_seconds"]) == 0

        rows = self._snapshot_rows(engine, activity_id)
        assert len(rows) == 2  # one superseded + one live, not destroyed
        live = [row for row in rows if row[4] is None]
        assert len(live) == 1
        assert live[0][1] == 200
        superseded = [row for row in rows if row[4] is not None]
        assert len(superseded) == 1
        assert superseded[0][1] == 180

    def test_no_snapshot_without_an_hr_timeline(
        self, client: TestClient, register_user: Any, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        response = client.post(
            "/api/v1/activities",
            files={"file": ("no_hr.gpx", _NO_HR_GPX, "application/octet-stream")},
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        activity_id = str(response.json()["id"])

        self._patch_profile(client, token, {"max_heart_rate": 180})
        zones = self._detail_zones(client, token, activity_id)

        # No HR data: no zones and nothing to snapshot.
        assert zones is None
        assert self._snapshot_rows(engine, activity_id) == []

    def test_snapshot_is_scoped_to_the_activity(
        self, client: TestClient, register_user: Any, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        first_id = self._import_run(client, token)
        second_id = self._import_run(client, token)

        self._patch_profile(client, token, {"max_heart_rate": 180})
        self._detail_zones(client, token, first_id)

        # A second activity has no snapshot yet; viewing it does not read the
        # first one's stored zones.
        rows_first = self._snapshot_rows(engine, first_id)
        assert len(rows_first) == 1

        self._detail_zones(client, token, second_id)
        rows_second = self._snapshot_rows(engine, second_id)
        assert len(rows_second) == 1
