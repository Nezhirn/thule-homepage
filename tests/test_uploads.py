"""Upload validation, serving and deletion rules."""
import re

from helpers import PNG_BYTES, SVG_BYTES, upload_image

from services import safe_upload_path


def test_upload_returns_uuid_filename(client):
    response = upload_image(client)
    assert response.status_code == 200
    body = response.json()
    assert re.fullmatch(r"[0-9a-f]{32}\.png", body["filename"])
    assert body["url"] == f"/api/uploads/{body['filename']}"


def test_upload_normalises_jpeg_extension(client):
    from helpers import JPEG_BYTES

    response = upload_image(client, filename="photo.jpg", content=JPEG_BYTES, content_type="image/jpeg")
    assert response.json()["filename"].endswith(".jpeg")


def test_upload_accepts_gif_and_webp(client):
    from helpers import GIF_BYTES, WEBP_BYTES

    assert upload_image(client, content=GIF_BYTES, content_type="image/gif").status_code == 200
    assert upload_image(client, content=WEBP_BYTES, content_type="image/webp").status_code == 200


def test_upload_rejects_svg_even_with_spoofed_content_type(client):
    response = upload_image(client, filename="x.png", content=SVG_BYTES, content_type="image/png")
    assert response.status_code == 400


def test_upload_rejects_arbitrary_bytes(client):
    response = upload_image(client, filename="x.png", content=b"#!/bin/sh\nrm -rf /", content_type="image/png")
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client):
    oversized = PNG_BYTES + b"\x00" * (10 * 1024 * 1024 + 1)
    response = upload_image(client, content=oversized)
    assert response.status_code == 413


def test_serve_upload_sets_cache_and_security_headers(client):
    filename = upload_image(client).json()["filename"]

    response = client.get(f"/api/uploads/{filename}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_serve_upload_rejects_unknown_extension(client):
    assert client.get("/api/uploads/whatever.svg").status_code == 404
    assert client.get("/api/uploads/whatever.txt").status_code == 404


def test_serve_upload_returns_404_for_missing_file(client):
    assert client.get("/api/uploads/" + "a" * 32 + ".png").status_code == 404


def test_safe_upload_path_blocks_traversal_and_absolute_paths(data_paths):
    import pytest
    from fastapi import HTTPException

    data_paths["uploads"].mkdir(parents=True, exist_ok=True)
    for bad in ["../homepage.db", "/etc/passwd", "..\\evil", "\x00", ""]:
        with pytest.raises(HTTPException):
            safe_upload_path(bad)


def test_safe_upload_path_blocks_symlink_escape(data_paths):
    import os

    import pytest
    from fastapi import HTTPException

    uploads = data_paths["uploads"]
    uploads.mkdir(parents=True, exist_ok=True)
    link = uploads / "escape.png"
    os.symlink("/etc/passwd", link)

    with pytest.raises(HTTPException):
        safe_upload_path("escape.png")


def test_delete_uploaded_file(client, data_paths):
    filename = upload_image(client).json()["filename"]

    response = client.delete(f"/api/upload/{filename}")

    assert response.status_code == 204
    assert not (data_paths["uploads"] / filename).exists()


def test_delete_missing_upload_is_404(client):
    assert client.delete("/api/upload/" + "b" * 32 + ".png").status_code == 404


def test_delete_upload_in_use_is_conflict(client, data_paths):
    filename = upload_image(client).json()["filename"]
    client.post("/api/cards", json={"title": "uses icon", "icon_path": filename})

    response = client.delete(f"/api/upload/{filename}")

    assert response.status_code == 409
    assert (data_paths["uploads"] / filename).exists()


def test_delete_background_upload_is_conflict(client):
    filename = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": filename})

    assert client.delete(f"/api/upload/{filename}").status_code == 409
