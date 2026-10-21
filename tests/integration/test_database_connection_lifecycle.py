import sqlite3

from mediguard.services import application as app


def test_database_context_closes_sqlite_connection(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIGUARD_DB_PATH", str(tmp_path / "claims.db"))
    with app.db() as connection:
        connection.execute("SELECT 1")
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError("The database context left its SQLite connection open.")
