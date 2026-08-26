"""Tests for the shared DAO base methods (list, get_by_id, get_by_uuid).

These exercise the identifier convention end to end: an int ``id`` primary
key plus a public ``uuid`` column, using ``strength_exercise_sets`` (the
first ``IntIdUuidModel`` table) as the live example.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.dao.strength_exercise_set_dao import StrengthExerciseSetDao
from app.models.strength_exercise_set import StrengthExerciseSet

FIXTURES = Path(__file__).parent / "fixtures"


def _import_gpx(client: TestClient, token: str) -> str:
    """Import the sample run and return the new activity's public uuid."""
    data = (FIXTURES / "run_sample.gpx").read_bytes()
    response = client.post(
        "/api/v1/activities",
        files={"file": ("run_sample.gpx", data, "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@contextmanager
def _direct_session(engine: Engine) -> Iterator[Session]:
    """A session outside the app's request lifecycle.

    Always closed (and rolled back) on exit, even when the test body
    fails — an open transaction would block the per-test TRUNCATE.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


class TestDaoBases:
    def test_list_pagination_get_by_id_and_get_by_uuid(
        self, client: TestClient, register_user, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        activity_uuid = _import_gpx(client, token)

        uuids = [uuid4() for _ in range(3)]
        with _direct_session(engine) as session:
            for index, row_uuid in enumerate(uuids, start=1):
                session.add(
                    StrengthExerciseSet(
                        uuid=row_uuid,
                        activity_id=activity_uuid,
                        exercise_name="Squats",
                        set_index=index,
                        reps=10,
                        weight_kg=80.0,
                    )
                )
            session.commit()

            dao = StrengthExerciseSetDao(session)

            # list(offset, limit) pages over the rows...
            first_page = dao.list(offset=0, limit=2)
            assert len(first_page) == 2
            second_page = dao.list(offset=2, limit=10)
            assert len(second_page) == 1

            # ...get_by_uuid fetches by the public uuid...
            fetched = dao.get_by_uuid(uuids[1])
            assert fetched is not None
            assert fetched.set_index == 2
            assert fetched.uuid == uuids[1]

            # ...get_by_id fetches by the internal int id...
            by_id = dao.get_by_id(fetched.id)
            assert by_id is not None
            assert by_id.uuid == uuids[1]

            # Unknown keys return None.
            assert dao.get_by_uuid(uuid4()) is None
            assert dao.get_by_id(999_999) is None

    def test_list_for_activity_orders_by_set_index(
        self, client: TestClient, register_user, uploads_dir: Path, engine: Engine
    ) -> None:
        token = str(register_user()["token"])
        activity_uuid = _import_gpx(client, token)

        with _direct_session(engine) as session:
            for index in (3, 1, 2):
                session.add(
                    StrengthExerciseSet(
                        uuid=uuid4(),
                        activity_id=activity_uuid,
                        exercise_name="Bench Press",
                        set_index=index,
                    )
                )
            session.commit()

            rows = StrengthExerciseSetDao(session).list_for_activity(activity_uuid)
            assert [row.set_index for row in rows] == [1, 2, 3]
