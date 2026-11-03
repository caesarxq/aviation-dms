import asyncio
import sqlite3

import pytest

from app import database


def _init_at(path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(path))
    asyncio.run(database.init_db())


def test_existing_database_gets_unique_mission_lifecycle_indexes(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    _init_at(path, monkeypatch)

    conn = sqlite3.connect(path)
    try:
        expected = {
            "flight_releases": "idx_flight_releases_mission_unique",
            "post_flight_reports": "idx_post_flight_reports_mission_unique",
        }
        for table, index_name in expected.items():
            indexes = {row[1]: row[2] for row in conn.execute(f"PRAGMA index_list({table})")}
            assert indexes.get(index_name) == 1
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("table", "id_column", "first_id", "second_id", "insert_sql", "params"),
    [
        (
            "flight_releases",
            "release_id",
            "REL-1",
            "REL-2",
            "INSERT INTO flight_releases (release_id, mission_id, plan_id, released_by, released_at, created_at) VALUES (?,?,?,?,?,?)",
            ("PLAN-1", "u-admin", "now", "now"),
        ),
        (
            "post_flight_reports",
            "report_id",
            "PFR-1",
            "PFR-2",
            "INSERT INTO post_flight_reports (report_id, mission_id, submitted_by, submitted_at, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            ("u-admin", "now", "now", "now"),
        ),
    ],
)
def test_upgrade_refuses_duplicate_lifecycle_rows_without_deleting_them(
    table, id_column, first_id, second_id, insert_sql, params, tmp_path, monkeypatch
):
    path = tmp_path / f"legacy-{table}.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.execute(insert_sql, (first_id, "M-DUP", *params))
    conn.execute(insert_sql, (second_id, "M-DUP", *params))
    conn.commit()
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", str(path))

    with pytest.raises(RuntimeError, match=f"duplicate {table} rows for mission M-DUP"):
        asyncio.run(database.init_db())

    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(f"SELECT {id_column} FROM {table} WHERE mission_id='M-DUP' ORDER BY {id_column}").fetchall()
        assert rows == [(first_id,), (second_id,)]
    finally:
        conn.close()
