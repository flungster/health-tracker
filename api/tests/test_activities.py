"""API tests for activity import and activity endpoints."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.imports.parsed import ParsedActivity, ParsedTrackpoint
from app.main import app
from app.services.activity_stats import KM_METERS, ActivityStatistics

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
        assert detail["heart_rate_zones"] is not None
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
        sports = response.json()["sports"]
        assert "running" in sports
        assert "cycling" in sports
        assert "strength" in sports


class TestActivityStatistics:
    def test_hr_zones_distribution(self) -> None:
        base = datetime(2024, 1, 1, tzinfo=UTC)

        def point(minutes: int, heart_rate: int) -> ParsedTrackpoint:
            return ParsedTrackpoint(
                recorded_at=base + timedelta(minutes=minutes),
                heart_rate_bpm=heart_rate,
            )

        activity = ParsedActivity(trackpoints=[point(0, 100), point(5, 150), point(10, 180)])
        zones = ActivityStatistics().compute_hr_zones(activity.trackpoints, max_heart_rate=200)
        assert zones is not None
        # 100bpm = 50% -> zone 1, 150bpm = 75% -> zone 4, 180bpm -> zone 5 (no time after).
        assert zones.zone_1_seconds == 300
        assert zones.zone_4_seconds == 300
        assert zones.zone_2_seconds == 0
        assert zones.zone_3_seconds == 0
        assert zones.zone_5_seconds == 0

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
        splits = ActivityStatistics().compute_splits(points, "km", KM_METERS)
        assert len(splits) == 3  # two full km + the ~0.11 km remainder
        assert splits[0].split_index == 1
        # 1 km takes ~9 steps x 10 s = ~90 s.
        assert 80 <= splits[0].duration_seconds <= 100
        assert splits[0].pace_seconds == pytest.approx(splits[0].duration_seconds, rel=0.05)
        assert splits[1].split_index == 2
