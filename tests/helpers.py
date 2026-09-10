"""Small helpers shared between backend tests."""
from fastapi.testclient import TestClient

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
GIF_BYTES = b"GIF89a" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 32
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"


def upload_image(
    client: TestClient,
    filename: str = "image.png",
    content: bytes = PNG_BYTES,
    content_type: str = "image/png",
):
    return client.post("/api/upload", files={"file": (filename, content, content_type)})


def create_card(client: TestClient, **overrides):
    payload = {"title": "Example", "url": "https://example.com", "size": "1x1", "grid_col": 1, "grid_row": 1}
    payload.update(overrides)
    response = client.post("/api/cards", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
