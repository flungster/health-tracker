"""API tests for activity duplicates (M28a): candidates, link/unlink/swap, overwrite.

The same workout uploaded twice (no shared external id across file uploads) is
the fixture for cross-source behaviour; the provider side of the same rules is
covered in test_providers_sync.py. Linked duplicates stay stored and reachable;
while linked they are excluded from the feed, counts and period summaries.
"""

from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Alice",
            "last_name": "Doe",
            "email": email,
            "password": "supersecret1",
        },
    )
    assert response.status_code == 201, response.text
    return cast(str, cast("dict[str, Any]", response.json())["token"])


def _import(client: TestClient, token: str) -> str:
    """Upload the sample GPX once more; returns the new activity's public uuid."""
    data = (Path(__file__).parent / "fixtures" / "run_sample.gpx").read_bytes()
    response = client.post(
        "/api/v1/activities",
        files={"file": ("run_sample.gpx", data, "application/octet-stream")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return cast("dict[str, Any]", response.json())["id"]


def _feed_ids(client: TestClient, token: str) -> set[str]:
    body = client.get("/api/v1/activities?limit=50", headers=_auth(token)).json()
    return {item["id"] for item in body["items"]}


def _link(client: TestClient, token: str, activity_id: str, primary_id: str) -> None:
    response = client.post(
        f"/api/v1/activities/{activity_id}/duplicates",
        json={"duplicate_of": primary_id},
        headers=_auth(token),
    )
    assert response.status_code == 204, response.text


def _linked_of(client: TestClient, token: str, primary_id: str) -> list[str]:
    body = client.get(f"/api/v1/activities/{primary_id}/duplicates", headers=_auth(token)).json()
    return [item["id"] for item in body["items"]]


def _import_file(client: TestClient, token: str, filename: str) -> str:
    """Upload a named fixture file; returns the new activity's public uuid."""
    data = (Path(__file__).parent / "fixtures" / filename).read_bytes()
    response = client.post(
        "/api/v1/activities",
        files={"file": (filename, data, "application/octet-stream")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return cast("dict[str, Any]", response.json())["id"]


def _scan(client: TestClient, token: str) -> dict[str, Any]:
    """Run the library-wide duplicate scan; returns its response body."""
    response = client.post("/api/v1/activities/duplicate-scan", headers=_auth(token))
    assert response.status_code == 200, response.text
    return cast("dict[str, Any]", response.json())


def _group_ids(body: dict[str, Any]) -> list[list[str]]:
    """The scan body's groups as lists of activity ids (member order preserved)."""
    return [[item["id"] for item in group["activities"]] for group in body["groups"]]


class TestDuplicateCandidates:
    def test_double_upload_is_a_candidate_of_each_other(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-candidates@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        body = client.get(
            f"/api/v1/activities/{first_id}/duplicate-candidates", headers=_auth(token)
        )
        assert body.status_code == 200, body.text
        data = cast("dict[str, Any]", body.json())
        assert [item["id"] for item in data["items"]] == [second_id]
        assert data["units"] in ("metric", "imperial")

    def test_candidates_excludes_linked_duplicates_and_self(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-candidates-excl@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)
        third_id = _import(client, token)
        _link(client, token, second_id, first_id)

        body = client.get(
            f"/api/v1/activities/{first_id}/duplicate-candidates", headers=_auth(token)
        ).json()
        # Only live primaries are candidates: the linked second one and self drop out.
        assert [item["id"] for item in body["items"]] == [third_id]

    def test_candidates_for_unknown_activity_is_404(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-candidates-404@example.com")
        response = client.get(
            "/api/v1/activities/b5f8c0a4-7d31-4e2b-9c65-a1b2c3d4e5f6/duplicate-candidates",
            headers=_auth(token),
        )
        assert response.status_code == 404


class TestLinkAndUnlink:
    def test_link_hides_from_feed_and_summary_but_stays_reachable(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-link@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        _link(client, token, second_id, first_id)
        assert _feed_ids(client, token) == {first_id}

        # The period summary drops the linked row too.
        body = client.get(
            "/api/v1/activities/summary",
            params={"start": "2024-06-01T00:00:00Z", "end": "2024-07-01T00:00:00Z"},
            headers=_auth(token),
        ).json()
        assert body["activity_count"]["total"] == 1

        # ...and the linked row is still reachable by its own URL.
        detail = client.get(f"/api/v1/activities/{second_id}", headers=_auth(token))
        assert detail.status_code == 200, detail.text

    def test_detail_view_exposes_the_link(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "dups-detail-link@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        # Live rows carry no link; after linking, the alias points at its primary.
        assert (
            client.get(f"/api/v1/activities/{first_id}", headers=_auth(token)).json()[
                "duplicate_of"
            ]
            is None
        )

        _link(client, token, second_id, first_id)

        detail = client.get(f"/api/v1/activities/{second_id}", headers=_auth(token)).json()
        assert detail["duplicate_of"] == first_id

    def test_linked_duplicates_listed_on_the_primary(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-listed@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        assert _linked_of(client, token, first_id) == []
        _link(client, token, second_id, first_id)
        assert _linked_of(client, token, first_id) == [second_id]

    def test_linking_a_duplicate_of_another_duplicate_is_rejected(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-depth@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)
        third_id = _import(client, token)
        _link(client, token, second_id, first_id)

        response = client.post(
            f"/api/v1/activities/{third_id}/duplicates",
            json={"duplicate_of": second_id},  # an alias, not a primary
            headers=_auth(token),
        )
        assert response.status_code == 422, response.text

    def test_linking_self_is_rejected(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "dups-self@example.com")
        first_id = _import(client, token)

        response = client.post(
            f"/api/v1/activities/{first_id}/duplicates",
            json={"duplicate_of": first_id},
            headers=_auth(token),
        )
        assert response.status_code == 422, response.text

    def test_linking_someone_elses_activity_is_rejected(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        owner = _register(client, "dups-foreign-owner@example.com")
        other = _register(client, "dups-foreign-other@example.com")
        foreign_id = _import(client, owner)

        response = client.post(
            "/api/v1/activities/b5f8c0a4-7d31-4e2b-9c65-a1b2c3d4e5f7/duplicates",
            json={"duplicate_of": foreign_id},
            headers=_auth(other),
        )
        assert response.status_code == 404, response.text

    def test_link_is_idempotent(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "dups-idempotent@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        _link(client, token, second_id, first_id)
        _link(client, token, second_id, first_id)  # already so: no error
        assert _feed_ids(client, token) == {first_id}

    def test_unlink_restores_the_row_to_the_feed(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-unlink@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)
        _link(client, token, second_id, first_id)

        response = client.delete(f"/api/v1/activities/{second_id}/duplicates", headers=_auth(token))
        assert response.status_code == 204, response.text
        assert _feed_ids(client, token) == {first_id, second_id}

    def test_unlinking_a_primary_is_rejected(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "dups-unlink-primary@example.com")
        first_id = _import(client, token)

        response = client.delete(f"/api/v1/activities/{first_id}/duplicates", headers=_auth(token))
        assert response.status_code == 422, response.text


class TestMakePrimary:
    def test_swap_makes_the_duplicate_live_and_links_the_old_primary(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-swap@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)
        _link(client, token, second_id, first_id)

        response = client.post(
            f"/api/v1/activities/{second_id}/duplicates",
            json={"duplicate_of": first_id, "make_primary": True},
            headers=_auth(token),
        )
        assert response.status_code == 204, response.text
        assert _feed_ids(client, token) == {second_id}
        assert _linked_of(client, token, second_id) == [first_id]

    def test_swap_repoints_the_targets_other_followers(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        # A->B, C linked to B; promoting A must re-point C at the new primary
        # so no chain deeper than one link exists.
        token = _register(client, "dups-swap-fanout@example.com")
        a_id = _import(client, token)
        b_id = _import(client, token)
        c_id = _import(client, token)
        _link(client, token, a_id, b_id)
        _link(client, token, c_id, b_id)

        response = client.post(
            f"/api/v1/activities/{a_id}/duplicates",
            json={"duplicate_of": b_id, "make_primary": True},
            headers=_auth(token),
        )
        assert response.status_code == 204, response.text

        linked = set(_linked_of(client, token, a_id))
        assert linked == {b_id, c_id}

    def test_swap_with_a_live_target_behaves_like_a_plain_link(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-swap-live-target@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        response = client.post(
            f"/api/v1/activities/{first_id}/duplicates",
            json={"duplicate_of": second_id, "make_primary": True},  # target is live
            headers=_auth(token),
        )
        assert response.status_code == 204, response.text
        # first stays live; second becomes its duplicate — same as a plain link.
        assert _feed_ids(client, token) == {first_id}
        assert _linked_of(client, token, first_id) == [second_id]


class TestOverwrite:
    def test_overwrite_soft_deletes_the_replaced_row(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-overwrite@example.com")
        first_id = _import(client, token)  # the original
        second_id = _import(client, token)  # the confirmed re-import

        response = client.post(
            f"/api/v1/activities/{second_id}/duplicates/overwrite",
            json={"duplicate_of": first_id},
            headers=_auth(token),
        )
        assert response.status_code == 204, response.text

        # The re-import is the only live row; the original is soft-deleted...
        assert _feed_ids(client, token) == {second_id}
        detail = client.get(f"/api/v1/activities/{first_id}", headers=_auth(token))
        assert detail.status_code == 404, detail.text

    def test_overwrite_unlinks_orphaned_aliases_of_the_replaced_row(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        # C was linked to the original; replacing the original must not strand
        # C pointing at a soft-deleted primary.
        token = _register(client, "dups-overwrite-orphan@example.com")
        first_id = _import(client, token)  # original (primary)
        second_id = _import(client, token)  # confirmed re-import
        third_id = _import(client, token)  # another source's copy of the original
        _link(client, token, third_id, first_id)

        response = client.post(
            f"/api/v1/activities/{second_id}/duplicates/overwrite",
            json={"duplicate_of": first_id},
            headers=_auth(token),
        )
        assert response.status_code == 204, response.text

        # C survives as a live activity again.
        assert _feed_ids(client, token) == {second_id, third_id}

    def test_overwrite_self_is_rejected(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "dups-overwrite-self@example.com")
        first_id = _import(client, token)

        response = client.post(
            f"/api/v1/activities/{first_id}/duplicates/overwrite",
            json={"duplicate_of": first_id},
            headers=_auth(token),
        )
        assert response.status_code == 422, response.text

    def test_overwrite_requires_the_replaced_row_to_be_live(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "dups-overwrite-dead@example.com")
        first_id = _import(client, token)

        deleted = client.delete(f"/api/v1/activities/{first_id}", headers=_auth(token))
        assert deleted.status_code == 204, deleted.text

        second_id = _import(client, token)
        response = client.post(
            f"/api/v1/activities/{second_id}/duplicates/overwrite",
            json={"duplicate_of": first_id},  # already soft-deleted
            headers=_auth(token),
        )
        assert response.status_code == 404, response.text


class TestLibraryScan:
    """The retroactive library-wide sweep (M29a): find duplicate groups in history.

    Reuses M28's matcher across the caller's live primaries; read-only (it reports,
    a human links). Linked duplicates and other users' rows are out of scope.
    """

    def test_empty_library_returns_no_groups(self, client: TestClient) -> None:
        token = _register(client, "scan-empty@example.com")

        body = _scan(client, token)
        assert body["groups"] == []
        assert body["units"] in ("metric", "imperial")

    def test_double_upload_is_one_group_in_start_order(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "scan-double@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        body = _scan(client, token)
        assert body["units"] == "metric"  # a fresh user has no imperial profile
        groups = _group_ids(body)
        assert len(groups) == 1
        # Identical imports share a start time, so the earlier-inserted row (the lower
        # id) is first — the natural primary to keep.
        assert groups[0] == [first_id, second_id]

    def test_different_sports_are_not_grouped(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "scan-sports@example.com")
        _import_file(client, token, "run_sample.gpx")  # a run (Jun 1)
        _import_file(client, token, "cycle_sample.tcx")  # a ride (Jun 15)

        body = _scan(client, token)
        # A run and a ride never match — different sport (and far apart in time).
        assert body["groups"] == []

    def test_linked_duplicates_are_excluded_from_the_scan(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "scan-linked@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)
        _link(client, token, second_id, first_id)  # hide the twin

        body = _scan(client, token)
        # Only one live primary remains for that workout: nothing left to pair with.
        assert body["groups"] == []

    def test_scan_is_scoped_to_the_caller(self, client: TestClient, uploads_dir: Path) -> None:
        owner = _register(client, "scan-scope-owner@example.com")
        other = _register(client, "scan-scope-other@example.com")
        _import_file(client, owner, "run_sample.gpx")  # two identical workouts...
        _import_file(client, other, "run_sample.gpx")  # ...but owned by different users

        # Each user has a single live primary, and the other's row is never considered:
        # neither scan can form a group. (If scoping leaked, owner's scan would pair them.)
        assert _scan(client, owner)["groups"] == []
        assert _scan(client, other)["groups"] == []

    def test_scan_reports_multiple_groups_ordered_by_earliest_start(
        self, client: TestClient, uploads_dir: Path
    ) -> None:
        token = _register(client, "scan-multi@example.com")
        run_a = _import_file(client, token, "run_sample.gpx")  # Jun 1
        run_b = _import_file(client, token, "run_sample.gpx")  # Jun 1 twin
        ride_a = _import_file(client, token, "cycle_sample.tcx")  # Jun 15
        ride_b = _import_file(client, token, "cycle_sample.tcx")  # Jun 15 twin

        body = _scan(client, token)
        groups = _group_ids(body)
        # Two clusters: the running pair (earlier start, so first), then the cycling pair.
        assert groups == [[run_a, run_b], [ride_a, ride_b]]

    def test_scan_does_not_link_anything(self, client: TestClient, uploads_dir: Path) -> None:
        token = _register(client, "scan-readonly@example.com")
        first_id = _import(client, token)
        second_id = _import(client, token)

        body = _scan(client, token)
        assert len(body["groups"]) == 1

        # The scan is a report, not an action: both rows are still live primaries and
        # nothing was linked (detail views carry no duplicate_of, feed shows both).
        assert _feed_ids(client, token) == {first_id, second_id}
        for activity_id in (first_id, second_id):
            detail = client.get(f"/api/v1/activities/{activity_id}", headers=_auth(token)).json()
            assert detail["duplicate_of"] is None

    def test_scan_requires_authentication(self, client: TestClient) -> None:
        response = client.post("/api/v1/activities/duplicate-scan")
        assert response.status_code == 401
