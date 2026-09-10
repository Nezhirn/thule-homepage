"""Settings endpoint behaviour, especially partial updates (review C3)."""
from helpers import upload_image


def test_get_settings_creates_defaults(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["background_image"] is None
    assert body["blur_radius"] == 0
    assert body["dark_mode"] is False


def test_partial_update_preserves_background_image(client, data_paths):
    filename = upload_image(client).json()["filename"]
    assert client.put("/api/settings", json={"background_image": filename}).status_code == 200

    response = client.put("/api/settings", json={"blur_radius": 5})

    assert response.status_code == 200
    assert response.json()["background_image"] == filename
    assert response.json()["blur_radius"] == 5
    assert (data_paths["uploads"] / filename).exists()


def test_partial_update_preserves_dark_mode(client):
    assert client.put("/api/settings", json={"dark_mode": True}).status_code == 200
    response = client.put("/api/settings", json={"blur_radius": 3})
    assert response.json()["dark_mode"] is True


def test_explicit_null_clears_background_and_deletes_file(client, data_paths):
    filename = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": filename})

    response = client.put("/api/settings", json={"background_image": None})

    assert response.status_code == 200
    assert response.json()["background_image"] is None
    assert not (data_paths["uploads"] / filename).exists()


def test_replacing_background_deletes_old_file(client, data_paths):
    first = upload_image(client).json()["filename"]
    second = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": first})

    client.put("/api/settings", json={"background_image": second})

    assert not (data_paths["uploads"] / first).exists()
    assert (data_paths["uploads"] / second).exists()


def test_background_path_traversal_is_rejected(client, data_paths):
    for bad in ["/etc/passwd", "../homepage.db", "..\\..\\windows", "a/b.png", "..", "\x00evil"]:
        response = client.put("/api/settings", json={"background_image": bad})
        assert response.status_code in (400, 422), f"{bad!r} should be rejected, got {response.status_code}"
    assert data_paths["db"].exists()


def test_blur_radius_bounds_are_enforced(client):
    assert client.put("/api/settings", json={"blur_radius": -1}).status_code == 422
    assert client.put("/api/settings", json={"blur_radius": 100000}).status_code == 422


def test_unknown_fields_are_rejected(client):
    assert client.put("/api/settings", json={"unknown_field": 1}).status_code == 422
