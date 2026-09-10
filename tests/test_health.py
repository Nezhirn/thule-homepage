"""Health endpoint, cache headers and security headers."""
import config


def test_health_reports_version(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": config.APP_VERSION}


def test_security_headers_are_set(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_index_is_not_cached(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_index_references_versioned_assets(client):
    html = client.get("/").text
    assert "__VERSION__" not in html
    assert f"css/styles.css?v={config.APP_VERSION}" in html
    assert f"js/app.js?v={config.APP_VERSION}" in html
    assert client.get(f"/js/app.js?v={config.APP_VERSION}").status_code == 200


def test_static_assets_are_revalidated(client):
    response = client.get("/css/styles.css")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_cors_is_not_enabled(client):
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
