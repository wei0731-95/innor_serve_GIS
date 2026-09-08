def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert isinstance(body["facility_count"], int)
    assert isinstance(body["version"], str) and body["version"]
    assert body["sync_running"] is False


def test_health_counts_facilities(synced_client):
    body = synced_client.get("/api/health").json()
    assert body["facility_count"] == synced_client.get("/api/facilities").json()["count"]


def test_docs_and_openapi_available(client):
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    for path in ("/api/health", "/api/facilities", "/api/facilities/{facility_id}", "/api/categories", "/api/sources", "/api/sync", "/api/sync/{source_id}"):
        assert path in paths
    # /api/docs 轉址到 /docs
    redirect = client.get("/api/docs", follow_redirects=False)
    assert redirect.status_code in (302, 307)
    assert redirect.headers["location"] == "/docs"


def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/facilities",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/api/facilities",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert denied.headers.get("access-control-allow-origin") is None
