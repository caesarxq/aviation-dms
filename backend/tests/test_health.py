from app import main


def test_health_reports_database_unavailable_as_unhealthy(client, monkeypatch):
    class BrokenDatabase:
        async def execute(self, query):
            raise RuntimeError("database connection unavailable")

        async def close(self):
            return None

    async def broken_get_db():
        return BrokenDatabase()

    monkeypatch.setattr(main, "get_db", broken_get_db)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not ready"}


def test_health_returns_ready_when_database_query_succeeds(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
