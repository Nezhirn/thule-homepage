"""Optional token authentication: open health, protected API, cookie for images."""
from helpers import PNG_BYTES

TOKEN = "test-secret-token"
HEADERS = {"X-Auth-Token": TOKEN}


def test_auth_disabled_when_token_not_configured(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/full-data").status_code == 200
    assert client.post("/api/cards", json={"title": "open"}).status_code == 201


def test_health_and_frontend_stay_public(auth_client):
    assert auth_client.get("/api/health").status_code == 200
    assert auth_client.get("/").status_code == 200
    assert auth_client.get("/css/styles.css").status_code == 200


def test_api_requires_token(auth_client):
    response = auth_client.get("/api/full-data")
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    # The security-header middleware must also cover early 401 responses.
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_wrong_token_is_rejected(auth_client):
    assert auth_client.get("/api/full-data", headers={"X-Auth-Token": "nope"}).status_code == 401


def test_header_token_authorizes_and_sets_session_cookie(auth_client):
    response = auth_client.get("/api/full-data", headers=HEADERS)
    assert response.status_code == 200
    assert "thule_session" in response.cookies or "thule_session" in auth_client.cookies


def test_bearer_token_is_accepted(auth_client):
    response = auth_client.get("/api/full-data", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200


def upload_image_auth(auth_client):
    response = auth_client.post(
        "/api/upload",
        files={"file": ("image.png", PNG_BYTES, "image/png")},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    return response


def test_cookie_authorizes_image_loads_but_not_mutations(auth_client):
    filename = upload_image_auth(auth_client).json()["filename"]

    # Image GET works with the session cookie only (no header).
    image = auth_client.get(f"/api/uploads/{filename}")
    assert image.status_code == 200

    # Mutations still require the explicit header.
    assert auth_client.post("/api/cards", json={"title": "cookie only"}).status_code == 401
    assert auth_client.post("/api/cards", json={"title": "with header"}, headers=HEADERS).status_code == 201


def test_import_requires_authentication(auth_client):
    assert auth_client.post("/api/import", json={"cards": []}).status_code == 401
